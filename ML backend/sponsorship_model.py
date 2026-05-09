"""Cold-start sponsorship predictor for VisaRank.

Two stacked logistic-regression models:

  1. Main classifier — predicts P(company sponsors a new H-1B hire) from:
       * NAICS industry code (when known)
       * Petitioner state (when known)
       * Char n-grams of the company name (3-5 letter sliding windows,
         TF-IDF weighted) — gives every name a unique fingerprint instead
         of relying on hand-picked substring flags
       * Hand-picked substring flags (TECHNOLOGIES / CONSULTING / etc.)
       * Name shape (length, word count, has-digit)

  2. NAICS imputer — predicts the most likely NAICS sector for a company
     given only its name (also char-n-grams). This is what makes the main
     classifier useful at cold-start: when a LinkedIn posting gives us
     just a name, we impute NAICS first, then run the main model.

The main label is non-leaky: ``new_emp_approval > 0`` for the company.
USCIS-derived counts are deliberately NOT used as features.

Public API (used by sponsorship.py for the cold-start fallback):

    predict_sponsorship_probability(name, naics=None, state=None) -> float

CLI:
    python sponsorship_model.py --train     # train + persist + report metrics
    python sponsorship_model.py "Acme Inc"  # one-off prediction
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, average_precision_score, brier_score_loss,
    classification_report, roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "visarank.db"
MODEL_PATH = PROJECT_ROOT / "sponsorship_model.joblib"

# Categorical features above this cardinality get bucketed into "OTHER".
TOP_NAICS_K = 25

# Substrings that show up in sponsor-heavy company names. Picked from
# inspection of the data — not exhaustive, just enough to give the LR
# meaningful name-shape signal at cold-start time.
NAME_TOKEN_FLAGS = [
    "TECHNOLOG", "CONSULT", "SOFTWARE", "SYSTEM", "SOLUTION",
    "GLOBAL", "SERVICES", "GROUP", "LAB", "RESEARCH",
    "DATA", "DIGITAL", "NETWORK", "ANALYTIC", "INFOTECH",
    "BIO", "PHARMA", "MEDICAL", "HEALTH",
    "FINANCIAL", "CAPITAL", "BANK",
    "ENGINEER", "INFRASTRUCTURE",
    "AMERICA", "INTERNATIONAL",
]


# ---------------------------------------------------------------------------
# NAICS keyword dictionary -- used to impute industry from a job description
# or title when the caller doesn't pass an explicit NAICS code. Phrases are
# multi-word where possible to keep false positives down ("software engineer"
# is a much stronger industry signal than the bare word "engineer").
# ---------------------------------------------------------------------------

NAICS_KEYWORDS: dict[str, list[str]] = {
    # 54 -- Professional / Scientific / Technical Services (most "tech" jobs)
    "54": [
        "software engineer", "machine learning", "data scientist",
        "kubernetes", "react", "python", "devops", "site reliability",
        "consulting", "product manager", "ml engineer", "developer",
        "backend engineer", "frontend engineer", "full stack",
        "cloud platform", "platform engineer", "engineering manager",
        "tensorflow", "pytorch", "saas",
    ],
    # 51 -- Information (publishing, broadcasting, telecom, media)
    "51": [
        "streaming", "broadcasting", "publishing", "telecommunications",
        "cable network", "internet service", "media platform",
        "content delivery", "video on demand", "subscriber",
        "wireless network", "fiber optic", "ott platform",
        "newsroom", "radio station",
    ],
    # 52 -- Finance and Insurance
    "52": [
        "trading desk", "portfolio manager", "underwriter",
        "hedge fund", "fintech", "actuarial", "risk model",
        "asset management", "wealth management", "investment banking",
        "credit risk", "derivatives", "quantitative analyst",
        "loan origination", "claims adjuster", "fixed income",
    ],
    # 62 -- Health Care and Social Assistance
    "62": [
        "patient", "clinical", "ehr", "electronic health record",
        "physician", "nurse", "hospital", "medical device",
        "pharmacy", "diagnosis", "treatment", "healthcare provider",
        "icu", "telehealth", "health plan", "registered nurse",
    ],
    # 31-33 -- Manufacturing
    "31-33": [
        "production line", "quality control", "manufacturing process",
        "industrial engineer", "assembly line", "automotive",
        "aerospace", "lean manufacturing", "supply chain manager",
        "iso 9001", "six sigma", "machinist", "fabrication",
    ],
    # 23 -- Construction
    "23": [
        "construction site", "civil engineer", "general contractor",
        "building permits", "site supervisor", "structural engineer",
        "bim", "blueprint", "osha",
    ],
    # 72 -- Accommodation and Food Services
    "72": [
        "restaurant", "kitchen staff", "hospitality industry",
        "barista", "chef", "front of house", "back of house",
        "hotel manager", "food service", "line cook", "sous chef",
    ],
    # 44-45 -- Retail Trade
    "44-45": [
        "retail store", "merchandise", "point of sale", "cashier",
        "store associate", "visual merchandising", "stockroom",
        "ecommerce fulfillment",
    ],
    # 48-49 -- Transportation and Warehousing
    "48-49": [
        "logistics", "freight", "trucking", "warehouse operations",
        "supply chain logistics", "fleet management", "dispatcher",
        "last mile", "shipping and receiving",
    ],
    # 61 -- Educational Services
    "61": [
        "curriculum", "k-12", "tutoring", "lecturer", "professor",
        "classroom", "instructional design", "school district",
        "academic advisor",
    ],
    # 56 -- Administrative and Support (staffing / outsourcing / facilities)
    "56": [
        "staffing agency", "recruiting agency", "outsourcing",
        "bpo", "facilities management", "janitorial",
        "temp agency", "contract staffing",
    ],
}

# Need at least this many keyword hits before we trust the dictionary's
# answer. Below this threshold we fall back to the name-based ML imputer.
NAICS_DICT_MIN_HITS = 2


# ---------------------------------------------------------------------------
# Training-data assembly
# ---------------------------------------------------------------------------

def load_training_frame(db_path: Path = DB_PATH) -> pd.DataFrame:
    """One row per normalized company. Aggregates across fiscal years."""
    if not db_path.exists():
        raise FileNotFoundError(
            f"{db_path} not found. Run sponsorship.py --reload first."
        )
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        """
        SELECT
            normalized_name,
            MAX(display_name) AS display_name,
            -- modal-ish NAICS / state across years for this company
            (SELECT naics_code FROM companies c2
             WHERE c2.normalized_name = c.normalized_name
             GROUP BY naics_code ORDER BY COUNT(*) DESC LIMIT 1) AS naics_code,
            (SELECT state FROM companies c2
             WHERE c2.normalized_name = c.normalized_name
             GROUP BY state ORDER BY COUNT(*) DESC LIMIT 1) AS state,
            SUM(new_emp_approval)        AS new_emp_approval,
            SUM(change_of_emp_approval)  AS change_of_emp_approval,
            SUM(continuation_approval)   AS continuation_approval,
            SUM(amended_approval)        AS amended_approval
        FROM companies c
        GROUP BY normalized_name
        """,
        conn,
    )
    conn.close()
    df["label"] = (df["new_emp_approval"] > 0).astype(int)
    return df


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

_DIGIT_RE = re.compile(r"\d")


def featurize(
    df: pd.DataFrame,
    *,
    top_naics: Optional[list[str]] = None,
    top_states: Optional[list[str]] = None,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Build the feature DataFrame the pipeline expects.

    Returns (frame, top_naics_used, top_states_used) so the same buckets can
    be reused at inference time. The raw uppercased name is kept as a column
    (`name_text`) so TfidfVectorizer can consume it inside the pipeline.
    """
    out = pd.DataFrame(index=df.index)

    naics = df["naics_code"].fillna("").astype(str).str.strip()
    naics = naics.replace("", "UNKNOWN")
    if top_naics is None:
        top_naics = (
            naics[naics != "UNKNOWN"].value_counts().head(TOP_NAICS_K)
            .index.tolist()
        )
    out["naics_bucket"] = np.where(naics.isin(top_naics), naics, "OTHER")

    state = df["state"].fillna("").astype(str).str.strip().str.upper()
    state = state.replace("", "UNKNOWN")
    if top_states is None:
        top_states = state.value_counts().index.tolist()
    out["state_bucket"] = np.where(state.isin(top_states), state, "OTHER")

    name = df["display_name"].fillna("").astype(str).str.upper()
    out["name_text"] = name
    for tok in NAME_TOKEN_FLAGS:
        out[f"tok_{tok.lower()}"] = name.str.contains(tok, regex=False).astype(int)
    out["name_len"] = name.str.len().astype(float)
    out["name_word_count"] = name.str.split().apply(len).astype(float)
    out["name_has_digit"] = name.str.contains(_DIGIT_RE).astype(int)

    return out, top_naics, top_states


