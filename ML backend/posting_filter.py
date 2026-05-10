"""Regex-based posting filter for VisaRank.

Reads a job posting (title + description) and returns a 5-bucket signal
about whether the posting itself is open to H-1B sponsorship — independent
of the company-level USCIS history.

Categories, in priority order at decision time:
    hard_no   -- explicit kill switch ("must have permanent work auth",
                 "US citizens only", ITAR, active security clearance)
    hard_yes  -- explicit invitation ("we sponsor H-1B", "visa sponsorship
                 available")
    soft_no   -- hedged negative ("unable to sponsor at this time")
    soft_yes  -- hedged positive ("will consider sponsoring qualified
                 candidates")
    neutral   -- no mention either way (the most common case)

Combine rules (applied by the Flask layer, NOT here):
    hard_no  -> override company tier to 1
    hard_yes -> +1 tier
    soft_no  -> -1 tier
    soft_yes -> no change (but surface evidence to the user)
    neutral  -> no change

This module is intentionally pure-regex. The phrasings the kill-switch
patterns match are legal boilerplate that companies copy near-verbatim, so
regex catches the bulk of real cases. The LLM-based fallback we discussed
is deliberately NOT shipped here — fewer moving parts for the demo.

Public API:
    analyze_posting(title="", description="") -> dict
        {category: str, evidence: list[str], all_matches: dict}

CLI:
    python posting_filter.py "<paste posting text here>"
    cat posting.txt | python posting_filter.py
"""

from __future__ import annotations

import json
import re
import sys
from typing import Optional

CATEGORIES = ("hard_no", "soft_no", "neutral", "soft_yes", "hard_yes")

# ---------------------------------------------------------------------------
# Pattern set. Each entry is (label, compiled_regex). The label is a short
# slug for debugging / tracing — it shows up in `all_matches`. Patterns are
# all case-insensitive and assume whitespace has been collapsed to single
# spaces by `_normalize`.
# ---------------------------------------------------------------------------

_F = re.IGNORECASE


def _rx(p: str) -> re.Pattern:
    return re.compile(p, _F)


