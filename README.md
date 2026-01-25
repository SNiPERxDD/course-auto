# Coursera Automation Protocol (CDP Implementation)

**Version:** 1.0.0 (Research Prototype)  
**Architecture:** Chrome DevTools Protocol (CDP) / Python 3  
**Status:** Experimental

## 1. System Overview

This tool implements a high-precision automation layer over an authoritative Chrome session. Unlike traditional "headless" bots which are easily fingerprinted, this system attaches to an existing, authenticated browser process using the remote debugging protocol.

### Core Capabilities
1.  **Session Persistence:** Operates within the user's primary authenticated context.
2.  **State Management:** Tracks visited URLs via `visited_history.json` to prevent redundant processing.
3.  **Content Archival:** Extracts transcripts and reading materials with cryptographic-level integrity checks (difflib variation analysis) to ensure unique versioning.
4.  **Completion Logic:** 
    *   **Video:** Enforces parity with native player events (`ended`) or configured completion thresholds.
    *   **Reading:** Simulates human engagement via randomized DOM interaction events.
    *   **Plugins:** Identifies and bypasses non-essential LTI (Learning Tools Interoperability) plugins.

## 2. Technical Prerequisites

The system requires an initialized debugging interface on the host browser.

### A. Environment
*   **Python:** 3.8+
*   **Dependencies:** `playwright`, `plyer`
*   **Browser:** Google Chrome (Chromium)

### B. Launch Configuration (Mandatory)
The host browser must be started with the remote debugging port exposed. Execute the following from a terminal:

**macOS:**
```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir="/tmp/chrome_dev"
```

**Windows:**
```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome_dev"
```

## 3. Execution Protocol

1.  **Authentication:** Log in to the target platform on the debugging instance.
2.  **Initialization:** Navigate to the target module entry point.
3.  **Engagement:**
    ```bash
    python coursera_stealth.py
    ```

## 4. Operational Configuration

Parameters are defined in the global configuration block of `coursera_stealth.py`:

*   `CDP_URL`: WebSocket interface endpoint (Default: `http://localhost:9222`).
*   `TRANSCRIPT_DIR`: Output vector for text artifacts.
*   `VIDEO_COMPLETION_THRESHOLD`: Completion strictness percentage (0-100).
*   `HISTORY_FILE`: Persistence storage for state tracking.

## 5. Known Limitations & Constraints

*   **Graded Instruments:** The system explicitly pauses upon detection of Graded Quizzes. Manual intervention is required for academic integrity and logic complexity reasons.
*   **LTI Plugins:** Heuristic detection of "Ungraded Plugins" is aggressive. False positives are possible if the plugin container mimics core content structure.
*   **Platform Variance:** DOM selectors are tightly coupled to the current frontend rendering logic. Layout changes by the vendor will necessitate selector refactoring.
*   **OS/IO Locking:** Non-blocking input on Windows requires `msvcrt`. Fallback logic defaults to "Stay/Safe" mode if the environment lacks asynchronous input support.

## 6. Disclaimer

This software is a research proof-of-concept for CDP-based automation. It is provided "as is" without warranty. Users assume all liability for its operation and adherence to platform Terms of Service.
