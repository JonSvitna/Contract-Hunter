# Settings Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user edit keywords, business profile, and scoring rules from the app while keeping the existing YAML config files as the source of truth.

**Architecture:** Add typed Pydantic settings schemas and YAML save helpers in the backend, expose focused PATCH endpoints under `/api/search/config`, update deterministic scoring to load configurable rules with defaults, then replace the read-only settings preview with structured editable forms. Scheduler and throttle controls stay on the same page and keep their existing APIs.

**Tech Stack:** FastAPI, Pydantic v2, PyYAML, pytest, Next.js App Router, React, TypeScript.

---

## File Structure

- Create `local-contract-hunter-ai/backend/app/schemas/settings.py`: typed settings payloads and validation.
- Modify `local-contract-hunter-ai/backend/app/services/source_service.py`: YAML load/save helpers for editable settings.
- Modify `local-contract-hunter-ai/backend/app/routes/search.py`: settings config PATCH routes.
- Modify `local-contract-hunter-ai/backend/app/services/scoring_service.py`: configurable scoring fallback.
- Create `local-contract-hunter-ai/backend/tests/test_settings_routes.py`: API persistence and validation tests.
- Modify `local-contract-hunter-ai/backend/tests/test_proposal_checklist_service.py` or create focused scoring tests if needed: prove scoring rules affect recommendation.
- Modify `local-contract-hunter-ai/frontend/lib/types.ts`: settings types.
- Modify `local-contract-hunter-ai/frontend/lib/api.ts`: settings update calls.
- Modify `local-contract-hunter-ai/frontend/app/settings/page.tsx`: structured editable UI.

Do not commit unless explicitly requested.

---

## Task 1: Backend Settings Schemas

**Files:**
- Create: `local-contract-hunter-ai/backend/app/schemas/settings.py`

- [ ] **Step 1: Add schema file**

Define:

```python
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class TargetContractSize(BaseModel):
    preferred_min: int = Field(ge=0)
    preferred_max: int = Field(ge=0)
    acceptable_max: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_order(self):
        if not (self.preferred_min <= self.preferred_max <= self.acceptable_max):
            raise ValueError("contract size must satisfy preferred_min <= preferred_max <= acceptable_max")
        return self


class KeywordsUpdate(BaseModel):
    keywords: list[str] = Field(max_length=100)

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for item in value:
            keyword = item.strip()
            if not keyword:
                continue
            key = keyword.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(keyword)
        if not normalized:
            raise ValueError("at least one keyword is required")
        return normalized


class BusinessProfileUpdate(BaseModel):
    name: str = Field(min_length=1)
    company: str = Field(min_length=1)
    location: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    target_contract_size: TargetContractSize
    preferred_work: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)


class ScoringWeights(BaseModel):
    skill_match: float = Field(ge=0, le=1)
    solo_fit: float = Field(ge=0, le=1)
    revenue_fit: float = Field(ge=0, le=1)
    local_fit: float = Field(ge=0, le=1)


class ScoringPenalties(BaseModel):
    complexity_factor: float = Field(ge=0, le=1)


class RecommendationBands(BaseModel):
    pursue_min: int = Field(ge=0, le=100)
    watch_min: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_order(self):
        if self.watch_min > self.pursue_min:
            raise ValueError("watch_min must be less than or equal to pursue_min")
        return self


class DeadlineRules(BaseModel):
    expired: int = Field(ge=0, le=100)
    lt_3_days: int = Field(ge=0, le=100)
    lt_7_days: int = Field(ge=0, le=100)


class ScoringRulesUpdate(BaseModel):
    weights: ScoringWeights
    penalties: ScoringPenalties
    hard_penalties: list[str] = Field(default_factory=list)
    positive_skills: list[str] = Field(default_factory=list)
    recommendation_bands: RecommendationBands
    deadline_rules: DeadlineRules
```

- [ ] **Step 2: Run import check**

Run:

```bash
cd "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend" && uv run --python 3.12 --with-requirements requirements.txt python -c "from app.schemas.settings import KeywordsUpdate, BusinessProfileUpdate, ScoringRulesUpdate"
```

Expected: exits `0`.

---

## Task 2: YAML Save Helpers And API Tests

**Files:**
- Modify: `local-contract-hunter-ai/backend/app/services/source_service.py`
- Modify: `local-contract-hunter-ai/backend/app/routes/search.py`
- Create: `local-contract-hunter-ai/backend/tests/test_settings_routes.py`