HARD_NO_PATTERNS: list[tuple[str, re.Pattern]] = [
    # "Must be authorized to work in the US without sponsorship now or in the future"
    ("auth_without_sponsor", _rx(
        r"must\s+(?:be\s+(?:able\s+to\s+be\s+)?|have\s+|possess\s+|maintain\s+|currently\s+have\s+)?"
        r"(?:legally\s+|currently\s+)?(?:be\s+)?(?:authorized|eligible)\s+to\s+work"
        r"(?:\s+in\s+the\s+(?:us|united\s+states))?"
        r"\s+(?:without|with\s+no|with\s+out)\s+"
        r"(?:current\s+or\s+future\s+|the\s+)?(?:need\s+(?:of|for)\s+)?"
        r"(?:visa\s+|employer\s+|h-?1b\s+|company\s+|future\s+)?sponsor"
    )),
    # "Must possess permanent / unrestricted / legal work authorization"
    ("permanent_work_auth", _rx(
        r"must\s+(?:have|possess|hold|maintain)\s+"
        r"(?:permanent|unrestricted|valid\s+and\s+unrestricted|long[- ]term|"
        r"current\s+and\s+permanent|indefinite|long\s+term)\s+"
        r"(?:us\s+)?(?:work\s+)?authoriz\w+"
    )),
    # "...without requiring sponsorship now or in the future"
    # Also catches "without a need for current or future visa sponsorship" (IBM phrasing)
    ("without_sponsor_clause", _rx(
        r"\b(?:without|with\s+no|with\s+out)\s+(?:requiring|needing|(?:a|the)\s+need\s+for)?\s*"
        r"(?:current\s+or\s+future\s+)?(?:visa\s+|h-?1b\s+|employer\s+|company\s+)?sponsorship"
        r"(?:\s+(?:now\s+or\s+in\s+the\s+future|at\s+any\s+time|ever))?"
    )),
    # "must have the ability to work without [a need for] sponsorship" (IBM / Avature phrasing)
    ("ability_to_work_without_sponsor", _rx(
        r"\bmust\s+have\s+(?:the\s+)?ability\s+to\s+work\s+"
        r"(?:in\s+the\s+(?:us|united\s+states)\s+)?"
        r"without\s+(?:(?:a|the)\s+need\s+for\s+)?(?:current\s+or\s+future\s+)?"
        r"(?:visa\s+|h-?1b\s+|employer\s+)?sponsor"
    )),
    # "No sponsorship available" / "We do not sponsor" / "will not be providing visa sponsorship"
    ("no_sponsorship_explicit", _rx(
        r"\b(?:no|not\s+able\s+to|unable\s+to|cannot|can\s+not|will\s+not|do\s+not|"
        r"does\s+not|we\s+do\s+not|we\s+will\s+not|we\s+cannot)\s+"
        r"(?:be\s+)?"                                             # handles "will not BE providing"
        r"(?:offer(?:ing)?\s+|provide\s+|providing\s+|currently\s+offer\s+|currently\s+provide\s+)?"
        r"(?:visa\s+|h-?1b\s+|employer\s+|work\s+)?sponsor(?:ship|\b)"
    )),
    ("sponsorship_not_available", _rx(
        r"\bsponsorship\s+is\s+not\s+(?:available|offered|provided|supported|"
        r"considered|an\s+option)\b"
    )),
    ("position_not_eligible", _rx(
        r"\bthis\s+(?:position|role|posting|opportunity|opening)\s+"
        r"(?:does\s+not\s+|is\s+not\s+(?:eligible\s+for\s+|able\s+to\s+))"
        r"(?:offer|provide|qualify\s+for|support)\s+"
        r"(?:visa\s+|h-?1b\s+|employer\s+)?sponsor"
    )),
    # US citizens only / must be US citizen
    ("us_citizen_required", _rx(
        r"\b(?:must\s+be\s+(?:a\s+)?|requires?\s+(?:a\s+)?)us\s+citizen"
        r"(?:s|ship)?(?:\s+or\s+permanent\s+resident)?\b"
    )),
    ("us_citizens_only", _rx(
        r"\bus\s+citizens?\s+only\b"
    )),
    ("citizenship_required", _rx(
        r"\b(?:us\s+)?citizenship\s+(?:is\s+|will\s+be\s+)?required\b"
    )),
    # Subject-verb-object form: "this role requires US citizenship"
    ("position_requires_citizenship", _rx(
        r"\b(?:positions?|roles?|this\s+(?:job|opening|opportunity))\s+"
        r"requires?\s+(?:us\s+)?(?:citizenship|us\s+citizens?)\b"
    )),
    # ITAR / export controlled / US person
    ("itar", _rx(r"\bitar(?:\s+regulations?)?\b")),
    ("export_controlled", _rx(
        r"\bexport[- ]controlled\b|"
        r"\bexport\s+control(?:\s+(?:laws?|regulations?|compliance|requirements?))?\b"
    )),
    ("us_person_required", _rx(
        r"\bus\s+person(?:s)?\s+(?:status\s+)?(?:only|required|status\s+is\s+required)\b"
    )),
    # Security clearance — effectively citizen-only by extension
    ("active_clearance", _rx(
        r"\b(?:active|current|existing)\s+(?:us\s+)?(?:government\s+)?"
        r"(?:secret|top\s+secret|confidential|security|ts[/ ]sci)?\s*"
        r"clearance\b"
    )),
    ("must_possess_clearance", _rx(
        r"\bmust\s+(?:possess|have|hold|maintain)\s+(?:and\s+\w+\s+)?"
        r"(?:a\s+)?(?:current\s+|active\s+|valid\s+)?"
        r"(?:us\s+)?(?:secret|top\s+secret|confidential|security|ts[/ ]sci)\s+"
        r"clearance\b"
    )),
    ("ts_sci", _rx(r"\bts\s*[/\\]\s*sci\b|\btop\s+secret(?:[/\\]\s*sci)?\b")),
    ("clearance_required", _rx(
        r"\b(?:secret|top\s+secret|confidential|security)\s+clearance\s+"
        r"(?:is\s+)?(?:required|needed|mandatory|to\s+(?:obtain|maintain))\b"
    )),
    # "to obtain a security clearance" implies citizenship requirement
    ("clearance_requires_citizenship", _rx(
        r"\bto\s+obtain\s+(?:and\s+\w+\s+)?(?:a\s+)?"
        r"(?:secret|top\s+secret|confidential|security)\s+clearance\b"
    )),
]

