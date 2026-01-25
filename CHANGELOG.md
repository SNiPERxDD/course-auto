# Changelog

All notable changes to this project will be documented in this file.

## [1.0.1] - 2026-01-25
### 🛠 Fixes
- **Video Failsafe**: Added 30-second pause timeout to force-resume videos stuck in buffering or paused states.

## [1.0.0] - 2026-01-25

### 🚀 Features
- **CDP Stealth**: Implemented Chrome DevTools Protocol attachment to bypass bot detection.
- **Videos**: 100% completion logic (waits for native `ended` event).
- **Readings**: Human-like randomized scrolling (variable speed/intervals).
- **Archival**: Automatic transcript and reading text extraction with strict versioning (`_v2.txt`).
- **State Persistence**: `visited_history.json` tracks completed URLs to prevent redundancy.
- **Robustness**: 
    - Auto-detects and pauses for **Graded Quizzes**.
    - Auto-skips **Ungraded Plugins** and **Practice Quizzes**.
    - Graceful `Ctrl+C` exit handling.

### 🛠 Improvements
- Suppressed Node.js/Playwright deprecation warnings.
- Added cross-platform Windows input fallback (safe-stay default).
- strict sidebar completion detection (no partial title matches).

### 📖 Documentation
- "Doctrine" standard README with technical specifications.
- Added Shields.io status badges.
