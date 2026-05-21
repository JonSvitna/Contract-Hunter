# Scoring Model

The MVP uses rule-based deterministic scoring first, with optional OpenAI-compatible enrichment when an API key is present.

## Score outputs

- `fit_score` (0-100)
- `skill_match` (0-100)
- `solo_fit` (0-100)
- `revenue_fit` (0-100)
- `local_fit` (0-100)
- `deadline_risk` (0-100)
- `complexity_risk` (0-100)
- `past_performance_risk` (Low/Medium/High)
- `recommendation` (Pursue/Watch/Skip/Manual Review)
- `reasoning`
- `next_steps`

## Positive drivers

- Local government context from the title, agency, source, or description.
- Cybersecurity consulting language (NIST, vulnerability, compliance, risk, security, attack surface).
- Advisory and assessment style scope.
- Smaller budget signals.

## Penalties

- 24/7 operations and SOC monitoring expectations.
- Large staffing or managed services style work.
- Federal/state mega-contract context.
- Construction, renovation, property, commodity, supply, hardware, and maintenance scopes.
- Tight or expired deadlines.

## Recommendation logic

- Higher fit + manageable complexity => Pursue.
- Medium fit => Watch.
- High deadline/complexity risk => Skip.
- Unclear signal profile => Manual Review.
