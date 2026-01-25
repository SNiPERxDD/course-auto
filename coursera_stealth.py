import time
import os
import re
import random
import sys
import select
import difflib
from playwright.sync_api import sync_playwright
from plyer import notification

# --- CONFIGURATION ---
# --- CONFIGURATION ---
CDP_URL = "http://localhost:9222"
TRANSCRIPT_DIR = "coursera_transcripts"
VIDEO_COMPLETION_THRESHOLD = 100 # Percentage (0-100) to consider video watched
HISTORY_FILE = "visited_history.json"

# Suppress Playwright/Node deprecation warnings
os.environ["NODE_OPTIONS"] = "--no-deprecation"

def check_and_handle_modal(page):
    """Checks for and handles common modals (Honor Code, Polls) anywhere."""
    try:
        # Honor Code
        if page.locator("h2", has_text="Coursera Honor Code").is_visible() or \
           page.locator("h1", has_text="Coursera Honor Code").is_visible():
            print("\n   └── 🛡️ Honor Code detected. Accepting...")
            # Click Continue (try multiple specific selectors provided by user logic)
            page.locator("button:has-text('Continue')").click(force=True)
            time.sleep(1)

        # Demographics Poll
        if page.locator("h2", has_text="Demographics Survey").is_visible():
             print("\n   └── 🗳️ Poll detected. Skipping...")
             page.locator("button:has-text('Continue'), button:has-text('Submit')").click()
             time.sleep(1)
    except: pass

