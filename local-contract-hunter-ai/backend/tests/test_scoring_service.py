from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.opportunity import Opportunity
from app.services import scoring_service


EXPECTED_SCORE_KEYS = {
    "fit_score",
    "skill_match",
    "solo_fit",
    "revenue_fit",
    "local_fit",
    "deadline_risk",
    "complexity_risk",
    "past_performance_risk",
    "recommendation",
    "reasoning",
    "next_steps",
}


def opportunity(
    *,
    title: str,
    agency: str,
    description_snippet: str,
    due_date: date | None = None,
) -> Opportunity:
    return Opportunity(
        title=title,
        agency=agency,
        source_name="Maryland eMMA",
        source_url="https://emma.maryland.gov/",
        opportunity_url="https://emma.maryland.gov/page.aspx/en/bpm/process_manage_extranet/1",
        due_date=due_date if due_date is not None else date.today() + timedelta(days=30),
        description_snippet=description_snippet,
        extraction_confidence=0.95,
        manual_review_needed=False,
        status="Saved",
    )


@pytest.fixture(autouse=True)
def disable_ai_overlay(monkeypatch):
    monkeypatch.setattr(scoring_service.ai_service, "score_text", lambda _: None)


def test_strong_emma_cyber_security_opportunity_scores_as_pursue():
    result = scoring_service.score_opportunity(
        opportunity(
            title="BPM056393 Cyber Asset Attack Surface Management",
            agency="DoIT - Dept Of Information Technology - Administration",
            description_snippet=(
                "Status: Open | Category: Cloud-based protection or security software | "
                "Type: IFB: Invitation for Bid (w/ Min Quals)"
            ),
        ),
        {"name": "Sean"},
    )

    assert set(result) == EXPECTED_SCORE_KEYS
    assert result["recommendation"] == "Pursue"
    assert result["fit_score"] >= 75
    assert result["skill_match"] >= 75
    assert result["local_fit"] == 85


def test_construction_security_false_positive_does_not_become_pursue():
    result = scoring_service.score_opportunity(
        opportunity(
            title="Security Fence Renovation and Property Improvements",
            agency="Maryland Department of General Services",
            description_snippet=(
                "Status: Open | Category: Building construction and facility renovation | "
                "Type: IFB: Invitation for Bid"
            ),
        ),
        {"name": "Sean"},
    )

    assert result["recommendation"] != "Pursue"
    assert result["complexity_risk"] >= 70
    assert result["fit_score"] < 55


def test_commodity_maintenance_opportunity_stays_skip_or_low_watch():
    result = scoring_service.score_opportunity(
        opportunity(
            title="Security Camera Hardware Maintenance Supplies",
            agency="Maryland Department of Public Safety",
            description_snippet=(
                "Status: Open | Category: Commodity maintenance supplies and installation | "
                "Type: IFB: Invitation for Bid"
            ),
        ),
        {"name": "Sean"},
    )

    assert result["recommendation"] in {"Skip", "Manual Review", "Watch"}
    assert result["recommendation"] != "Pursue"
    assert result["fit_score"] <= 55
    assert result["complexity_risk"] >= 70


@pytest.mark.parametrize(
    ("due_date", "expected_deadline_risk", "expected_recommendation"),
    [
        (None, 30, "Pursue"),
        (date.today() - timedelta(days=1), 100, "Skip"),
        (date.today() + timedelta(days=2), 90, "Skip"),
    ],
)
def test_deadline_risk_remains_meaningful_for_missing_expired_and_tight_dates(
    due_date,
    expected_deadline_risk,
    expected_recommendation,
):
    row = opportunity(
        title="Cybersecurity Risk Assessment",
        agency="Maryland Department of Information Technology",
        description_snippet="NIST cybersecurity compliance assessment and security policy review.",
    )
    row.due_date = due_date

    result = scoring_service.score_opportunity(row, {"name": "Sean"})

    assert result["deadline_risk"] == expected_deadline_risk
    assert result["recommendation"] == expected_recommendation