HARD_YES_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("h1b_sponsorship_available", _rx(
        r"\bh-?1b\s+sponsorship\s+(?:is\s+)?(?:available|offered|provided|supported)\b"
    )),
    ("visa_sponsorship_available", _rx(
        r"\bvisa\s+sponsorship\s+(?:is\s+)?(?:available|offered|provided|supported)\b"
    )),
    ("we_sponsor_visas", _rx(
        r"\bwe\s+(?:will\s+|do\s+|currently\s+)?sponsor\s+(?:visas?|h-?1b)"
    )),
    ("sponsorship_available", _rx(
        r"\bsponsorship\s+is\s+available\b"
    )),
    ("happy_to_sponsor", _rx(
        r"\b(?:happy|willing|able)\s+to\s+sponsor\b"
    )),
]

SOFT_NO_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("unable_at_this_time", _rx(
        r"\b(?:unable|not\s+able)\s+to\s+(?:provide\s+|offer\s+)?"
        r"(?:visa\s+|h-?1b\s+)?sponsorship\s+"
        r"(?:at\s+this\s+time|currently|right\s+now|for\s+this\s+role)\b"
    )),
    ("not_considering_sponsorship", _rx(
        r"\bnot\s+(?:currently\s+)?(?:considering|accepting|offering)\s+"
        r"(?:visa\s+|h-?1b\s+)?sponsorship\b"
    )),
    ("sponsorship_not_for_this_role", _rx(
        r"\bsponsorship\s+(?:is\s+)?not\s+(?:available|offered)\s+"
        r"(?:for\s+this\s+(?:role|position)|at\s+this\s+time)\b"
    )),
]

SOFT_YES_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("will_consider", _rx(
        r"\b(?:may|might|will|could|would)\s+consider\s+"
        r"(?:visa\s+|h-?1b\s+|employer\s+)?sponsor"
    )),
    ("open_to_sponsoring", _rx(
        r"\bopen\s+to\s+(?:visa\s+|h-?1b\s+)?sponsor(?:ing|ship)?\b"
    )),
    ("sponsor_for_qualified", _rx(
        r"\b(?:would|will|may|happy\s+to)\s+sponsor\s+(?:for\s+)?"
        r"(?:exceptional|qualified|the\s+right|outstanding|strong)\s+candidates?\b"
    )),
    ("case_by_case", _rx(
        r"\b(?:visa\s+|h-?1b\s+)?sponsorship\s+"
        r"(?:will\s+be\s+|is\s+)?(?:considered|evaluated)\s+"
        r"(?:on\s+a\s+)?case[- ]by[- ]case\b"
    )),
]


# ---------------------------------------------------------------------------
# Soft veto: phrasings that LOOK like a hard_no but are actually neutral or
# softer. Applied AFTER the initial scan to demote false positives.
# Most common in practice: "Citizenship preferred but not required."
# ---------------------------------------------------------------------------

_PREFERENCE_VETO = _rx(
    r"\b(?:preferred|a\s+plus|nice\s+to\s+have)(?:\s+but\s+not\s+required)?\b"
)


def _has_preference_veto_near(text: str, span: tuple[int, int]) -> bool:
    """True if 'preferred' / 'a plus' / 'not required' appears within
    60 chars of the matched span — flips a hard_no to neutral."""
    start, end = span
    window = text[max(0, start - 60): end + 60]
    return bool(_PREFERENCE_VETO.search(window))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """Collapse whitespace so multi-line postings match single-line patterns."""
    return _WS_RE.sub(" ", (text or "")).strip()