def load_history():
    """Loads the set of visited URLs from JSON."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f: return set(json.load(f))
        except: pass
    return set()

def save_history(history_set):
    """Saves the set of visited URLs to JSON."""
    try:
        with open(HISTORY_FILE, "w") as f: json.dump(list(history_set), f)
    except: pass

def save_content_smart(filepath, new_content):
    """Saves content, verifying correlation (>95%) to avoid overwriting distinct content."""
    if not os.path.exists(filepath):
        with open(filepath, "w") as f: f.write(new_content)
        return filepath
    
    try:
        with open(filepath, "r") as f: existing = f.read()
        ratio = difflib.SequenceMatcher(None, existing, new_content).ratio()
        
        if ratio > 0.95:
            return filepath # Same content (duplicates), ignore
            
        # Content is different! Create a new version
        print(f"   └── ⚠️ Content changed (Correlation {ratio:.1%}). Saving new version.")
        base, ext = os.path.splitext(filepath)
        counter = 2
        while True:
            candidate = f"{base}_v{counter}{ext}"
            if not os.path.exists(candidate):
                with open(candidate, "w") as f: f.write(new_content)
                return candidate
            
            # Check if this version matches to avoid creating v3, v4 of same thing
            with open(candidate, "r") as f: existing_v = f.read()
            ratio_v = difflib.SequenceMatcher(None, existing_v, new_content).ratio()
            if ratio_v > 0.95:
                return candidate
            counter += 1
    except Exception as e:
        print(f"   └── ⚠️ Save error: {e}")
        return filepath

def parse_time_to_seconds(time_str):
    """(Fixed) Parses time string to seconds with error handling."""
    if not time_str: return 0
    try:
        parts = list(map(int, time_str.split(':')))
        if len(parts) == 2: return parts[0] * 60 + parts[1]
        if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
    except ValueError:
        return 0 # Non-fatal, just means time isn't parseable yet
    except Exception:
        return 0
    return 0

def get_page_context(page):
    """Scrapes Course and Module names for logging."""
    try:
        module = page.locator("span.css-6ecy9b").first.inner_text()
    except:
        module = "Unknown Module"
    
    try:
        course = page.title().split("|")[0].strip()
    except:
        course = "Unknown Course"
        
    return f"📘 {course} > {module}"

def random_human_scroll(page, duration_sec, initial_context):
    """(New) Performs randomized, human-like scrolling."""
    start_time = time.time()
    while (time.time() - start_time) < duration_sec:
        # 1. Check for Interruptions (Quiz)
        if page.locator(".rc-QuizApp").count() > 0: return

        # 2. Check for User Navigation (Context Change)
        current_context = get_page_context(page)
        if current_context != initial_context:
            print(f"\n🛑 User navigated away! Stopping current timer.")
            print(f"   └── Switched to: {current_context}")
            return "NAVIGATED"

        # Random scroll amount and interval (Dynamic Range)
        # Use more variable ranges to avoid detection fingerprints
        scroll_y = random.randint(30, 300) 
        
        # Direction: Mostly down (85%), occasionally up (15%)
        direction = 1 if random.random() > 0.15 else -1
        
        # Check Modals during reading (Honor Code might pop up)
        check_and_handle_modal(page)
        
        try:
            # Smooth scroll simulation could be better, but we vary the steps
            page.mouse.wheel(0, scroll_y * direction)
        except Exception as e:
            # Don't fail silently; log it so we know if we lost the page
            print(f"\n   └── ⚠️ Scroll failed (Page closed?): {e}")
            break
        
        # Variable sleep to avoid heartbeat detection
        time.sleep(random.uniform(1.5, 4.0))
        
        # Log progress occasionally
        elapsed = time.time() - start_time
        remaining = duration_sec - elapsed
        prog = (elapsed / duration_sec) * 100
        
        # Reading Progress Bar
        bar_len = 20
        filled = int(bar_len * prog / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        if remaining > 0:
             print(f"\r   └── ⏳ Reading: [{bar}] {prog:.1f}% ({int(remaining)}s left)    ", end="")
    return "COMPLETED"

def input_with_timeout(timeout=30):
    """Waits for user input with a timeout (Cross-platform safe)."""
    print(f"   └── ✅ Item Completed. Skipping in {timeout}s... (Press 's' to SKIP, ENTER to STAY)")
    
    # Windows (nt) fallback using msvcrt if possible or safe default
    if os.name == 'nt':
        try:
            import msvcrt
            start_t = time.time()
            while (time.time() - start_t) < timeout:
                if msvcrt.kbhit():
                    ch = msvcrt.getch().lower()
                    if ch == b's': return False # Skip
                    return True # Stay (Any other key)
                time.sleep(0.1)
            return False # Timeout -> Auto-skip
        except ImportError:
             print("   └── (Windows: Non-blocking input not supported. Defaulting to STAY for safety)")
             time.sleep(timeout)
             return True # Default to STAY on Windows if we can't capture input
             
    # Unix/Mac
    import select
    i, o, e = select.select([sys.stdin], [], [], timeout)
    if i:
        line = sys.stdin.readline().strip().lower()
        if line == 's':
            return False # User requested skip
        return True # User stayed (Enter or other key)
    return False # Timeout (Auto-skip)

def check_completed_status(page):
    """Checks if the current item is already marked as completed."""
    try:
        # 1. Get Current Title to match in Sidebar
        current_title = page.title().split("|")[0].strip()
        
        # 2. Check Sidebar for this specific item having a success icon
        # CRITICAL: Use strict matching to avoid confusing "Product" with "Product Overview"
        # We get all items containing the text, then filter for EXACT match
        candidates = page.locator(f"div.outline-single-item-content-wrapper", has_text=current_title).all()
        
        target_item = None
        for item in candidates:
            try:
                # Sidebar item text usually: "Title\n10 min\n..."
                # We want the first line (Title) to match exactly
                item_text = item.inner_text().strip()
                item_title = item_text.split('\n')[0].strip()
                
                if item_title == current_title:
                    target_item = item
                    break
            except: pass
        
        if target_item and target_item.is_visible():
             # Check for the Green Tick specific to this item
             if target_item.locator("[data-testid='learn-item-success-icon']").count() > 0:
                 print(f"   └── 🔍 Sidebar indicates '{current_title}' is Completed.")
                 return True

        # 3. Fallbacks (Main Content)
        if page.locator("main h3", has_text="Completed").count() > 0: return True
        if page.locator("main [data-testid='learn-item-success-icon']").count() > 0: return True
        
        # 4. Check "Mark as completed" button absence for Readings
        if page.locator(".reading-title").count() > 0:
             # If title exists but button doesn't, it's likely done.
             # But be careful of loading states. We assume page is loaded.
             if page.locator("button:has-text('Mark as completed')").count() == 0:
                 return True

    except: pass
    return False

def get_filename_prefix(page):
    """Extracts 'M1', 'M2' etc from the module header or title."""
    try:
        # 1. Priority: Check Page Title (e.g. "Module 2 Overview | Course Name")
        title_text = page.title()
        match = re.search(r"Module\s*(\d+)", title_text, re.IGNORECASE)
        if match:
             return f"M{match.group(1)}_"

        # 2. Fallback: Breadcrumb/Header
        module_text = page.locator("span.css-6ecy9b").first.inner_text()
        match = re.search(r"MODULE\s*(\d+)", module_text, re.IGNORECASE)
        if match:
            return f"M{match.group(1)}_"
            
        # 3. Super Fallback: Check for any "Module X" visible in main content title
        main_header = page.locator("h1").first.inner_text()
        match = re.search(r"Module\s*(\d+)", main_header, re.IGNORECASE)
        if match:
             return f"M{match.group(1)}_"

    except: pass
    return ""

def handle_automation():
    with sync_playwright() as p:
        print(f"📡 Attempting to connect to existing Chrome on {CDP_URL}...")
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            context = browser.contexts[0]
            
            # Find the Coursera Tab
            page = None
            for p_obj in context.pages:
                if "coursera.org" in p_obj.url:
                    page = p_obj
                    page.bring_to_front()
                    print(f"✅ Coursera tab detected: {page.title()}")
                    break
            
            if not page:
                print("❌ No Coursera tab found. Opening one...")
                page = context.new_page()
                page.goto("https://www.coursera.org/")
                print("⚠️ Please navigate to a course item (Video/Reading) to start.")
                return

        except Exception as e:
            print(f"❌ Connection Failed: {e}")
            return

        print("👀 Monitoring for content...")
        last_log = ""
        visited_urls = load_history()

        while True:
            # 1. Context Logging
            try:
                current_context = get_page_context(page)
                if current_context != last_log:
                    print(f"\n{current_context}")
                    last_log = current_context
                    
                # 0. History Check (State Persistence)
                # If we have fully completed this URL before, we can skip logic or fast-track.
                # However, user might want to re-watch. We will log it.
                current_url = page.url.split('?')[0].split('#')[0] # Normalize: Remove query params and hash
                
                if current_url in visited_urls:
                     if "ALREADY_VISITED" not in last_log:
                         print("   └── 📜 History: Item already visited/completed.")
                         # We don't auto-skip immediately here to allow re-verification, 
                         # but checking completed status will likely be faster.
            except: pass

            # 2. Check for Polls
            try:
                # Selector for Poll Header
                poll_header = page.locator('h2.css-tlf8h5', has_text="Poll")
                if poll_header.count() > 0:
                     print("⚠️ Poll Detected. Attempting to skip...")
                     skip_btn = page.locator('span.cds-button-label', has_text="Skip").first
                     if skip_btn.is_visible():
                         skip_btn.click()
                         print("✅ Poll Skipped.")
                         time.sleep(2)
            except: pass

            # 3. Content Detection
            
            # Video: .rc-VideoControlsContainer OR video tag
            is_video = page.locator(".rc-VideoControlsContainer, video").count() > 0

            # Quiz Detection (Priority)
            # .rc-QuizApp = Standard Quiz
            # .rc-FormPartsQuestion = Assignment
            # Title has "Quiz" = Orientation/Practice Quiz
            is_quiz = page.locator(".rc-QuizApp, .rc-FormPartsQuestion, [data-testid='quiz-submit-button']").count() > 0
            if not is_quiz:
                 # Fallback: Check Title
                 if "Quiz" in page.title():
                     is_quiz = True

            # Plugin / Assignment Detection
            # "Ungraded Plugin", "Ungraded External Tool", or "Peer-graded Assignment"
            is_plugin = False
            is_assignment = False
            
            try:
                # Check for "Ungraded Plugin" text in metadata or headers
                # CRITICAL: Scan 'main' only to avoid sidebar/nav bar matches
                if page.locator("main", has_text="Ungraded Plugin").count() > 0 or \
                   page.locator("main", has_text="Ungraded External Tool").count() > 0:
                     is_plugin = True
                
                # Check for "Peer-graded Assignment" or "Case Study"
                if "Peer-graded Assignment" in page.title() or "Case Study" in page.title():
                    is_assignment = True
                    is_plugin = True # Reuse plugin skip logic for now
            except: pass

            # Reading: .reading-title OR data-testid='cml-viewer' OR generic "Reading" pill
            # CRITICAL: We only check for reading if it is NOT a quiz OR plugin OR assignment
            is_reading = False
            if not is_quiz and not is_video and not is_plugin and not is_assignment:
                is_reading = page.locator(".reading-title, [data-testid='cml-viewer']").count() > 0
                if not is_reading:
                     # Check for the metadata pill containing "Reading"
                     is_reading = page.locator("div:has-text('Reading')").locator("span:has-text('min')").count() > 0
            
            # Additional safety: If title has Quiz, it's not a reading
            if "Quiz" in page.title() or "Assignment" in page.title(): 
                is_reading = False
                
            # --- MODAL CHECK BEFORE ACTION ---
            check_and_handle_modal(page)

            # --- CHECK COMPLETION STATUS ---
            if (is_video or is_reading or is_plugin) and not is_quiz:
                if check_completed_status(page):
                     # Add to history since we confirmed it's done
                     # Normalize URL
                     normalized_url = page.url.split('?')[0].split('#')[0]
                     visited_urls.add(normalized_url)
                     save_history(visited_urls)
                     
                     user_stayed = input_with_timeout(30)
                     if not user_stayed:
                         # Skip/Navigate
                         print("   └── ⏭️ Skipping...")
                         try:
                             next_btn = page.locator("button[data-testid='next-item'], button:has-text('Go to next item')").first
                             if next_btn.is_visible(): 
                                 next_btn.click(force=True)
                                 time.sleep(5)
                                 continue
                         except: pass

            # --- HANDLERS ---
            
            if is_plugin:
                 if "PLUGIN" not in last_log:
                     print(f"\n🧩 UNGRADED PLUGIN DETECTED.")
                     print("   └── Skipping external tool/survey...")
                     last_log = "PLUGIN"
                 
                 # Attempt to Mark Complete or Next
                 try:
                     mark_btn = page.locator("button:has-text('Mark as completed')").first
                     if mark_btn.is_visible(): 
                         mark_btn.click()
                         print("   └── ✅ Marked as Completed.")
                         time.sleep(2)
                     
                     # Add to history
                     normalized_url = page.url.split('?')[0].split('#')[0]
                     visited_urls.add(normalized_url)
                     save_history(visited_urls)
                     
                     next_btn = page.locator("button[data-testid='next-item'], button:has-text('Go to next item')").first
                     if next_btn.is_visible():
                         next_btn.click(force=True)
                         time.sleep(5)
                 except: pass
                 time.sleep(2)
                 continue

            if is_quiz:
                # Check if it is a GRADED item
                # we look for "Graded" in the H1 or badges
                is_graded = False
                try:
                    text_content = page.locator("main").inner_text()
                    if "Graded Assignment" in text_content or "weighted heavily" in text_content:
                        is_graded = True
                    # Also check title specifically
                    if "Graded Quiz" in page.title():
                        is_graded = True
                except: pass
                
                if is_graded:
                    if "QUIZ" not in last_log:
                        print(f"\n🛑 GRADED QUIZ DETECTED.")
                        print("   └── Actions paused. Please solve manually.")
                        try: notification.notify(title="Coursera Bot", message="Graded Quiz detected!")
                        except: pass
                        last_log = "QUIZ"
                    
                    # Pause until cleared
                    while page.locator(".rc-QuizApp, .rc-FormPartsQuestion").count() > 0:
                        time.sleep(2)
                    print("✅ Quiz cleared. Resuming...")
                    continue
                else:
                    # Non-Graded (Practice/Orientation)
                    if "SKIP_QUIZ" not in last_log:
                        print(f"\n⚠️ Non-Graded Quiz Detected (Orientation/Practice).")
                        print("   └── Attempting to Skip/Next...")
                        last_log = "SKIP_QUIZ"
                    
                    try:
                        next_btn = page.locator("button[data-testid='next-item'], button:has-text('Go to next item')").first
                        if next_btn.is_visible():
                            next_btn.click(force=True)
                            time.sleep(5)
                        else:
                            # If no next button, maybe it's just a reading-style quiz? 
                            # Try Mark as Complete
                            mark_btn = page.locator("button:has-text('Mark as completed')").first
                            if mark_btn.is_visible(): mark_btn.click()
                    except: pass
                    time.sleep(2)
                    continue

            elif is_video:
                if "VIDEO" not in last_log:
                    print(f"\n🎥 VIDEO DETECTED.")
                    last_log = "VIDEO"
                
                # Capture start context for navigation check
                start_context = get_page_context(page)

                # A. Scrape Transcript (Retry Logic)
                try:
                    # Give time for UI to settle
                    time.sleep(2) 
                    transcript_btn = page.locator("button:has-text('Transcript')").first
                    if transcript_btn.is_visible(): 
                        transcript_btn.click()
                        time.sleep(1)
                    
                    # specific selector from Plan.md
                    # .rc-Transcript or #cds-react-aria...
                    page.wait_for_selector(".rc-Transcript, .rc-TranscriptHighlighter", timeout=5000)
                    transcript_text = page.locator(".rc-Transcript, .rc-TranscriptHighlighter").first.inner_text()
                    
                    title = page.title().split("|")[0].strip()
                    safe_title = re.sub(r'\W+', '_', title)
                    prefix = get_filename_prefix(page)
                    filepath = f"{TRANSCRIPT_DIR}/{prefix}{safe_title}_transcript.txt"
                    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
                    final_path = save_content_smart(filepath, transcript_text)
                    print(f"   └── 📝 Transcript saved: {final_path}")
                except Exception as e:
                    print(f"   └── ⚠️ Transcript scrape warning: {e}")

                # B. Mute & Playback
                try:
                    # Mute using button if possible (Stealth)
                    mute_btn = page.locator('button[aria-label="Mute"]').first
                    if mute_btn.is_visible():
                        mute_btn.click()
                        print("   └── 🔇 Video Muted.")
                    else:
                        # Fallback JS mute
                        page.evaluate("document.querySelector('video').volume = 0")
                        
                    # Explicitly click Play if needed
                    play_btn = page.locator('button[aria-label="Play"], button[data-testid="play-button"]').first
                    if play_btn.is_visible():
                        play_btn.click()
                    else:
                        page.evaluate("document.querySelector('video').play()")
                except: pass

                # C. Wait for Completion (Robust "Next" Check)
                print("   └── ⏳ Watching video (Waiting for 'Next' button)...")
                
                # We wait for the "Go to next item" button to be ENABLED and VISIBLE
                # Or for the video 'ended' even
                while True:
                    # CHECK FOR USER NAVIGATION
                    if get_page_context(page) != start_context:
                        print("\n🛑 User navigated away! Aborting video match.")
                        break

                    # Monitor Progress & Completion
                    try:
                        curr = page.locator(".current-time-display").first.inner_text()
                        total = page.locator(".duration-display").first.inner_text()
                        
                        curr_sec = parse_time_to_seconds(curr)
                        total_sec = parse_time_to_seconds(total)
                        prog = 0
                        
                        if total_sec > 0:
                            prog = (curr_sec / total_sec) * 100
                            # Interactive bar
                            bar_len = 20
                            filled = int(bar_len * prog / 100)
                            bar = "█" * filled + "░" * (bar_len - filled)
                            print(f"\r   └── ⏳ Progress: [{bar}] {prog:.1f}% ({curr}/{total})", end="")

                        # CRITICAL: Only trust "Next" button if we have watched most of the video
                        # or if the video is natively ended.
                        is_ended = page.evaluate("document.querySelector('video').ended")
                        
                        # Stricter >= THRESHOLD or native end
                        # Note: We subtract a small buffer (e.g. 0.5%) for float imprecision if purely time-based,
                        # but simple >= matches user intent.
                        if is_ended or prog >= VIDEO_COMPLETION_THRESHOLD:
                             print("\n   └── ✅ Video Complete (Progress/Ended).")
                             break
                             
                        # Check Next Button (But only if we are close to end)
                        # Some courses show "Next" immediately. We must ignore it until we are done.
                        # Check Next Button (Strict > Threshold - small buffer for rounding)
                        if prog >= (VIDEO_COMPLETION_THRESHOLD - 1): # Allow 1% buffer for rounding (e.g. 99% if 100)
                            next_btn = page.locator("button[data-testid='next-item'], button:has-text('Go to next item')").first
                            if next_btn.is_visible() and next_btn.is_enabled():
                                print(f"\n   └── ✅ Video Complete (Button Enabled & >{VIDEO_COMPLETION_THRESHOLD-1}%).")
                                
                                # Add to history
                                normalized_url = page.url.split('?')[0].split('#')[0]
                                visited_urls.add(normalized_url)
                                save_history(visited_urls)
                                
                                next_btn.click(force=True)
                                break
                                
                    except Exception as e: 
                        # Fallback for when elements are missing/loading
                        # Check native ended as backup
                        try:
                            if page.evaluate("document.querySelector('video').ended"): break
                        except: pass
                        # print(f"\r   └── Debug: {e}", end="")
                    
                    time.sleep(1)
                
                # Navigate (If not clicked by loop)
                try:
                     # Only click if we didn't abort
                     if get_page_context(page) == start_context:
                         # Add to history (Reading assumed complete if we are moving on)
                         normalized_url = page.url.split('?')[0].split('#')[0]
                         visited_urls.add(normalized_url)
                         save_history(visited_urls)
                         
                         next_btn = page.locator("button[data-testid='next-item'], button:has-text('Go to next item')").first
                         if next_btn.is_visible(): next_btn.click(force=True)
                except: pass
                time.sleep(5)


            elif is_reading:
                start_context = get_page_context(page)
                if "READING" not in last_log:
                    print(f"\n📖 READING DETECTED.")
                    last_log = "READING"

                
                # A. Time Detection (Targeted)
                wait_min = 5 # Default
                try:
                    # Strategy: Look for the time specifically inside the Content Metadata
                    # typically found near the "Reading" label or in the Item Header.
                    # We avoid scanning the whole body to prevent picking up "30 min" from a sidebar quiz.

                    found_time = None
                    
                    # 1. Metadata container with "Reading" (Most accurate)
                    # HTML structure: <div>Reading<span>10 min</span></div>
                    try:
                        # Find div containing "Reading", then get its text
                        metadata_divs = page.locator("div", has_text=re.compile(r"Reading", re.IGNORECASE)).all()
                        for div in metadata_divs:
                            if div.is_visible():
                                text = div.inner_text()
                                # Expect strict "Reading ... 10 min" pattern
                                match = re.search(r"Reading.*?(\d+)\s*min", text, re.IGNORECASE | re.DOTALL)
                                if match:
                                    found_time = int(match.group(1))
                                    print(f"   └── 🔍 Detected via Metadata: {found_time} mins")
                                    break
                    except: pass

                    # 2. Main Header (Second best)
                    if not found_time:
                         try:
                             header_text = page.locator("h1").first.inner_text()
                             # Check siblings or parent of H1 for time
                             # Often "Title (10 min)"
                             match = re.search(r"(\d+)\s*min", header_text)
                             if match:
                                 found_time = int(match.group(1))
                                 print(f"   └── 🔍 Detected via Header: {found_time} mins")
                         except: pass

                    if found_time:
                        wait_min = found_time
                        # cap removed based on user/review feedback
                    else:
                        rand_default = random.randint(7, 12)
                        print(f"   └── ⚠️ No specific time found. Defaulting to {rand_default} mins (Randomized).")
                        wait_min = rand_default

                except Exception as e:
                    print(f"   └── ⚠️ Time detection error: {e}")
                
                print(f"   └── ⏱️ Time Required: {wait_min} minutes")

                # B. Scrape Reading Content (New Feature)
                try:
                    # Selector for reading body from Plan.md
                    reading_body = page.locator("div.rc-CML")
                    if reading_body.count() > 0:
                        content = reading_body.inner_text()
                        title = page.title().split("|")[0].strip()
                        safe_title = re.sub(r'\W+', '_', title)
                        prefix = get_filename_prefix(page)
                        filepath = f"{TRANSCRIPT_DIR}/{prefix}{safe_title}_reading.txt"
                        os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
                        final_path = save_content_smart(filepath, content)
                        print(f"   └── 📝 Reading content saved: {final_path}")
                except Exception as e:
                    print(f"   └── ⚠️ Scraping failed: {e}")

                # C. Human Scrolling (With Navigation Check)
                status = random_human_scroll(page, wait_min * 60, start_context)
                
                if status == "NAVIGATED":
                    continue # Restart main loop
                
                # D. Mark Complete
                try:
                    btn = page.locator("button:has-text('Mark as completed')")
                    if btn.is_visible(): 
                        btn.click()
                        print("\n   └── ✅ Marked as Completed.")
                    else:
                        print("\n   └── ✅ Finished.")
                except: pass
                
                # Navigate
                try:
                     next_btn = page.locator("button[data-testid='next-item'], button:has-text('Go to next item')").first
                     if next_btn.is_visible(): next_btn.click()
                except: pass
                time.sleep(5)
            
            else:
                # Idle
                print(".", end="", flush=True)
                time.sleep(2)

if __name__ == "__main__":
    try:
        handle_automation()
    except KeyboardInterrupt:
        print("\n\n🛑 Script stopped by user. Exiting...")
        sys.exit(0)
