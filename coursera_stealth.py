import time
import os
import re
import random
import sys
import select
import difflib
import json
import urllib.parse
import xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright
from plyer import notification
from course_manager import CourseManager
from discover_selectors_coursera import get_detailed_course_map, get_robust_course_name

# --- CONFIGURATION ---
CDP_URL = "http://localhost:9222"
TRANSCRIPT_DIR = "coursera_transcripts"
VIDEO_COMPLETION_THRESHOLD = 100 # Percentage (0-100) to consider video watched

# Suppress Playwright/Node deprecation warnings
os.environ["NODE_OPTIONS"] = "--no-deprecation"

# GLOBAL STATE TRACKERS
current_manager = None
last_known_course = ""

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

        # Video "Reflect" / Interrupt
        # Looks for "Reflect" header or generic modal with Continue during video
        if page.locator("h1, h2, h3", has_text="Reflect").is_visible():
             print("\n   └── ⏸️ Video Interrupt (Reflect) detected. Resuming...")
             page.locator("button:has-text('Continue')").click(force=True)
             time.sleep(1)
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
    
    # 0. Focus on Main Content to avoid Sidebar Scroll
    # We want to hover over the reading text so wheel events affect the right area
    try:
        # Common containers for readings
        main_content = page.locator("div.rc-CML, main, div[role='main']").first
        if main_content.is_visible():
            main_content.hover()
            # Constrain mouse moves to this box
            box = main_content.bounding_box()
            safe_x_min = box['x'] + 20
            safe_x_max = box['x'] + box['width'] - 20
        else:
            # Fallback: Assume sidebar is left < 300px
            safe_x_min = 350
            safe_x_max = 900
    except:
        safe_x_min = 350
        safe_x_max = 900

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
            
            # STEALTH: Random mouse fidget *within content bounds*
            if random.random() < 0.4: # 40% chance
                x = random.randint(int(safe_x_min), int(safe_x_max))
                y = random.randint(200, 700)
                # steps=10+ ensures smooth movement instead of teleporting
                try: page.mouse.move(x, y, steps=random.randint(10, 20))
                except: pass
                
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
    """Extracts 'M1', 'M2' etc from the Module header that CONTAINS the current item."""
    try:
        # 1. Identify the Current Item in the Sidebar
        current_title = page.title().split("|")[0].strip()
        
        # We find the specific sidebar item that matches our title
        # using the same strict matching logic as check_completed_status
        candidates = page.locator(f"div.outline-single-item-content-wrapper", has_text=current_title).all()
        target_item = None
        
        for item in candidates:
            # Strict verification
            if item.inner_text().split('\n')[0].strip() == current_title:
                target_item = item
                break
        
        if target_item:
            # 2. Traverse Up to find the Module Panel/Region
            # The item is usually inside a div[role='region'] (the accordion panel)
            # We want to find the header associated with this panel.
            
            # Playwright doesn't have a simple "closest" locator that returns the handle easily in Python API without eval,
            # but we can try to find the 'closest' parent having "Module" text in its PREVIOUS sibling or header.
            
            # Robust Approach: Find the accordion region containing this item
            region = target_item.locator("xpath=./ancestor::div[@role='region']").first
            
            if region.is_visible():
                region_id = region.get_attribute("id")
                if region_id:
                    # Find the button that controls this region
                    header = page.locator(f"button[aria-controls='{region_id}']").first
                    if header.is_visible():
                         header_text = header.inner_text()
                         match = re.search(r"Module\s*(\d+)", header_text, re.IGNORECASE)
                         if match: return f"M{match.group(1)}_"

        # 3. Fallback: Page Title (if logic above fails)
        title_text = page.title()
        match = re.search(r"Module\s*(\d+)", title_text, re.IGNORECASE)
        if match:
             return f"M{match.group(1)}_"

    except: pass
    return "M1_" # Default