def _build_main_pipeline() -> Pipeline:
    """Main classifier: name + NAICS + state -> P(sponsors)."""
    cat_cols = ["naics_bucket", "state_bucket"]
    num_cols = (
        [f"tok_{t.lower()}" for t in NAME_TOKEN_FLAGS]
        + ["name_len", "name_word_count", "name_has_digit"]
    )
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
        ("num", StandardScaler(), num_cols),
        ("char_ng", TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5),
            max_features=2000, sublinear_tf=True, min_df=2,
        ), "name_text"),
    ])
    return Pipeline([
        ("pre", pre),
        ("clf", LogisticRegression(
            max_iter=2000, class_weight="balanced", C=1.0, solver="liblinear",
        )),
    ])


def _build_naics_imputer() -> Pipeline:
    """Multiclass: name -> NAICS bucket. Used when caller has no NAICS."""
    pre = ColumnTransformer([
        ("char_ng", TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5),
            max_features=3000, sublinear_tf=True, min_df=2,
        ), "name_text"),
    ])
    return Pipeline([
        ("pre", pre),
        ("clf", LogisticRegression(
            max_iter=2000, C=1.0, solver="lbfgs", n_jobs=-1,
        )),
    ])


# ---------------------------------------------------------------------------
# Train + evaluate
# ---------------------------------------------------------------------------

