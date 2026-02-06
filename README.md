# Coursera Automation Protocol (CDP Implementation)

![Version](https://img.shields.io/badge/version-1.4.2-blue?style=flat-square)
![Python](https://img.shields.io/badge/python-3.8%2B-green?style=flat-square)
![Protocol](https://img.shields.io/badge/protocol-CDP-orange?style=flat-square)
![Status](https://img.shields.io/badge/status-Research_Prototype-red?style=flat-square)

> [!WARNING]
> **Use at your own risk.** This tool relies on specific CSS selectors that Coursera can change at any time. It **can and will break** without notice if the site is updated. Manual intervention is often required.

## 1. System Overview

This tool implements a high-precision automation layer over an authoritative Chrome session. Unlike traditional "headless" bots which are easily fingerprinted, this system attaches to an existing, authenticated browser process using the remote debugging protocol.

### Core Capabilities
1.  **Session Persistence:** Operates within the user's primary authenticated context.
2.  **Course Archival Engine:** Uses `course_manager.py` to build a high-fidelity map of the course and state-track progress using a structured XML ledger (`course_content.xml`).
3.  **Dual-Mode Operation:**
    *   **Stealth Mode (`coursera_stealth.py`):** Monitors user activity and acts as a "Senior Hacker" co-pilot, handling navigation and archival during playback.
    *   **Archiver Mode (`coursera_archiver.py`):** Targeted, map-driven engine that directly visits and scrapes all high-value content (Videos/Readings).
4.  **Content Archival:** Extracts transcripts and reading materials with integrity checks to ensure unique versioning.
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
# 1. Clone the repository
git clone https://github.com/SNiPERxDD/course-auto.git
cd course-auto

# 2. Create a virtual environment (keeps your system python clean)
python -m venv .venv

# 3. Allow script execution for this session (fixes "disabled by your system" errors)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force

# 4. Activate the environment
.\.venv\Scripts\Activate.ps1

# 5. Install dependencies
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

> [!WARNING]
> **Data Integrity Constraint**: Do NOT run `coursera_stealth.py` and `coursera_archiver.py` simultaneously on the same course. They write to the same `course_content.xml` ledger. Simultaneous execution will cause race conditions and corrupt the database.

1.  **Authentication:** Log in to the target platform on the debugging instance.
2.  **Initialization:** Navigate to the target module entry point.
3.  **Engagement:**

    **Option A: Stealth Co-Pilot (Standard)**
    Monitors your progress and archives as you watch.
    ```bash
    python coursera_stealth.py
    ```

    **Option B: Dedicated Archiver (Bulk)**
    Directly navigates and scrapes all Video/Reading content defined in the course map.
    ```bash
    python coursera_archiver.py
    # Optional: Force re-scrape everything
    python coursera_archiver.py --force
    ```

## 4. Operational Configuration

Parameters are defined in the global configuration block of `coursera_stealth.py`:

*   `CDP_URL`: WebSocket interface endpoint (Default: `http://localhost:9222`).
*   `TRANSCRIPT_DIR`: Output vector for text artifacts.
*   `VIDEO_COMPLETION_THRESHOLD`: Completion strictness percentage (0-100).

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
