from __future__ import annotations

import json
from datetime import date

from app.models.opportunity import Opportunity
from app.services.ai_service import ai_service
from app.services.source_service import load_scoring_rules


POSITIVE_SKILLS = [
    "cyber",
    "cybersecurity",
    "security",
    "security software",
    "cloud-based protection",
    "attack surface",
    "vulnerability",
    "nist",
    "cmmc",
    "policy",
    "awareness",
    "risk",
    "grc",
    "compliance",
    "assessment",
    "information technology",
]

NEGATIVE_TERMS = [
    "24/7",
    "soc monitoring",
    "managed services",
    "staffing",
    "multi-year",
    "enterprise-wide",
    "team of",
    "federal",
    "statewide",
    "construction",
    "renovation",
    "property improvements",
    "facility",
    "fence",
    "commodity",
    "maintenance",
    "supplies",
    "hardware",
    "installation",
]

DEFAULT_SCORING_RULES = {
    "weights": {
        "skill_match": 0.25,
        "solo_fit": 0.25,
        "revenue_fit": 0.20,
        "local_fit": 0.30,
    },
    "penalties": {
        "complexity_factor": 0.20,
    },
    "hard_penalties": NEGATIVE_TERMS,
    "positive_skills": POSITIVE_SKILLS,
    "recommendation_bands": {
        "pursue_min": 75,
        "watch_min": 55,
    },
    "deadline_rules": {
        "expired": 100,
        "lt_3_days": 90,
        "lt_7_days": 65,
    },
}


def _clip(value: int) -> int:
    return max(0, min(100, value))


def _scoring_rules() -> dict:
    configured = load_scoring_rules()
    return {
        "weights": {**DEFAULT_SCORING_RULES["weights"], **configured.get("weights", {})},
        "penalties": {**DEFAULT_SCORING_RULES["penalties"], **configured.get("penalties", {})},
        "hard_penalties": configured.get("hard_penalties") or DEFAULT_SCORING_RULES["hard_penalties"],
        "positive_skills": configured.get("positive_skills") or DEFAULT_SCORING_RULES["positive_skills"],
        "recommendation_bands": {
            **DEFAULT_SCORING_RULES["recommendation_bands"],
            **configured.get("recommendation_bands", {}),
        },
        "deadline_rules": {
            **DEFAULT_SCORING_RULES["deadline_rules"],
            **configured.get("deadline_rules", {}),
        },
    }


def _recommendation(
    fit_score: int,
    deadline_risk: int,
    complexity_risk: int,
    recommendation_bands: dict,
) -> str:
    if deadline_risk >= 85:
        return "Skip"
    if fit_score >= int(recommendation_bands.get("pursue_min", 75)) and complexity_risk <= 50:
        return "Pursue"
    if fit_score >= int(recommendation_bands.get("watch_min", 55)):
        return "Watch"
    if complexity_risk >= 80:
        return "Skip"
    return "Manual Review"


def score_opportunity(opportunity: Opportunity, profile: dict) -> dict:
    scoring_rules = _scoring_rules()
    positive_skills = scoring_rules["positive_skills"]
    negative_terms = scoring_rules["hard_penalties"]
    weights = scoring_rules["weights"]
    penalties = scoring_rules["penalties"]
    recommendation_bands = scoring_rules["recommendation_bands"]
    deadline_rules = scoring_rules["deadline_rules"]
    text = " ".join(
        part
        for part in [
            opportunity.title,
            opportunity.agency,
            opportunity.source_name,
            opportunity.description_snippet or "",
        ]
        if part
    ).lower()

    local_fit = 85 if "maryland" in text or "county" in text or "municipal" in text else 60
    skill_hits = sum(1 for kw in positive_skills if kw.lower() in text)
    skill_match = _clip(35 + skill_hits * 10)

    negative_hits = sum(1 for kw in negative_terms if kw.lower() in text)
    complexity_risk = _clip(20 + negative_hits * 18)
    solo_fit = _clip(85 - negative_hits * 20)

    revenue_fit = 70
    if any(symbol in text for symbol in ["$2,000", "$5,000", "$10,000", "$25,000"]):
        revenue_fit = 90
    if "$100,000" in text or "$250,000" in text or "$1,000,000" in text:
        revenue_fit = 25

    deadline_risk = 30
    if opportunity.due_date:
        days = (opportunity.due_date - date.today()).days
        if days < 0:
            deadline_risk = int(deadline_rules.get("expired", 100))
        elif days < 3:
            deadline_risk = int(deadline_rules.get("lt_3_days", 90))
        elif days < 7:
            deadline_risk = int(deadline_rules.get("lt_7_days", 65))

    fit_score = _clip(
        int(
            (skill_match * float(weights.get("skill_match", 0.25)))
            + (solo_fit * float(weights.get("solo_fit", 0.25)))
            + (revenue_fit * float(weights.get("revenue_fit", 0.2)))
            + (local_fit * float(weights.get("local_fit", 0.3)))
        )
        - int(complexity_risk * float(penalties.get("complexity_factor", 0.2)))
    )

    past_performance_risk = "Medium"
    if "past performance" in text and "3 years" in text:
        past_performance_risk = "High"
    if "small business" in text or "consulting" in text:
        past_performance_risk = "Low"

    recommendation = _recommendation(
        fit_score,
        deadline_risk,
        complexity_risk,
        recommendation_bands,
    )
    reasoning = (
        "Strong local-cyber alignment for a solo consultant."
        if recommendation == "Pursue"
        else "Needs manual validation due to risk or unclear scope."
    )
    next_steps = [
        "Open original posting and confirm scope/deliverables.",
        "Check due date and submission mechanism.",
        "Draft one-page capability statement aligned to the requirements.",
    ]

    ai_payload = ai_service.score_text(
        "Return strict JSON with keys fit_score, skill_match, solo_fit, revenue_fit, "
        "local_fit, deadline_risk, complexity_risk, past_performance_risk, recommendation, "
        "reasoning, next_steps based on this opportunity and profile. "
        f"Opportunity: {opportunity.title} | Agency: {opportunity.agency} | "
        f"Source: {opportunity.source_name} | Description: {opportunity.description_snippet or ''}. "
        f"Profile: {json.dumps(profile)}"
    )
    if ai_payload:
        try:
            ai_payload["fit_score"] = _clip(int(ai_payload.get("fit_score", fit_score)))
            return ai_payload
        except Exception:
            pass

    return {
        "fit_score": fit_score,
        "skill_match": skill_match,
        "solo_fit": solo_fit,
        "revenue_fit": revenue_fit,
        "local_fit": local_fit,
        "deadline_risk": deadline_risk,
        "complexity_risk": complexity_risk,
        "past_performance_risk": past_performance_risk,
        "recommendation": recommendation,
        "reasoning": reasoning,
        "next_steps": next_steps,
    }