def train_and_evaluate(*, db_path: Path = DB_PATH, save: bool = True) -> dict:
    df = load_training_frame(db_path)
    X_raw, top_naics, top_states = featurize(df)
    y = df["label"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X_raw, y, test_size=0.2, stratify=y, random_state=42
    )

    main_pipe = _build_main_pipeline()
    main_pipe.fit(X_train, y_train)

    p_test = main_pipe.predict_proba(X_test)[:, 1]
    yhat_test = (p_test >= 0.5).astype(int)

    # Baseline: NAICS-conditional rate (looked up from train set).
    naics_rate = (
        pd.DataFrame({"naics": X_train["naics_bucket"].values, "y": y_train})
        .groupby("naics")["y"].mean()
    )
    global_rate = float(y_train.mean())
    base_p = (
        X_test["naics_bucket"].map(naics_rate).fillna(global_rate).values
    )
    majority = int(y_train.mean() >= 0.5)
    base_majority = np.full_like(y_test, majority)

    # NAICS imputer: train only on rows where NAICS is genuinely known
    # (label=naics_bucket, but skip rows that fell into the OTHER bucket
    # because they had unknown NAICS to begin with).
    train_known_mask = X_train["naics_bucket"] != "OTHER"
    X_imp_train = X_train[train_known_mask]
    y_imp_train = X_train.loc[train_known_mask, "naics_bucket"].values

    test_known_mask = X_test["naics_bucket"] != "OTHER"
    X_imp_test = X_test[test_known_mask]
    y_imp_test = X_test.loc[test_known_mask, "naics_bucket"].values

    imputer = _build_naics_imputer()
    imputer.fit(X_imp_train, y_imp_train)
    imputer_acc = float(accuracy_score(y_imp_test, imputer.predict(X_imp_test)))

    # End-to-end cold-start AUC: drop NAICS at test time, impute, then score.
    X_test_cold = X_test.copy()
    imputed = imputer.predict(X_test_cold)
    X_test_cold["naics_bucket"] = imputed
    p_test_cold = main_pipe.predict_proba(X_test_cold)[:, 1]

    metrics = {
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "label_rate_train": float(y_train.mean()),
        "lr_with_naics": {
            "auc": float(roc_auc_score(y_test, p_test)),
            "ap": float(average_precision_score(y_test, p_test)),
            "brier": float(brier_score_loss(y_test, p_test)),
            "acc@0.5": float(accuracy_score(y_test, yhat_test)),
        },
        "lr_cold_start": {
            "auc": float(roc_auc_score(y_test, p_test_cold)),
            "ap": float(average_precision_score(y_test, p_test_cold)),
            "brier": float(brier_score_loss(y_test, p_test_cold)),
        },
        "naics_imputer": {
            "acc": imputer_acc,
            "n_classes": int(len(set(y_imp_train))),
        },
        "baseline_majority": {
            "acc": float(accuracy_score(y_test, base_majority)),
        },
        "baseline_naics_rate": {
            "auc": float(roc_auc_score(y_test, base_p)),
            "ap": float(average_precision_score(y_test, base_p)),
            "brier": float(brier_score_loss(y_test, base_p)),
        },
    }

    if save:
        joblib.dump(
            {
                "pipeline": main_pipe,
                "naics_imputer": imputer,
                "top_naics": top_naics,
                "top_states": top_states,
                "label_rate": float(y.mean()),
            },
            MODEL_PATH,
        )

    print("=" * 72)
    print(f"Trained on {metrics['n_train']:,} companies, "
          f"tested on {metrics['n_test']:,}")
    print(f"Positive (sponsors) rate: {metrics['label_rate_train']:.3f}")
    print()
    print(f"  LR (with NAICS)     AUC={metrics['lr_with_naics']['auc']:.3f}   "
          f"AP={metrics['lr_with_naics']['ap']:.3f}   "
          f"Brier={metrics['lr_with_naics']['brier']:.3f}   "
          f"Acc@.5={metrics['lr_with_naics']['acc@0.5']:.3f}")
    print(f"  LR (cold start)     AUC={metrics['lr_cold_start']['auc']:.3f}   "
          f"AP={metrics['lr_cold_start']['ap']:.3f}   "
          f"Brier={metrics['lr_cold_start']['brier']:.3f}")
    print(f"  NAICS-rate baseline AUC={metrics['baseline_naics_rate']['auc']:.3f}   "
          f"AP={metrics['baseline_naics_rate']['ap']:.3f}   "
          f"Brier={metrics['baseline_naics_rate']['brier']:.3f}")
    print(f"  Majority-class      Acc={metrics['baseline_majority']['acc']:.3f}")
    print()
    print(f"  NAICS imputer       Acc={metrics['naics_imputer']['acc']:.3f} "
          f"({metrics['naics_imputer']['n_classes']} classes)")
    print()
    print("Classification report (main LR with-NAICS @ 0.5):")
    print(classification_report(y_test, yhat_test, digits=3))
    if save:
        print(f"Saved bundle -> {MODEL_PATH}")
    return metrics


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def impute_naics_from_text(text: str) -> Optional[tuple[str, int, list[str]]]:
    """Return (naics_code, hit_count, matched_phrases) for the best-scoring
    sector, or None if no sector accumulates >= NAICS_DICT_MIN_HITS.

    Case-insensitive substring count. Multi-word phrases are scored 1 hit
    each, regardless of how many times they appear, so a JD that just says
    "software engineer" five times doesn't run away with the verdict.
    """
    if not text:
        return None
    haystack = text.lower()
    best_code: Optional[str] = None
    best_count = 0
    best_matches: list[str] = []
    for code, phrases in NAICS_KEYWORDS.items():
        matched = [p for p in phrases if p in haystack]
        if len(matched) > best_count:
            best_count = len(matched)
            best_code = code
            best_matches = matched
    if best_code is None or best_count < NAICS_DICT_MIN_HITS:
        return None
    return best_code, best_count, best_matches


