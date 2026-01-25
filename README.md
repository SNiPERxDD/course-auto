# Coursera Automation Protocol (CDP Implementation)

![Version](https://img.shields.io/badge/version-1.0.0-blue?style=flat-square)
![Python](https://img.shields.io/badge/python-3.8%2B-green?style=flat-square)
![Protocol](https://img.shields.io/badge/protocol-CDP-orange?style=flat-square)
![Status](https://img.shields.io/badge/status-Research_Prototype-red?style=flat-square)

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

### B. Installation

**Windows (PowerShell Recommended):**
```powershell
# 1. Create a virtual environment (keeps your system python clean)
python -m venv .venv

# 2. Allow script execution for this session (fixes "disabled by your system" errors)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force

# 3. Activate the environment
.\.venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install -r requirements.txt
playwright install chromium
```

**macOS / Linux:**
```bash
git clone https://github.com/SNiPERxDD/course-auto.git
cd course-auto
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### C. Launch Configuration (Mandatory)
The host browser must be started with the remote debugging port exposed. Execute the following from a terminal:

**macOS:**
```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir="/tmp/chrome_dev"
```

**Windows (PowerShell):**
Try the first command. If it fails (Chrome not found), try the "Alternative x86" command.

```powershell
# Option 1: Standard 64-bit Installation
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome_dev"

# Option 2: Alternative (x86) Installation
& "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome_dev"
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
*   **Source Site Updates:** The script relies on specific CSS selectors (e.g., class names). If Coursera updates their website layout or code, these selectors WILL break, and the script will need to be updated.
*   **OS/IO Locking:** Non-blocking input on Windows requires `msvcrt`. Fallback logic defaults to "Stay/Safe" mode if the environment lacks asynchronous input support.

## 6. Disclaimer

This software is a research proof-of-concept for CDP-based automation. It is provided "as is" without warranty. Users assume all liability for its operation and adherence to platform Terms of Service.

## 7. Contributing

See `CONTRIBUTING.md` for guidelines on how to report issues and submit pull requests.

## 8. License

Distributed under the MIT License. See `LICENSE` for more information.
