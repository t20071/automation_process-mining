# Changelog

## 0.2.0 — 2026-10-16

### Added
- **Overview tab** with process health score (0–100), auto-generated key findings,
  weekly volume/throughput trends and a process-path (variant) table.
- **Interactive process map** rendered client-side from Graphviz DOT — crisp, zoomable,
  with start/end nodes, frequency or mean-wait edge labels and a rare-transition filter.
- **Impact & ROI tab** with adjustable currency, hourly cost, handling time, adoption and
  scope; results are annualised from the log's time span.
- **Decision gate** upgrades: step-by-step gate trace, proposal sandbox, live Groq agent
  for real cases, downloadable JSONL audit log.
- **Event log tab** with data-quality summary, filters and cleaned-CSV export.
- Ingestion now derives `duration_seconds` from timestamps when the column is missing.
- Analysis settings in the sidebar (bottleneck count, consistency threshold).
- New unit tests (ingestion, analytics, LLM parsing, DOT builder, gate trace) and a
  GitHub Actions CI workflow.

### Changed
- Complete UI redesign (editorial enterprise style: light grotesk display type,
  eyebrow labels, bracketed stats, numbered sections) driven by `.streamlit/config.toml`.
- Repository reorganised: `ui/components`, `ui/views`, `ingestion/`, `tests/unit`,
  `tests/integration`, `docs/`.
- Bottleneck steps are no longer also flagged as automatable.
- Default Groq model is `llama-3.3-70b-versatile` (the previous default was retired).
- Matplotlib dependency removed.

### Fixed
- Uploading a second CSV showed the first file's cached results.
- "Upload new file" immediately reloaded the previous upload.
- Sidebar toggle was hidden by CSS.
- `CONFIDENCE_THRESHOLD` was read before `.env` was loaded.
- LLM replies wrapped in Markdown code fences failed to parse.

## 0.1.0

- Initial release: DFG discovery, automation advisor, gate engine, Streamlit dashboard.
