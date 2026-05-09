"""Cold-start sponsorship predictor for VisaRank.

Trains a logistic regression to predict P(company sponsors a new H-1B hire)
from features that are available even when the company is NOT in our USCIS
database — i.e. things we can compute from a LinkedIn posting alone:

    - NAICS industry code (when known; "other" bucket otherwise)
    - Petitioner state (proxy for posting location at training time)
    - Name token features (substring flags for "TECHNOLOGIES", "CONSULTING",
      "SOFTWARE", "SOLUTIONS", etc.)
    - Name shape: length, has-digit, all-caps

The label is a non-leaky binary: ``new_emp_approval > 0`` for the company.
USCIS-derived counts (continuations, totals, etc.) are deliberately NOT used
as features — that's what kept the previous LR sketch circular.

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
    be reused at inference time.
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
    for tok in NAME_TOKEN_FLAGS:
        out[f"tok_{tok.lower()}"] = name.str.contains(tok, regex=False).astype(int)
    out["name_len"] = name.str.len().astype(float)
    out["name_word_count"] = name.str.split().apply(len).astype(float)
    out["name_has_digit"] = name.str.contains(_DIGIT_RE).astype(int)

    return out, top_naics, top_states


def _build_pipeline() -> Pipeline:
    cat_cols = ["naics_bucket", "state_bucket"]
    num_cols = (
        [f"tok_{t.lower()}" for t in NAME_TOKEN_FLAGS]
        + ["name_len", "name_word_count", "name_has_digit"]
    )
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
        ("num", StandardScaler(), num_cols),
    ])
    return Pipeline([
        ("pre", pre),
        ("clf", LogisticRegression(
            max_iter=1000, class_weight="balanced", C=1.0, solver="liblinear",
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

    pipe = _build_pipeline()
    pipe.fit(X_train, y_train)

    p_test = pipe.predict_proba(X_test)[:, 1]
    yhat_test = (p_test >= 0.5).astype(int)

    # Baseline 1: majority class
    majority = int(y_train.mean() >= 0.5)
    base1_pred = np.full_like(y_test, majority)
    # Baseline 2: NAICS-conditional rate (looked up from train set)
    naics_rate = (
        pd.DataFrame({"naics": X_train["naics_bucket"].values, "y": y_train})
        .groupby("naics")["y"].mean()
    )
    global_rate = float(y_train.mean())
    base2_p = (
        X_test["naics_bucket"].map(naics_rate).fillna(global_rate).values
    )

    metrics = {
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "label_rate_train": float(y_train.mean()),
        "lr": {
            "auc": float(roc_auc_score(y_test, p_test)),
            "ap": float(average_precision_score(y_test, p_test)),
            "brier": float(brier_score_loss(y_test, p_test)),
            "acc@0.5": float(accuracy_score(y_test, yhat_test)),
        },
        "baseline_majority": {
            "acc": float(accuracy_score(y_test, base1_pred)),
        },
        "baseline_naics_rate": {
            "auc": float(roc_auc_score(y_test, base2_p)),
            "ap": float(average_precision_score(y_test, base2_p)),
            "brier": float(brier_score_loss(y_test, base2_p)),
        },
    }

    if save:
        joblib.dump(
            {
                "pipeline": pipe,
                "top_naics": top_naics,
                "top_states": top_states,
                "label_rate": float(y.mean()),
            },
            MODEL_PATH,
        )

    print("=" * 64)
    print(f"Trained on {metrics['n_train']:,} companies, "
          f"tested on {metrics['n_test']:,}")
    print(f"Positive (sponsors) rate: {metrics['label_rate_train']:.3f}")
    print()
    print(f"  LR              AUC={metrics['lr']['auc']:.3f}   "
          f"AP={metrics['lr']['ap']:.3f}   "
          f"Brier={metrics['lr']['brier']:.3f}   "
          f"Acc@.5={metrics['lr']['acc@0.5']:.3f}")
    print(f"  NAICS-rate      AUC={metrics['baseline_naics_rate']['auc']:.3f}   "
          f"AP={metrics['baseline_naics_rate']['ap']:.3f}   "
          f"Brier={metrics['baseline_naics_rate']['brier']:.3f}")
    print(f"  Majority-class  Acc={metrics['baseline_majority']['acc']:.3f}")
    print()
    print("Classification report (LR @ 0.5):")
    print(classification_report(y_test, yhat_test, digits=3))
    if save:
        print(f"Saved model -> {MODEL_PATH}")
    return metrics


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

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


def predict_sponsorship_probability(
    name: str,
    naics: Optional[str] = None,
    state: Optional[str] = None,
) -> float:
    """Return P(this company sponsors at least one new H-1B hire).

    All non-name fields are optional. Missing values fall through to the
    "OTHER" / "UNKNOWN" buckets the model was trained against.
    """
    bundle = _load_bundle()
    if not name or not name.strip():
        return float(bundle["label_rate"])  # uninformative prior

    raw = pd.DataFrame([{
        "display_name": name.strip(),
        "naics_code": (naics or "").strip(),
        "state": (state or "").strip().upper(),
    }])
    feats, _, _ = featurize(
        raw, top_naics=bundle["top_naics"], top_states=bundle["top_states"]
    )
    p = bundle["pipeline"].predict_proba(feats)[0, 1]
    return float(p)


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
    args = parser.parse_args(argv[1:])

    if args.train:
        train_and_evaluate(save=True)
        return 0

    if args.name:
        p = predict_sponsorship_probability(args.name, args.naics, args.state)
        print(f"{args.name!r:40s}  P(sponsors) = {p:.3f}")
        return 0

    # No args: run the demo bundle (requires a saved model).
    if not MODEL_PATH.exists():
        print("No model on disk yet. Training now...\n")
        train_and_evaluate(save=True)
        print()
    print("Demo predictions:")
    for q, naics, state in DEMO_QUERIES:
        p = predict_sponsorship_probability(q, naics, state)
        ctx = f"naics={naics!s:<6} state={state!s:<3}"
        print(f"  {q!r:32s} {ctx}  P(sponsors)={p:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))
