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