- [ ] **Step 1: Write tests for keywords and config response**

Create tests that use `tmp_path`/monkeypatch or the existing test config directory pattern to assert:

```python
def test_patch_keywords_normalizes_and_persists(client):
    response = client.patch(
        "/api/search/config/keywords",
        json={"keywords": [" cybersecurity ", "", "Cybersecurity", "NIST"]},
    )
    assert response.status_code == 200
    assert response.json() == {"keywords": ["cybersecurity", "NIST"]}

    preview = client.get("/api/search/config")
    assert preview.status_code == 200
    assert preview.json()["keywords"] == ["cybersecurity", "NIST"]
    assert "scoring_rules" in preview.json()
```

- [ ] **Step 2: Write validation tests**

Add:

```python
def test_patch_business_profile_rejects_invalid_contract_size(client):
    payload = {
        "name": "Sean",
        "company": "Vulnaguard LLC",
        "location": "Maryland",
        "profile": "Solo consultant",
        "skills": ["risk assessment"],
        "certifications": [],
        "education": [],
        "target_contract_size": {
            "preferred_min": 25000,
            "preferred_max": 2000,
            "acceptable_max": 50000,
        },
        "preferred_work": [],
        "avoid": [],
    }
    response = client.patch("/api/search/config/business-profile", json=payload)
    assert response.status_code == 422
```

Add:

```python
def test_patch_scoring_rules_rejects_out_of_bounds_weight(client):
    payload = {
        "weights": {"skill_match": 1.5, "solo_fit": 0.25, "revenue_fit": 0.2, "local_fit": 0.3},
        "penalties": {"complexity_factor": 0.2},
        "hard_penalties": ["staffing"],
        "positive_skills": ["cybersecurity"],
        "recommendation_bands": {"pursue_min": 75, "watch_min": 55},
        "deadline_rules": {"expired": 100, "lt_3_days": 90, "lt_7_days": 65},
    }
    response = client.patch("/api/search/config/scoring-rules", json=payload)
    assert response.status_code == 422
```

- [ ] **Step 3: Implement helpers**

Add to `source_service.py`:

```python
def save_keywords(keywords: list[str]) -> dict:
    payload = {"keywords": keywords}
    with (settings.config_dir / "keywords.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False)
    return payload


def load_scoring_rules() -> dict:
    return _read_yaml(settings.config_dir / "scoring_rules.yaml")


def save_business_profile(profile: dict) -> dict:
    with (settings.config_dir / "business_profile.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(profile, f, sort_keys=False)
    return profile


def save_scoring_rules(rules: dict) -> dict:
    with (settings.config_dir / "scoring_rules.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(rules, f, sort_keys=False)
    return rules
```

- [ ] **Step 4: Implement routes**

Import the schemas and helpers in `routes/search.py`. Add:

```python
@router.patch("/config/keywords")
def patch_keywords(payload: KeywordsUpdate):
    return save_keywords(payload.keywords)


@router.patch("/config/business-profile")
def patch_business_profile(payload: BusinessProfileUpdate):
    return save_business_profile(payload.model_dump())


@router.patch("/config/scoring-rules")
def patch_scoring_rules(payload: ScoringRulesUpdate):
    return save_scoring_rules(payload.model_dump())
```

Update `GET /config` to include `scoring_rules`.

- [ ] **Step 5: Run tests**

Run:

```bash
cd "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend" && uv run --python 3.12 --with-requirements requirements.txt pytest tests/test_settings_routes.py -q
```

Expected: pass.

---

## Task 3: Configurable Scoring

**Files:**
- Modify: `local-contract-hunter-ai/backend/app/services/scoring_service.py`
- Test: `local-contract-hunter-ai/backend/tests/test_settings_routes.py` or new `local-contract-hunter-ai/backend/tests/test_scoring_service.py`

- [ ] **Step 1: Add scoring test**

Add a focused test that monkeypatches `load_scoring_rules()` or uses temporary YAML to prove recommendation bands are used:

