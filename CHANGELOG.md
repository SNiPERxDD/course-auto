# Changelog

All notable changes to this project will be documented in this file.

## [1.4.1] - 2026-02-02
### 🚀 Features
- **Robust Transcript extraction**: Introduced a 2-stage extraction system. It first attempts UI-based scraping and automatically falls back to the "Downloads" tab to process `.txt` assets if the UI is brittle.
- **Selector Schema Update**: Added `downloads_tab` and `transcript_download_link` to `discover_selectors_coursera.py` for automated asset discovery.

## [1.4.2] - 2026-02-03
### 🛡️ Stability Hardening
- **Self-Healing Loop**: implemented automatic page re-acquisition if the browser connection is dropped.
- **Fail-Safe wrappers**: Wrapped all critical handlers (Quiz, Video, Reading) in granular `try-except` blocks to prevent crashes.
- **Fixed Next Button Logic**: Updated `get_next_button` to prioritize *visible* elements and hardened `human_click` to ignore hover failures (overlay resilience).
- **Fixed Sidebar Scrolling**: Constrained random mouse movements to the main content area to prevent accidental sidebar navigation.
- **Enhanced Content Detection**: Added explicit detection/skip for "Peer Assessment", "Honors Assignment", and "Review Your Peers".

## [1.4.0] - 2026-02-02
### 🚀 Features (Stealth Suite)
- **High-Precision Organic Completion**: Randomized video completion target (97.0 - 100.0%) to evade behavioral analysis.
- **Attention Fidgeting**: Added randomized mouse "fidget" movements during video playback and reading sessions to simulate active engagement.
- **Human Clicking (Tactical Approach)**: Refactored all button interactions to a unified `human_click` utility with smooth glide trajectories (steps) and organic reaction times.

## [1.3.0] - 2026-02-02
### 🚀 Features
- **Dedicated Targeted Archiver**: Introduced `coursera_archiver.py`, a standalone script for high-efficiency, map-driven scraping.
- **Direct Navigation Engine**: Bypasses brittle UI traversal by visiting targets directly from the internal map.
- **HVC (High-Value Content) Focus**: Targeted extraction of Video transcripts and Reading body text only.
- **Resumption Intelligence**: Automatically skips items already present in the XML ledger to prevent redundant hits.

## [1.1.0] - 2026-02-02
### 🚀 Features
- **Global Course Mapping**: Added initial deep scan to expand sidebar module accordions and print a high-resolution ASCII tree of the entire course structure.
- **Literal Type Extraction**: Refactored type detection to extract categories directly from sidebar subtext (e.g., "Ungraded Plugin", "Reading", "Video"). This eliminates hardcoded type guessing.
- **Technical URL Prioritization**: Scanning logic now prioritizes technical URL markers (like `/ungradedlab/`) over filler keywords. This ensures introductory content correctly satisfies discovery targets and prevents infinite navigation loops.
- **Dynamic Exit Targets**: Logic now determines which core lesson types are actually present in the course and only awaits those before autonomous termination.
- **Filler Content Filtering**: Automatically recognizes and ignores non-essential items like surveys ("How Was the Course?"), welcome pages, and orientations using a combination of subtext parsing and keyword detection.
- **Improved Smart-NAV**: Navigation now utilizes the global course map to efficiently hop across modules to find missing targets.

### 🛠 Improvements
- Refactored sidebar parsing to handle flat DOM structures and improved type detection via `aria-label`.
- Added `wait_for_selector` and multi-tag support (H2, H3, Button) for resilient mapping.
- Cleaned up tree visualization with ASCII connectors and type icons.

## [1.0.1] - 2026-01-25
### 🛠 Fixes
- **Video Failsafe**: Added 30-second pause timeout to force-resume videos stuck in buffering or paused states.
- **Log Spam Fix**: Added URL-based stuck detection (`stuck_on_item_counter`) to quietly exit when the course is finished.

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
