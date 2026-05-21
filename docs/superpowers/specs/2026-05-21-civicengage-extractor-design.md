# CivicEngage Extractor Design

## Purpose

Improve source quality for Maryland county procurement pages that use CivicEngage bid listings. Several county sources expose public `Bids.aspx` pages, but the generic scraper only scans anchor text for keywords and often creates broad manual-review fallback rows. A CivicEngage-specific extractor should produce more precise bid candidates with real posting links, titles, statuses, and due dates where available.

## Scope

This spec covers the first source-specific extractor phase:

- Add a small scraper selection framework that can choose a specialized scraper for known source URL patterns.
- Implement a CivicEngage bids scraper for public `Bids.aspx` pages.
- Use the existing source validation/run history dashboard to measure extractor results.
- Keep non-CivicEngage sources on the existing generic scraper.
- Add focused tests with fake pages; do not rely on live county websites in tests.

Out of scope:

- OpenGov, IonWave, Workday, or eMMA extractor improvements.
- New database fields for sources.
- Bulk validation controls.
- Browser-bypass logic for blocked sites.
- Proposal workflow changes.

## Current Baseline

Source validation now records `SourceRun` and `SourceRunItem` history. The current generic scraper lives at:

- `local-contract-hunter-ai/backend/app/scrapers/generic_procurement_scraper.py`

Scraper selection currently happens in:

- `local-contract-hunter-ai/backend/app/services/search_service.py`

`get_scraper_for_source(source)` returns `EmmaScraper` for `source_type == "emma"` and `GenericProcurementScraper` for everything else.

County sources currently using or likely matching CivicEngage-style bid pages include:

- `Allegany County Bid Postings` -> `https://www.alleganygov.org/bids.aspx`
- `Caroline County Bid Opportunities` -> `https://www.carolinemd.org/Bids.aspx`
- `Queen Anne's County Bid Postings` -> `https://www.qac.org/bids.aspx`
- `Wicomico County Bid Postings` -> `https://www.wicomicocounty.org/Bids.aspx?CatID=All&Status=&showAllBids=on&txtSort=Category`

These should be the initial validation targets.

## Design

### Scraper Selection

Add a helper in `search_service.py` or a small new module:

```python
def get_scraper_for_source(source: Source):
    ...
```

Keep the existing public function name so tests and callers do not need to change. Internally, select:

- `EmmaScraper` when `source_type.lower() == "emma"`.
- `CivicEngageBidScraper` when the source URL host/path resembles a CivicEngage bid page:
  - URL path contains `bids.aspx` case-insensitively.
  - Or query/path includes common CivicEngage bid-listing structure.
- `GenericProcurementScraper` otherwise.

Do not add a DB `extractor_key` yet. URL-based detection is enough for this phase and avoids changing source editing flows.

### CivicEngageBidScraper

Create:

- `local-contract-hunter-ai/backend/app/scrapers/civicengage_bid_scraper.py`

Interface:

```python
class CivicEngageBidScraper(BaseScraper):
    def __init__(
        self,
        delay_seconds: float = 2.0,
        max_candidate_links: int = 120,
        page_timeout_ms: int = 20000,
        body_timeout_ms: int = 5000,
    ) -> None:
        ...

    def scrape(self, source_name: str, source_url: str, keywords: list[str]) -> list[dict]:
        ...
```

Behavior:

1. Open `source_url` with Playwright.
2. Read the body text for fallback snippets and due-date parsing.
3. Extract anchors from the page, preserving `href` and visible text.
4. Treat anchors as bid candidates when:
   - Link text is not empty.
   - Link URL or text includes `bid`, `rfp`, `proposal`, `solicitation`, `quote`, or `Bids.aspx?bidID=`.
   - Prefer candidate links with `bidID=` because they usually point to individual postings.
5. If keyword terms match the candidate link text, mark `manual_review_needed=False`.
6. If no keywords match but the link appears to be a real bid posting, still return it with `manual_review_needed=True` and moderate confidence. This is better than one generic fallback row because it preserves the specific posting URL.
7. Parse possible due dates from link text first, then surrounding/body text if needed.
8. Deduplicate candidates by final URL.
9. If no bid candidates are found, return the same style of manual-review fallback as the generic scraper.

Candidate shape stays compatible with existing search persistence:

```python
{
    "title": "...",
    "agency": source_name,
    "source_name": source_name,
    "source_url": source_url,
    "opportunity_url": joined_url,
    "due_date": due_date,
    "description_snippet": snippet,
    "extraction_confidence": confidence,
    "manual_review_needed": manual_review_needed,
}
```

### Confidence

Use existing helpers from `extraction_service.py`:

- `confidence_from_text`
- `parse_possible_due_date`
- `snippet_with_keywords`

Then apply small extractor-specific adjustments:

- Real bid detail URL with keyword match: at least `0.75`.
- Real bid detail URL without keyword match: at least `0.45` and manual review.
- Fallback row: `0.2`.

Keep scores bounded to `0.0` through `1.0`.

### Error Handling

The scraper should follow the generic scraper's graceful behavior:

- If Playwright is unavailable, return one manual-review fallback candidate.
- If navigation, parsing, or browser launch fails, return one manual-review failure candidate.
- Cleanup failures from browser/context close must not escape.

Source run history should then show a completed run with a manual-review candidate rather than a failed run, unless the failure occurs outside scraper execution.

## API And UI Impact

No new API endpoints are required.

Existing endpoints should automatically benefit:

- `POST /api/search/validate/source`
- `POST /api/search/run`
- `GET /api/sources/dashboard`
- `GET /api/source-runs/{run_id}`

The `/sources` dashboard should show improved candidate counts and lower manual-review fallback rates for CivicEngage sources when real bid posting links are extracted.

No frontend UI changes are required for this phase unless tests reveal a display bug.

## Testing

Backend tests should cover:

- Scraper selection chooses `CivicEngageBidScraper` for `Bids.aspx` URLs.
- Scraper selection leaves non-CivicEngage generic sources on `GenericProcurementScraper`.
- CivicEngage scraper extracts a `bidID=` detail link as a candidate.
- Keyword-matching candidates are not manual review and have higher confidence.
- Non-keyword bid candidates are still specific manual-review candidates.
- Duplicate bid links are emitted once.
- No candidate links returns a manual-review fallback.
- Cleanup failures do not escape.
- Existing generic scraper tests continue to pass.
- Source validation route records `SourceRunItem` rows for extracted CivicEngage candidates.

Verification:

- Run targeted scraper and search tests.
- Run full backend tests.
- Run frontend build.
- Smoke validate one live CivicEngage source, such as `Allegany County Bid Postings`, and confirm the latest source run is `completed`.

## Acceptance Criteria

- CivicEngage `Bids.aspx` sources use the new scraper automatically.
- Validating a CivicEngage source can produce specific bid candidates instead of only one broad fallback row.
- Source run history records those candidates and actions.
- Non-CivicEngage sources keep existing behavior.
- Backend tests and frontend build pass.
- Live validation of at least one CivicEngage source completes without the Playwright cleanup failure.

## Future Work

- Add `extractor_key` or source category metadata once the UI supports source editing.
- Add OpenGov and IonWave extractors.
- Add per-source validation status notes explaining which extractor was used.
- Add source dashboard filters for `extractor`, `high manual review`, and `failed last run`.