```python
def test_score_opportunity_uses_configured_recommendation_bands(monkeypatch):
    monkeypatch.setattr(
        "app.services.scoring_service.load_scoring_rules",
        lambda: {
            "weights": {"skill_match": 0.25, "solo_fit": 0.25, "revenue_fit": 0.2, "local_fit": 0.3},
            "penalties": {"complexity_factor": 0.2},
            "hard_penalties": ["staffing"],
            "positive_skills": ["cybersecurity"],
            "recommendation_bands": {"pursue_min": 95, "watch_min": 55},
            "deadline_rules": {"expired": 100, "lt_3_days": 90, "lt_7_days": 65},
        },
    )
    opportunity = Opportunity(
        title="Cybersecurity assessment",
        agency="County",
        source_name="County",
        source_url="https://example.test",
        description_snippet="cybersecurity assessment",
        status="Saved",
    )
    result = score_opportunity(opportunity, {})
    assert result["recommendation"] != "Pursue"
```

- [ ] **Step 2: Implement defaults and rules merge**

In `scoring_service.py`:

- Import `load_scoring_rules`.
- Add `DEFAULT_SCORING_RULES`.
- Add `_scoring_rules()` that merges YAML over defaults.
- Update `_recommendation()` to accept configured bands.
- Update deadline risk to use configured deadline values.
- Update fit score calculation to use configured weights and complexity factor.
- Keep AI payload override behavior unchanged.

- [ ] **Step 3: Run scoring/settings tests**

Run:

```bash
cd "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend" && uv run --python 3.12 --with-requirements requirements.txt pytest tests/test_settings_routes.py tests/test_proposal_checklist_service.py -q
```

Expected: pass.

---

## Task 4: Frontend Types, API, And UI

**Files:**
- Modify: `local-contract-hunter-ai/frontend/lib/types.ts`
- Modify: `local-contract-hunter-ai/frontend/lib/api.ts`
- Modify: `local-contract-hunter-ai/frontend/app/settings/page.tsx`

- [ ] **Step 1: Add frontend settings types**

Add `TargetContractSize`, `BusinessProfile`, `ScoringRules`, and `SettingsConfig`.

- [ ] **Step 2: Add API client methods**

Add:

```typescript
updateKeywords: (keywords: string[]) =>
  fetchJson<{ keywords: string[] }>("/api/search/config/keywords", {
    method: "PATCH",
    body: JSON.stringify({ keywords })
  })
```

Add equivalent methods for business profile and scoring rules.

- [ ] **Step 3: Update settings page state**

Add separate local state and section save/error messages:

- `keywordDraft`
- `businessProfile`
- `scoringRules`
- `savingSection`
- `sectionMessages`
- `sectionErrors`

Use line-based helper functions:

```typescript
function toLines(values: string[]): string {
  return values.join("\\n");
}

function fromLines(value: string): string[] {
  return value.split("\\n").map((item) => item.trim()).filter(Boolean);
}
```

- [ ] **Step 4: Replace readonly cards**

Replace the profile `<pre>` and keyword chips-only card with editable sections. Add a scoring rules card. Keep scheduler/throttle cards below them.

- [ ] **Step 5: Build frontend**

Run:

```bash
cd "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/frontend" && npm run build
```

Expected: pass.

---

## Task 5: Verification

**Files:**
- Modify only touched files if verification reveals defects.

- [ ] **Step 1: Run full backend tests**

```bash
cd "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/backend" && uv run --python 3.12 --with-requirements requirements.txt pytest -q
```

Expected: pass.

- [ ] **Step 2: Run frontend build**

```bash
cd "/Users/seanm/Documents/GitHub/Contract-Hunter/local-contract-hunter-ai/frontend" && npm run build
```

Expected: pass.

- [ ] **Step 3: Smoke settings API**

With backend running, call:

```bash
curl -sS -X PATCH "http://127.0.0.1:8000/api/search/config/keywords" \
  -H "Content-Type: application/json" \
  -d '{"keywords":["cybersecurity"," cybersecurity ","NIST"]}'
```

Expected response:

```json
{"keywords":["cybersecurity","NIST"]}
```

Restore the original keywords from `config/keywords.yaml` if the smoke test changes local config.

---

## Self-Review

- Spec coverage:
  - Backend write helpers and APIs: Tasks 1-2.
  - Scoring uses YAML: Task 3.
  - Structured UI: Task 4.
  - Verification: Task 5.
- Red-flag scan: no incomplete task instructions remain.
- Type consistency:
  - Backend route names match frontend API paths.
  - `scoring_rules` matches the `GET /api/search/config` field and `ScoringRules` type.
