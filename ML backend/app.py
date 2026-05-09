"""Flask HTTP server for VisaRank.

Thin glue layer over sponsorship.score_with_cold_start. Accepts the
extension's JobInfo / VisaFitRequest payload, runs the full pipeline
(USCIS lookup -> cold-start LR -> posting kill-switch), and returns the
extension's CompanyAnalysis shape.

Endpoints:
    GET  /api/health    -> {ok, db_rows, model_loaded, schema_version}
    POST /api/analyze   -> {jobInfo, analysis}

Run:
    cd "ML backend" && python app.py
    # serves http://localhost:8000
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request
from flask_cors import CORS

from sponsorship import (
    DB_PATH,
    SCHEMA_VERSION,
    score_with_cold_start,
)

# Lazy: model + posting filter loaded inside score_with_cold_start.
PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_PATH = PROJECT_ROOT / "sponsorship_model.joblib"

# Tier -> sponsorScore (0-100)
TIER_TO_SCORE = {5: 90, 4: 70, 3: 50, 2: 25, 1: 5}
# Tier -> verdict
TIER_TO_VERDICT = {5: "sponsor", 4: "sponsor", 3: "unknown", 2: "unlikely", 1: "unlikely"}

# "San Francisco, CA" -> "CA". Also handles trailing parens like
# "Austin, TX (On-site)" or "Seattle, WA · United States".
_STATE_RE = re.compile(r",\s*([A-Z]{2})\b")


app = Flask(__name__)
CORS(
    app,
    resources={r"/api/*": {"origins": [
        "chrome-extension://*",
        "http://localhost:*",
        "http://127.0.0.1:*",
    ]}},
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_state(location: str) -> Optional[str]:
    if not location:
        return None
    m = _STATE_RE.search(location)
    return m.group(1) if m else None


def _build_h1b_history(features: Optional[dict]) -> list[dict]:
    """Convert features['per_year'] into the extension's H1BRecord list."""
    if not features or not features.get("per_year"):
        return []
    out: list[dict] = []
    for year, counts in sorted(features["per_year"].items()):
        approved = sum(v for k, v in counts.items() if k.endswith("_approval"))
        denied = sum(v for k, v in counts.items() if k.endswith("_denial"))
        out.append({
            "year": int(year),
            "approved": int(approved),
            "denied": int(denied),
            "initialApprovals": int(counts.get("new_emp_approval", 0)),
        })
    return out


def _to_company_analysis(verdict: dict, fallback_company: str) -> dict:
    """Map score_with_cold_start output to the extension's CompanyAnalysis."""
    tier = verdict["tier"]
    feats = verdict.get("features")
    matched = feats["matched_name"] if feats else fallback_company

    return {
        "company": matched,
        "sponsorScore": TIER_TO_SCORE[tier],
        "verdict": TIER_TO_VERDICT[tier],
        "h1bHistory": _build_h1b_history(feats),
        "notes": verdict["reason"],
        # Diagnostic fields the extension can ignore but a debug panel can show.
        "tier": tier,
        "source": verdict["source"],
        "matchScore": verdict.get("match_score"),
        "modelProbability": verdict.get("prediction"),
        "postingSignal": verdict.get("posting_signal"),
        "overrideApplied": verdict.get("override_applied", False),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    db_rows = None
    db_ok = False
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("SELECT COUNT(*) FROM companies")
        db_rows = cur.fetchone()[0]
        conn.close()
        db_ok = True
    except Exception:
        pass

    return jsonify({
        "ok": db_ok,
        "db_rows": db_rows,
        "model_loaded": MODEL_PATH.exists(),
        "schema_version": SCHEMA_VERSION,
    })


@app.post("/api/analyze")
def analyze():
    body = request.get_json(silent=True) or {}

    company = (body.get("company") or "").strip()
    if not company:
        return jsonify({"error": "missing required field: company"}), 400

    location = body.get("location") or ""
    description = body.get("description") or ""
    # Accept both `title` (JobInfo) and `role` (VisaFitRequest) for the
    # job-title field. Whichever the extension sent, we use it.
    title = body.get("title") or body.get("role") or ""

    state = _extract_state(location)

    verdict = score_with_cold_start(
        company,
        state=state,
        description=description or None,
        title=title or None,
    )

    analysis = _to_company_analysis(verdict, fallback_company=company)

    # Echo back jobInfo so the extension can store the round-tripped object.
    job_info = {
        "company": company,
        "title": body.get("title") or body.get("role") or "",
        "location": location,
        "isRemote": bool(body.get("isRemote", False)),
        "platform": body.get("platform") or "unknown",
        "url": body.get("url") or "",
        "description": description,
    }

    return jsonify({"jobInfo": job_info, "analysis": analysis})


@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "not found"}), 404


@app.errorhandler(500)
def server_error(_):
    return jsonify({"error": "internal server error"}), 500


if __name__ == "__main__":
    # debug=False so we don't reload the model on every code change in
    # this directory; toggle to True if you want autoreload.
    app.run(host="127.0.0.1", port=8000, debug=False)