_BUNDLE_CACHE: Optional[dict] = None


def _load_bundle() -> dict:
    global _BUNDLE_CACHE
    if _BUNDLE_CACHE is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"{MODEL_PATH} not found. Run "
                "`python sponsorship_model.py --train` first."
            )
        _BUNDLE_CACHE = joblib.load(MODEL_PATH)
    return _BUNDLE_CACHE


def _resolve_naics(
    bundle: dict,
    feats: pd.DataFrame,
    *,
    naics_provided: bool,
    description: Optional[str],
    title: Optional[str],
) -> tuple[str, str]:
    """Decide the NAICS bucket to feed the main LR.

    Priority:
      1. Caller passed `naics` -> already in feats. ``source = "provided"``.
      2. JD/title hits the keyword dictionary -> use that. ``source = "jd_dict"``.
      3. Name-based ML imputer.                  ``source = "name_imputed"``.
      4. None of the above -> stays "OTHER".     ``source = "default"``.
    """
    current = str(feats.loc[0, "naics_bucket"])
    if naics_provided and current != "OTHER":
        return current, "provided"

    text = " ".join(filter(None, [title, description])).strip()
    if text:
        hit = impute_naics_from_text(text)
        if hit is not None:
            code, _, _ = hit
            # Only use it if our trained model has seen this NAICS bucket.
            if code in bundle["top_naics"]:
                feats.loc[0, "naics_bucket"] = code
                return code, "jd_dict"

    imputer = bundle.get("naics_imputer")
    if imputer is not None:
        predicted = imputer.predict(feats)[0]
        feats.loc[0, "naics_bucket"] = predicted
        return str(predicted), "name_imputed"

    return current, "default"


