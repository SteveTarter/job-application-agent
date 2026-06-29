# Changelog

All notable changes to the Job Application Agent will be documented in this file.

## [Unreleased] - 2026-06-29

### Added
- **Multi-job Session Isolation**: Added `job_index` tracking to `AgentState` and prefixed all job-related interrupts (`job_input`, `letter_confirm`, `refinement_input`) with the job index. This prevents frontend client-side cache collisions and ensures prompts are always rendered correctly across multiple job postings.
- **Explicit Phrase Traversals**: Shifted workflow routing transitions to deterministic string matches on explicit user phrases:
  - Transition from `setup_candidate` to `analyze_job` via `"job postings"`.
  - Transition from `analyze_job` to `generate_cover_letter` via `"cover letter"`.
  - Transition from `analyze_job` or `generate_cover_letter` back to `setup_candidate` via `"update profile"`.
  - Transition from `generate_cover_letter` to `analyze_job` via `"job postings"`.
- **Google Search Grounding Fallback**: Added a two-step search grounding fallback in `analyze_job` to retrieve real-time company background and news for unknown companies, bypassing controlled generation limitations.
- **Multimodal PDF Processing**: Added local file path detection and integration of `pypdf` to extract candidate hyperlinked LinkedIn/GitHub URLs and read PDF binary contents directly via Gemini's multimodal API.

### Fixed
- **Cover Letter Cache Invalidation**: Explicitly cleared cached cover letters and reset draft numbers when routing back to the profile setup stage or when adjusting match scores/strategies, ensuring cover letters are regenerated with the updated context.
- **Strict Profile Update Routing**: Restricted profile update triggers in the cover letter refinement screen to explicit words like `"update profile"` or `"edit resume"`, preventing factual statements about skills or experience from incorrectly routing to setup.
- **GitHub Username Normalization**: Normalizes extracted GitHub URLs/paths to raw usernames to prevent 404 API errors during repo fetching.
- **URL Fetching Detection**: Refined URL detection in `analyze_job` to only fetch job postings when the input is a single HTTP(S) URL without spaces or newlines, preventing pasted descriptions from triggering loaders.
- **Name Capitalization**: Normalized candidate names using Title case format.
- **Error Propagation**: Removed mock fallbacks and boilerplate in company searches, repository fetching, and URL loading, propagating clean exceptions to the console/UI.