def _scan(
    text: str,
    patterns: list[tuple[str, re.Pattern]],
    *,
    apply_preference_veto: bool = False,
) -> list[dict]:
    """Find first match per pattern. Returns a list of {label, snippet, span}."""
    found: list[dict] = []
    for label, pat in patterns:
        m = pat.search(text)
        if not m:
            continue
        if apply_preference_veto and _has_preference_veto_near(text, m.span()):
            continue
        start, end = m.span()
        ctx_start = max(0, start - 30)
        ctx_end = min(len(text), end + 30)
        snippet = text[ctx_start:ctx_end].strip()
        # Add ellipses to make it obvious the snippet is a window, not a quote.
        if ctx_start > 0:
            snippet = "…" + snippet
        if ctx_end < len(text):
            snippet = snippet + "…"
        found.append({"label": label, "snippet": snippet})
    return found


def analyze_posting(title: str = "", description: str = "") -> dict:
    """Classify a posting's sponsorship language.

    Inputs are concatenated (title first, then description) so the regex
    pass sees both. Order of decision is hard_no > hard_yes > soft_no >
    soft_yes > neutral; if multiple categories fire, the highest-priority
    one wins but ALL matches are surfaced in `all_matches` for debugging.
    """
    text = _normalize(f"{title or ''}\n{description or ''}")

    matches = {
        "hard_no":   _scan(text, HARD_NO_PATTERNS, apply_preference_veto=True),
        "hard_yes":  _scan(text, HARD_YES_PATTERNS),
        "soft_no":   _scan(text, SOFT_NO_PATTERNS),
        "soft_yes":  _scan(text, SOFT_YES_PATTERNS),
    }

    if matches["hard_no"]:
        category = "hard_no"
        evidence = [m["snippet"] for m in matches["hard_no"]]
    elif matches["hard_yes"]:
        category = "hard_yes"
        evidence = [m["snippet"] for m in matches["hard_yes"]]
    elif matches["soft_no"]:
        category = "soft_no"
        evidence = [m["snippet"] for m in matches["soft_no"]]
    elif matches["soft_yes"]:
        category = "soft_yes"
        evidence = [m["snippet"] for m in matches["soft_yes"]]
    else:
        category = "neutral"
        evidence = []

    return {
        "category": category,
        "evidence": evidence,
        "all_matches": matches,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_DEMO_POSTINGS: list[tuple[str, str]] = [
    (
        "Software Engineer (US Citizens Only — ITAR)",
        "We're hiring a software engineer to work on export-controlled "
        "systems. Active TS/SCI clearance required. Must be a US citizen.",
    ),
    (
        "Backend Engineer",
        "We are looking for a backend engineer with strong distributed-"
        "systems experience. Must be authorized to work in the United "
        "States without the need for current or future sponsorship.",
    ),
    (
        "Frontend Engineer",
        "Build delightful user experiences with our product team. "
        "We sponsor H-1B visas for qualified candidates and have a "
        "strong track record of supporting international hires.",
    ),
    (
        "Data Scientist",
        "Join our growing analytics team. Visa sponsorship will be "
        "considered on a case-by-case basis for exceptional candidates.",
    ),
    (
        "Senior Engineer",
        "Looking for senior engineers to drive our platform. "
        "Competitive salary and benefits. Remote-friendly.",
    ),
    (
        "Compliance Analyst",
        "Risk and compliance role. Citizenship preferred but not required. "
        "Strong attention to detail expected.",
    ),
]


def _format(query_label: str, result: dict) -> str:
    lines = [f"\n[{result['category'].upper():>9}]  {query_label}"]
    if result["evidence"]:
        for e in result["evidence"]:
            lines.append(f"    evidence: {e}")
    else:
        lines.append("    (no sponsorship-related language detected)")
    return "\n".join(lines)


def _cli(argv: list[str]) -> int:
    if len(argv) > 1 and argv[1] in ("--demo", "-d"):
        for title, desc in _DEMO_POSTINGS:
            r = analyze_posting(title, desc)
            print(_format(title, r))
        return 0

    if len(argv) > 1:
        text = " ".join(argv[1:])
    else:
        text = sys.stdin.read()

    result = analyze_posting(description=text)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))