def predict_sponsorship_probability(
    name: str,
    naics: Optional[str] = None,
    state: Optional[str] = None,
    description: Optional[str] = None,
    title: Optional[str] = None,
) -> float:
    """Return P(this company sponsors at least one new H-1B hire).

    Only `name` is required. NAICS resolution order:
      1. explicit `naics` arg
      2. JD/title keyword dictionary
      3. name-based ML imputer
    Missing state falls through to the "UNKNOWN" bucket.
    """
    bundle = _load_bundle()
    if not name or not name.strip():
        return float(bundle["label_rate"])

    raw = pd.DataFrame([{
        "display_name": name.strip(),
        "naics_code": (naics or "").strip(),
        "state": (state or "").strip().upper(),
    }])
    feats, _, _ = featurize(
        raw, top_naics=bundle["top_naics"], top_states=bundle["top_states"]
    )
    _resolve_naics(
        bundle, feats,
        naics_provided=bool((naics or "").strip()),
        description=description, title=title,
    )
    p = bundle["pipeline"].predict_proba(feats)[0, 1]
    return float(p)


def predict_with_details(
    name: str,
    naics: Optional[str] = None,
    state: Optional[str] = None,
    description: Optional[str] = None,
    title: Optional[str] = None,
) -> dict:
    """Same as predict_sponsorship_probability but exposes the resolution
    path -- useful for debugging and the CLI / Flask response."""
    bundle = _load_bundle()
    if not name or not name.strip():
        return {
            "p_sponsors": float(bundle["label_rate"]),
            "naics_used": None, "state_used": None,
            "naics_source": "uninformative_prior",
            "naics_evidence": [],
        }

    raw = pd.DataFrame([{
        "display_name": name.strip(),
        "naics_code": (naics or "").strip(),
        "state": (state or "").strip().upper(),
    }])
    feats, _, _ = featurize(
        raw, top_naics=bundle["top_naics"], top_states=bundle["top_states"]
    )
    code, source = _resolve_naics(
        bundle, feats,
        naics_provided=bool((naics or "").strip()),
        description=description, title=title,
    )
    # If we used the dictionary, surface which phrases fired (for the demo).
    evidence: list[str] = []
    if source == "jd_dict":
        text = " ".join(filter(None, [title, description])).strip()
        hit = impute_naics_from_text(text)
        if hit is not None:
            _, _, evidence = hit

    p = bundle["pipeline"].predict_proba(feats)[0, 1]
    return {
        "p_sponsors": float(p),
        "naics_used": code,
        "state_used": str(feats.loc[0, "state_bucket"]),
        "naics_source": source,
        "naics_evidence": evidence,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

DEMO_QUERIES = [
    ("Stripe", "52", "CA"),
    ("Google", "54", "CA"),
    ("Acme Random Holdings", None, None),
    ("Smith Family Diner", "72", "OH"),
    ("Quantum AI Labs", "54", "MA"),
    ("Joe's Plumbing LLC", "23", "TX"),
]


def _cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Train and run the cold-start sponsorship predictor."
    )
    parser.add_argument("--train", action="store_true", help="Train + save the model.")
    parser.add_argument("name", nargs="?", help="Company name to score.")
    parser.add_argument("--naics", default=None)
    parser.add_argument("--state", default=None)
    parser.add_argument("--jd", "--description", dest="jd", default=None,
                        help="Job description text (used for NAICS imputation).")
    parser.add_argument("--title", default=None,
                        help="Job title (used for NAICS imputation).")
    args = parser.parse_args(argv[1:])

    if args.train:
        train_and_evaluate(save=True)
        return 0

    if args.name:
        d = predict_with_details(
            args.name, args.naics, args.state,
            description=args.jd, title=args.title,
        )
        evidence = (
            f"  via [{', '.join(d['naics_evidence'])}]"
            if d["naics_evidence"] else ""
        )
        print(
            f"{args.name!r:40s}  P(sponsors)={d['p_sponsors']:.3f}   "
            f"NAICS={d['naics_used']} ({d['naics_source']}){evidence}   "
            f"state={d['state_used']}"
        )
        return 0

    # No args: run the demo bundle (requires a saved model).
    if not MODEL_PATH.exists():
        print("No model on disk yet. Training now...\n")
        train_and_evaluate(save=True)
        print()
    print("Demo predictions:")
    for q, naics, state in DEMO_QUERIES:
        d = predict_with_details(q, naics, state)
        print(
            f"  {q!r:32s} naics={d['naics_used']:<7} ({d['naics_source']:<13}) "
            f"state={d['state_used']:<8}  P(sponsors)={d['p_sponsors']:.3f}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))
