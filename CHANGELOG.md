# Changelog

## [2026-01-25 12:30] - Stealth Migration & Cleanup
- **Removed** `playwright-stealth` dependency (bloat/unused).
- **Updated** `README.md` to reflect true "Stealth Mode" capabilities (CDP based).
- **Refactored** `coursera_stealth.py` (In Progress):
    - Removed `playbackRate` hack (Stealth violation).
    - Fixed `parse_time_to_seconds` silent failure.
    - Implemented robust Video Completion (Wait for "Next" button).
    - Implemented Reading Scraping and robust time detection.
    - Implemented randomized human scrolling.