def human_click(page, locator, force=True, reaction_range=(0.4, 0.9)):
    """
    Performs a human-like click: 
    1. Smooth Mouse Glide (Steps) to localized button coordinate
    2. Reaction/Thinking Pause
    3. Final Click
    """
    try:
        if not locator.is_visible(): return False
        
        # 1. Smooth Approach (Best Effort)
        try:
            # Ensure element is in view
            locator.scroll_into_view_if_needed(timeout=2000)
            
            # Hover to trigger states (don't fail on this)
            locator.hover(force=force, timeout=2000)
            
            # Small random pause for "thought"
            time.sleep(random.uniform(*reaction_range))
        except: 
            pass # Continue to click even if hover/scroll fought back
        
        # 2. The Click (Priority)
        # Force click ensures we don't get blocked by minimal overlays
        locator.click(force=force)
        return True
    except:
        return False

def try_extract_transcript(page):
    """
    Two-stage transcript extraction:
    1. UI Scrape (Standard)
    2. Downloads Fallback (.txt file)
    """
    # Stage 1: Standard UI Scrape
    try:
        # Check if tab exists/needs clicking
        t_tab = page.locator("button:has-text('Transcript')").first
        if t_tab.is_visible():
            t_tab.click()
            time.sleep(1.5)
        
        # Look for standard containers
        page.wait_for_selector(".rc-Transcript, .rc-TranscriptHighlighter", timeout=3000)
        text = page.locator(".rc-Transcript, .rc-TranscriptHighlighter").first.inner_text()
        if text.strip():
            return text.strip(), "UI_Scrape"
    except:
        pass

    # Stage 2: Downloads Fallback (The user's reported edge case)
    try:
        d_tab = page.locator("button:has-text('Downloads')").first
        if d_tab.is_visible():
            d_tab.click()
            time.sleep(2)
            
            # Look for "Transcript" link (usually English)
            # Strategy: Find link that has 'Transcript' text and is likely a file
            transcript_link = page.locator("a:has-text('Transcript'), li:has-text('Transcript') a").first
            if transcript_link.is_visible():
                print("   └── 📥 UI Scrape failed. Attempting .txt download fallback...")
                try:
                    with page.expect_download(timeout=10000) as download_info:
                        transcript_link.click()
                    download = download_info.value
                    temp_path = download.path()
                    
                    if temp_path and os.path.exists(temp_path):
                        with open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
                            text = f.read()
                        if text.strip():
                            return text.strip(), "File_Download"
                except Exception as de:
                    print(f"   └── ⚠️ Download fallback failed: {de}")
    except:
        pass

    return None, "FAILED"

def get_next_button(page):
    """
    Robust strategy to find the 'Next' navigation button.
    Prioritizes specific data-testids, then aria-labels, then text.
    RETURNS: First *VISIBLE* matching button.
    """
    locs = [
        "button[data-testid='next-item']",
        "button[aria-label='Go to next item']", 
        "button:has-text('Go to next item')",
        "div[role='button']:has-text('Next')",
    ]
    
    # Create combined locator
    combo_loc = page.locator(", ".join(locs))
    
    # Iterate to find first VISIBLE one
    # This prevents picking a hidden 'Next' button (e.g. in a hidden video player wrapper)
    count = combo_loc.count()
    for i in range(count):
        candidate = combo_loc.nth(i)
        if candidate.is_visible():
            return candidate
            
    # Fallback
    return combo_loc.first

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
        last_action_log = "" # Tracks specific action states (VIDEO, READING, etc)
        
        # GLOBAL STATE TRACKERS (within loop context)
        current_manager = None
        last_known_course = ""

        while True:
            # --- SELF-HEALING: RECLAIM PAGE ---
            try:
                if page.is_closed():
                    print("\n⚠️ Target page closed. Scanning for active Coursera tab...")
                    found = False
                    for p_obj in context.pages:
                        if "coursera.org" in p_obj.url:
                            page = p_obj
                            page.bring_to_front()
                            print(f"✅ Re-acquired Coursera tab: {page.title()}")
                            found = True
                            break
                    if not found:
                        print("❌ No Coursera tab found. Waiting 5s...")
                        time.sleep(5)
                        continue
            except: 
                time.sleep(5)
                continue

            # STUCK DETECTION LOGIC (URL BASED)
            # Checked OUTSIDE the Try-Except block so sys.exit() works!
            try:
                # STUCK DETECTION LOGIC (URL BASED)
                # Normalize URL: Remove query params and hash using standard urllib
                parsed = urllib.parse.urlparse(page.url)
                current_url_check = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                
                # FIX: Reset counter if video is actively playing (prevent false stuck trigger on long videos)
                is_video_active = False
                try:
                    if page.locator("video").count() > 0:
                        if not page.evaluate("document.querySelector('video').paused"):
                            is_video_active = True
                except: pass

                if current_url_check == last_processed_url and not is_video_active:
                    stuck_on_item_counter += 1
                else:
                    stuck_on_item_counter = 0
                    last_processed_url = current_url_check

                if stuck_on_item_counter > 5: # ~5 loops without URL change
                     print("\n🛑 End of Course or Stuck detected (No Next Item).")
                     print("   └── Script exiting quietly to prevent log spam.")
                     sys.exit(0)
            except SystemExit: raise # Re-raise exit
            except: pass # Ignore other errors accessing page.url

            # ---------------------------------------------------------
            # 1. DYNAMIC COURSE MAPPING (Context Switcher)
            # ---------------------------------------------------------
            try:
                detected_course = get_robust_course_name(page)
                if detected_course != last_known_course and len(detected_course) > 3:
                    print(f"\n🌍 Context Switch Detected: {detected_course}")
                    msg = "Generating high-fidelity course map..."
                    print(f"   └── {msg}")
                    
                    course_map = get_detailed_course_map(page)
                    if course_map:
                        current_manager = CourseManager(course_map, detected_course)
                        last_known_course = detected_course
                        print(f"   └── 🗺️  Map Loaded. XML Ledger: {current_manager.xml_path}")
                    else:
                        print("   └── ⚠️ Map generation failed.")
            except Exception as e:
                print(f"   └── ⚠️ Mapping error: {e}")

            # 1. Context Logging
            try:
                current_context = get_page_context(page)
                if current_context != last_log:
                    print(f"\n{current_context}")
                    last_log = current_context
                    last_action_log = "" # Reset action log on new context
                     
                # 0. History Check (State Persistence)
                # Normalize URL: Remove query params and hash using standard urllib
                parsed = urllib.parse.urlparse(page.url)
                current_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                
                # Check history from Manager if available, otherwise fallback
                if current_manager and os.path.exists(current_manager.xml_path):
                    try:
                        tree = ET.parse(current_manager.xml_path)
                        for item in tree.getroot().findall(".//item"):
                            if item.get("url") == current_url: # Use == for exact match
                                content = item.find("content")
                                if content is not None and content.text:
                                    if "ALREADY_SCRAPED" not in last_action_log:
                                         print("   └── 📜 History: Item already archived in XML.")
                                         last_action_log += "ALREADY_SCRAPED"
                                    break
                    except: pass

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

            # 3. Content Detection (Safe)
            is_video = False
            is_quiz = False
            is_plugin = False
            is_assignment = False
            is_reading = False

            try:
                # Video: .rc-VideoControlsContainer OR video tag
                is_video = page.locator(".rc-VideoControlsContainer, video").count() > 0

                # Quiz Detection (Priority)
                is_quiz = page.locator(".rc-QuizApp, .rc-FormPartsQuestion, [data-testid='quiz-submit-button']").count() > 0
                if not is_quiz:
                     # Fallback: Check Title
                     if "Quiz" in page.title():
                         is_quiz = True

                try:
                    # Check for "Ungraded Plugin" text in metadata or headers
                    # CRITICAL: Scan 'main' only to avoid sidebar/nav bar matches
                    if page.locator("main", has_text="Ungraded Plugin").count() > 0 or \
                       page.locator("main", has_text="Ungraded External Tool").count() > 0:
                         is_plugin = True
                    
                    # Check for "Peer-graded Assignment", "Case Study", "Honors Assignment"
                    # Also "Review Your Peers" which often appears in 3-part peer reviews
                    title_lower = page.title().lower()
                    if any(x in title_lower for x in ["peer-graded", "peer assessment", "case study", "honors assignment", "review your peers"]):
                        is_assignment = True
                        is_plugin = True # Reuse plugin skip logic for now
                except: pass

                # Reading: .reading-title OR data-testid='cml-viewer' OR generic "Reading" pill
                # CRITICAL: We only check for reading if it is NOT a quiz OR plugin OR assignment
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
            except Exception as e:
                print(f"⚠️ Content detection error: {e}")
                time.sleep(2)
                continue

            # --- CHECK COMPLETION STATUS ---
            try:
                if (is_video or is_reading or is_plugin) and not is_quiz:
                    if check_completed_status(page):
                         user_stayed = input_with_timeout(30)
                         if not user_stayed:
                             # Skip/Navigate
                             print("   └── ⏭️ Skipping...")
                             try:
                                 next_btn = get_next_button(page)
                                 
                                 # Try Human Click
                                 if next_btn.is_visible() and human_click(page, next_btn):
                                     time.sleep(5)
                                     continue
                                 
                                 # Fallback: Map Navigation (Hacker Mode)
                                 # If button is missing or click failed, force move to next URL
                                 print("   └── ⚠️ Click failed/Button missing. Attempting Map Fallback...")
                                 if current_manager:
                                     next_url = current_manager.get_next_url(page.url)
                                     if next_url:
                                         print(f"   └── 🧭 Map Navigate -> {next_url}")
                                         page.goto(next_url)
                                         time.sleep(5)
                                         continue
                             except: pass
                             
                             time.sleep(2)
                             continue
            except Exception as e:
                print(f"⚠️ Completion check error: {e}")
                time.sleep(2)

            # --- HANDLERS ---
            
            if is_plugin:
                 if "PLUGIN" not in last_action_log:
                     print(f"\n🧩 UNGRADED PLUGIN/RESOURCE DETECTED.")
                     last_action_log += "PLUGIN"
                 
                 # Attempt to Mark Complete (Resource) or Next
                 try:
                     mark_btn = page.locator("button:has-text('Mark as completed')").first
                     
                     if mark_btn.is_visible():
                         # It's a resource/case study that requires "reading"
                         print("   └── 📖 Resource detected (has completion button). Simulating activity...")
                         
                         # Grab context for the scroll function
                         current_context = get_page_context(page)
                         
                         # Simulate reading for 15-30 seconds
                         random_human_scroll(page, random.randint(15, 30), current_context)
                         
                         if mark_btn.is_visible():
                             mark_btn.click()
                             print("   └── ✅ Marked as Completed.")
                             time.sleep(2)
                     else:
                         # No mark button, probably distinct tool or purely optional
                         print("   └── Skipping external tool/survey...")

                     next_btn = get_next_button(page)
                     if next_btn.is_visible():
                         human_click(page, next_btn)
                         time.sleep(5)
                 except: pass
                 time.sleep(2)
                 continue

            if is_quiz:
                try:
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
                        if "QUIZ" not in last_action_log:
                            print(f"\n🛑 GRADED QUIZ DETECTED.")
                            print("   └── Actions paused. Please solve manually.")
                            try: notification.notify(title="Coursera Bot", message="Graded Quiz detected!")
                            except: pass
                            last_action_log += "QUIZ"
                        
                        # Pause until cleared
                        while page.locator(".rc-QuizApp, .rc-FormPartsQuestion").count() > 0:
                            time.sleep(2)
                        print("✅ Quiz cleared. Resuming...")
                        continue
                    else:
                        # Non-Graded (Practice/Orientation)
                        if "SKIP_QUIZ" not in last_action_log:
                            print(f"\n⚠️ Non-Graded Quiz Detected (Orientation/Practice).")
                            print("   └── Attempting to Skip/Next...")
                            last_action_log += "SKIP_QUIZ"
                        
                        try:
                            next_btn = get_next_button(page)
                            
                            # Try Human Click
                            if next_btn.is_visible() and human_click(page, next_btn):
                                time.sleep(5)
                                continue
                                
                            # Fallback: Map Navigation (Hacker Mode)
                            print("   └── ⚠️ Quiz Skip Button missing/failed. Attempting Map Fallback...")
                            if current_manager:
                                next_url = current_manager.get_next_url(page.url)
                                if next_url:
                                    print(f"   └── 🧭 Map Navigate -> {next_url}")
                                    page.goto(next_url)
                                    time.sleep(5)
                                    continue

                            # Last Resort: Mark Complete
                            mark_btn = page.locator("button:has-text('Mark as completed')").first
                            if mark_btn.is_visible(): mark_btn.click()
                        except: pass
                        time.sleep(2)
                        continue
                except Exception as e:
                    print(f"   └── ⚠️ Quiz handler error: {e}")
                    time.sleep(2)
                    continue

            elif is_video:
                try:
                    if "VIDEO" not in last_action_log:
                        print(f"\n🎥 VIDEO DETECTED.")
                        last_action_log += "VIDEO"
                    
                    # Capture start context for navigation check
                    start_context = get_page_context(page)

                    # A. Extract Transcript (Robust 2-Stage)
                    transcript_text, method = try_extract_transcript(page)
                    if transcript_text:
                        title = page.title().split("|")[0].strip()
                        if current_manager:
                            fname, ok = current_manager.save_content(page.url, transcript_text, "Transcript")
                            print(f"   └── 💾 Archived ({method}): {fname} (XML OK: {ok})")
                        else:
                            safe_title = re.sub(r'\W+', '_', title)
                            filepath = f"{TRANSCRIPT_DIR}/{safe_title}_transcript.txt"
                            save_content_smart(filepath, transcript_text)
                    else:
                        # Final notification if BOTH failed
                        print(f"   └── ⚠️ Transcript extraction failed.")

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
                    paused_counter = 0
                    
                    # We wait for the "Go to next item" button to be ENABLED and VISIBLE
                    # Or for the video 'ended' even
                    while True:
                        # CHECK FOR USER NAVIGATION
                        if get_page_context(page) != start_context:
                            print("\n🛑 User navigated away! Aborting video match.")
                            break

                        # Check for "Reflect" or other Modals blocking playback
                        check_and_handle_modal(page)

                        # --- AUTO-RESUME CHECK ---
                        try:
                            is_paused = page.evaluate("document.querySelector('video').paused")
                            if is_paused:
                                paused_counter += 1
                                if paused_counter > 30:
                                    print(f"\n   └── ⚠️ Auto-resume: Video was stuck paused for 30s. Forcing play.")
                                    page.evaluate("document.querySelector('video').play()")
                                    paused_counter = 0
                            else:
                                paused_counter = 0
                        except: pass

                        # Monitor Progress & Completion
                        try:
                            curr = page.locator(".current-time-display").first.inner_text()
                            total = page.locator(".duration-display").first.inner_text()
                            
                            curr_sec = parse_time_to_seconds(curr)
                            total_sec = parse_time_to_seconds(total)
                            prog = 0
                            
                            if total_sec > 0:
                                prog = (curr_sec / total_sec) * 100
                                
                                # Dynamic Threshold: Randomize "done" state between 97.0% and 100.0%
                                completion_target = local_video_target if 'local_video_target' in locals() else round(random.uniform(97.0, 100.0), 2)
                                local_video_target = completion_target # Persist
                                
                                # STEALTH: "Fidget" mouse randomly to simulate attention
                                if random.random() < 0.3: # 30% chance per loop
                                    x = random.randint(100, 700)
                                    y = random.randint(100, 500)
                                    try: page.mouse.move(x, y, steps=random.randint(5, 12))
                                    except: pass

                                # Interactive bar
                                bar_len = 20
                                filled = int(bar_len * prog / 100)
                                bar = "█" * filled + "░" * (bar_len - filled)
                                print(f"\r   └── 🎥 Watch: [{bar}] {prog:.1f}% (Target: >{completion_target}%)", end="")
                                
                                if prog >= completion_target:
                                     print(f"\n   └── ✅ Target Reached (> {completion_target}%). Simulating reaction time...")
                                     time.sleep(random.uniform(2, 4))
                                     break

                            # CRITICAL: Only trust "Next" button if we have watched most of the video
                            # or if the video is natively ended.
                            is_ended = page.evaluate("document.querySelector('video').ended")
                            
                            # Stricter >= THRESHOLD or native end
                            # Note: We subtract a small buffer (e.g. 0.5%) for float imprecision if purely time-based,
                            # but simple >= matches user intent.
                            if is_ended or prog >= completion_target:
                                 print("\n   └── ✅ Video Complete (Progress/Ended).")
                                 break
                                 
                            # Check Next Button (But only if we are close to end)
                            # Some courses show "Next" immediately. We must ignore it until we are done.
                            # Check Next Button (Strict > Threshold - small buffer for rounding)
                            if prog >= (completion_target - 0.5): # Allow 1% buffer for rounding (e.g. 99% if 100)
                                next_btn = get_next_button(page)
                                if next_btn.is_visible() and next_btn.is_enabled():
                                     print(f"\n   └── ✅ Video Complete (Button Enabled & >{completion_target-1}%).")
                                     human_click(page, next_btn)
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
                    navigated = False
                    try:
                        # Only click if we didn't abort
                        if get_page_context(page) == start_context:
                            next_btn = get_next_button(page)
                            
                            # Try Human Click
                            if next_btn.is_visible() and human_click(page, next_btn, reaction_range=(0.6, 1.4)):
                                navigated = True
                    except: pass

                    # Hacker Fallback: Map-based Navigation
                    if not navigated and current_manager:
                        print("   └── ⚠️ Video Nav failed. Attempting Map Fallback...")
                        next_url = current_manager.get_next_url(page.url)
                        if next_url:
                            print(f"   └── 🧭 Map Navigate -> {next_url}")
                            page.goto(next_url)
                            time.sleep(5)
                    
                    time.sleep(5)
                except Exception as e:
                    print(f"   └── ⚠️ Video handler error: {e}")
                    time.sleep(2)
                    continue


            elif is_reading:
                try:
                    start_context = get_page_context(page)
                    if "READING" not in last_action_log:
                        print(f"\n📖 READING DETECTED.")
                        last_action_log += "READING"

                    
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
                    
                    # Apply Stealth Randomization (97% - 100% of the stated time)
                    # This mimics a human finishing slightly early or right on time
                    completion_factor = random.uniform(0.97, 1.0)
                    wait_sec = int(wait_min * 60 * completion_factor)
                    print(f"   └── ⏳ Reading for {wait_sec//60}m {wait_sec%60}s (Factor: {completion_factor:.2%})")
                    
                    # B. Scrape Reading Content (Structured)
                    try:
                        reading_body = page.locator("div.rc-CML")
                        if reading_body.count() > 0:
                            content = reading_body.inner_text()
                            if current_manager:
                                fname, ok = current_manager.save_content(page.url, content, "Reading")
                                print(f"   └── 💾 Archived: {fname} (XML OK: {ok})")
                            else:
                                title = page.title().split("|")[0].strip()
                                safe_title = re.sub(r'\W+', '_', title)
                                filepath = f"{TRANSCRIPT_DIR}/{safe_title}_reading.txt"
                                save_content_smart(filepath, content)
                    except Exception as e:
                        print(f"   └── ⚠️ Scraping failed: {e}")

                    # C. Human Scrolling (With Navigation Check)
                    status = random_human_scroll(page, wait_sec, start_context)
                    
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
                         next_btn = get_next_button(page)
                         if next_btn.is_visible(): human_click(page, next_btn)
                    except: pass
                    time.sleep(5)
                except Exception as e:
                     print(f"   └── ⚠️ Reading handler error: {e}")
                     time.sleep(2)
                     continue
            
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
