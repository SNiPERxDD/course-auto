import time
import json
import yaml
import os
import sys
import shutil
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
CDP_URL = "http://localhost:9222"
CONFIG_FILE = "config.yaml"

# Suppress Playwright/Node deprecation warnings (Internal to Node driver)
os.environ["NODE_OPTIONS"] = "--no-deprecation"

# Core types we aim to verify, but we'll filter this based on actual course content
CORE_TYPES = ["VIDEO", "READING", "QUIZ", "ASSIGNMENT", "LAB"]
GLOBAL_REQUIRED_TYPES = set() 

# Items to ignore when marking types as 'discovered'
FILLER_KEYWORDS = ["how was the course", "course farewell", "please tell us about yourself", "survey"]

# Targeted Elements based on Plan.md and Coursera UI patterns
ELEMENTS_SCHEMA = {
    "course_metadata": {
        "course_name": {
            "selectors": [
                "a[title*='Home Page']", 
                "a.cds-150", 
                "a.cds-341.css-yrq2q5",
                "nav[aria-label='Breadcrumbs'] li:first-child"
            ],
            "description": "The main course title link"
        },
        "module_name": {
            "selectors": [
                "button.cds-AccordionHeader-button[aria-expanded='true'] span",
                "nav[aria-label='Breadcrumbs'] li:last-child",
                "span.css-6ecy9b"
            ],
            "description": "Current active module header"
        }
    },
    "video_controls": {
        "play_button": {
            "selectors": [
                "button[aria-label='Play']",
                "button[data-testid='play-button']",
                "svg[data-testid='PlayArrowSvg']"
            ],
            "description": "Video play/pause trigger"
        },
        "current_time": {
            "selectors": [
                "span.current-time-display",
                "span[aria-label='Video Progress']",
                "div[role='slider']"
            ],
            "description": "Current playback timestamp"
        },
        "duration": {
            "selectors": [
                "span.duration-display",
                "div.video-player-progress-bar span:last-child"
            ],
            "description": "Total video length"
        },
        "mute_button": {
            "selectors": [
                "button[aria-label='Mute']",
                "button[aria-label='Unmute']",
                "svg[data-testid='VolumeUpSvg']"
            ],
            "description": "Audio toggle"
        }
    },
    "content": {
        "transcript_container": {
            "selectors": [
                ".rc-Transcript",
                ".rc-TranscriptHighlighter",
                "button:has-text('Transcript')"
            ],
            "description": "Interactive transcript area"
        },
        "downloads_tab": {
            "selectors": [
                "button:has-text('Downloads')",
                "[data-testid='downloads-tab']",
                "a:has-text('Downloads')"
            ],
            "description": "Tab for downloading lesson assets"
        },
        "transcript_download_link": {
            "selectors": [
                "a:has-text('Transcript')",
                "li:has-text('Transcript') a",
                "a:has-text('.txt')"
            ],
            "description": "Link to download the transcript file"
        },
        "reading_body": {
            "selectors": [
                "div.rc-ReadingItemDisplay",
                "div.rc-CML",
                "div[role='presentation']",
                "[data-testid='cml-viewer']"
            ],
            "description": "Main reading text container"
        }
    },
    "navigation": {
        "next_item": {
            "selectors": [
                "button[aria-label='Go to next item']",
                "button[data-testid='next-item']",
                "button:has-text('Go to next item')"
            ],
            "description": "Button to advance to next lesson"
        },
        "mark_complete": {
            "selectors": [
                "button[data-testid='mark-complete']",
                "button:has-text('Mark as completed')"
            ],
            "description": "Reading completion button"
        },
        "completed_stamp": {
            "selectors": [
                "a[aria-label*='Completed']",
                "h3:has-text('Completed')"
            ],
            "description": "Visual confirmation of completion"
        }
    },
    "sidebar": {
        "success_icon": {
            "selectors": [
                "[data-testid='learn-item-success-icon']"
            ],
            "description": "Green checkmark in sidebar"
        }
    }
}

def load_config():
    """Loads existing config.yaml if it exists."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return yaml.safe_load(f) or {}
        except: pass
    return {}

def get_robust_module_name(page):
    """
    Hierarchical module name detection to avoid false positives.
    Uses expanded accordion first, then page text search.
    """
    try:
        # 1. Primary: The expanded accordion header in the sidebar
        header = page.locator("button.cds-AccordionHeader-button[aria-expanded='true'] span").first
        if header.count() > 0 and header.is_visible():
            text = header.inner_text().strip()
            if text and "module" in text.lower(): return text

        # 2. Fallback: Specific breadcrumb or header patterns
        patterns = [
            "nav[aria-label='Breadcrumbs'] li:last-child",
            "h2.cds-119",
            "span:has-text('Module')"
        ]
        for p in patterns:
            loc = page.locator(p).first
            if loc.count() > 0 and loc.is_visible():
                text = loc.inner_text().strip()
                if text and len(text) > 3: return text

    except: pass
    return "Unknown Module"

def find_element_in_frames(page, selector):
    """Searches main page and all iframes for a selector."""
    try:
        # Check main page
        loc = page.locator(selector).first
        if loc.count() > 0 and loc.is_visible():
            return loc, "main"
        
        # Check all frames
        for frame in page.frames:
            try:
                loc = frame.locator(selector).first
                if loc.count() > 0: # Note: visibility check can be tricky in frames
                    return loc, f"frame[{frame.name or frame.url[:30]}]"
            except: continue
    except: pass
    return None, None

def backup_config():
    """Copies current config.yaml to deleted/ with a timestamp."""
    if os.path.exists(CONFIG_FILE):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = "deleted"
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            backup_path = os.path.join(backup_dir, f"config_backup_{timestamp}.yaml")
            shutil.copy2(CONFIG_FILE, backup_path)
        except Exception as e:
            print(f"⚠️  Backup failed: {e}")

def detect_page_type(page):
    """Detects if the page is a Lecture (Video), Supplement (Reading), or Quiz."""
    url = page.url.lower()
    title = page.title().lower()
    
    # Core technical markers based on URL
    if "/lecture/" in url: return "VIDEO"
    if "/supplement/" in url: return "READING"
    if "/quiz/" in url or "/exam/" in url: return "QUIZ"
    if "/ungradedlab/" in url or "/programming/" in url or "/ungradedwidget/" in url: return "LAB"
    if "/peer/" in url: return "ASSIGNMENT"
    if "/discussion/" in url: return "DISCUSSION"
    if "/wrapup/" in url: return "WRAPUP"

    # Secondary markers based on title
    if "quiz" in title or "exam" in title: return "QUIZ"
    if "assignment" in title or "review your peers" in title: return "ASSIGNMENT"
    if "forum" in title: return "DISCUSSION"
    if "congratulations" in title or "course farewell" in title: return "WRAPUP"
    if "survey" in title or "how was the course" in title: return "SURVEY"
    
    # Check for filler content last
    for kw in FILLER_KEYWORDS:
        if kw in title:
            return "FILLER"
    
    return "UNKNOWN"

def get_robust_course_name(page):
    """Tries various selectors to find the Course Name."""
    selectors = [
        "a[title*='Home Page']", 
        "a.cds-150", 
        "a.cds-341.css-yrq2q5",
        "nav[aria-label='Breadcrumbs'] li:first-child",
        "h1"
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                text = loc.inner_text().strip() or loc.get_attribute("title")
                if text and len(text) > 2:
                    return text.replace("\n", " ")
        except: pass
    return "Course"

def auto_hop_next(page, config):
    """Attempts to automatically navigate to the next item."""
    print("[NAVIGATE] Preparing for Auto-Hop...")
    time.sleep(5) # Give user 5 seconds to see highlights before jumping
    
    # 1. Look for 'Next' button in config or schema
    next_selectors = config.get("navigation", {}).get("next_item", [])
    if isinstance(next_selectors, str): next_selectors = [next_selectors]
    
    # Flatten list of lists if needed
    for selector in next_selectors:
        try:
            loc, loc_type = find_element_in_frames(page, selector)
            if loc:
                print(f"[ACTION] Clicking 'Next' [{selector}] ({loc_type})")
                loc.click()
                return True
        except: continue
    
    # 2. Fallback: Search for any button with 'Next' text
    try:
        next_btn = page.locator("button:has-text('Next'), button[aria-label*='next']").first
        if next_btn.count() > 0 and next_btn.is_visible():
            print("[ACTION] Clicking fallback 'Next' button")
            next_btn.click()
            return True
    except: pass

    print("[WARN] Auto-Hop failed: 'Next' button not found.")
    return False

def verify_scraping(page, selector, el_name):
    """Performs a test scrape to verify the selector actually works."""
    try:
        loc, _ = find_element_in_frames(page, selector)
        if loc:
            text = loc.inner_text().strip()
            if text:
                preview = text[:150].replace('\n', ' ') + "..."
                print(f"  [SCRAPE OK] {el_name}: \"{preview}\"")
                return True
            else:
                print(f"  [SCRAPE WARN] {el_name}: No text content found.")
    except Exception as e:
        print(f"  [SCRAPE FAIL] {el_name}: {e}")
    return False

def expand_sidebar(page):
    """Finds and clicks all collapsed module accordions in the sidebar."""
    try:
        # Coursera uses cds-AccordionHeader-button
        collapsed = page.locator("button.cds-AccordionHeader-button[aria-expanded='false']")
        count = collapsed.count()
        if count > 0:
            print(f"[ACTION] Expanding {count} collapsed modules for global discovery...")
            # Click them one by one
            for i in range(count):
                try:
                    # After clicking one, the DOM might shift, so we always grab the 'first' collapsed one
                    btn = page.locator("button.cds-AccordionHeader-button[aria-expanded='false']").first
                    if btn.count() > 0:
                        btn.click()
                        time.sleep(0.5) 
                except: continue
            return True
    except: pass
    return False

def get_detailed_course_map(page):
    """
    Builds a hierarchical map of the course using a flat-list traversal.
    Structure: { ModuleName: [(LessonName, Type, URL), ...] }
    """
    course_map = {}
    try:
        # 1. Wait for sidebar content to exist
        try:
            page.wait_for_selector("a[href*='/learn/']", timeout=10000)
        except: pass

        # 2. Expand all modules
        expand_sidebar(page)
        time.sleep(1) 
        
        # 3. Get all relevant items in order (headers and links)
        # Use a broad selector for headers to catch various Coursera layouts
        items = page.locator("button.cds-AccordionHeader-button, h2, h3, a[aria-label][href*='/learn/']")
        count = items.count()
        
        if count == 0:
            return {}

        current_module = "Course Highlights"
        lessons = []
        
        for i in range(count):
            item = items.nth(i)
            tag = item.evaluate("el => el.tagName")
            
            # Module Header?
            if tag in ["BUTTON", "H2", "H3"]:
                header_text = item.inner_text().strip()
                if not header_text: continue
                # Basic check: if it's too short, it might not be a real header
                if len(header_text) < 3: continue
                
                # If we have lessons from previous group, save them
                if lessons:
                    course_map[current_module] = lessons
                
                current_module = header_text.split('\n')[0]
                lessons = []
            elif tag == "A":
                # Lesson link
                href = item.get_attribute("href")
                label = (item.get_attribute("aria-label") or "").lower()
                
                full_text = item.inner_text().strip()
                
                # If we got no text, it might be lazy loading - scroll it and try once more
                if not full_text:
                    try:
                        item.scroll_into_view_if_needed()
                        time.sleep(0.5)
                        full_text = item.inner_text().strip()
                    except: pass

                lines = [l.strip() for l in full_text.split('\n') if l.strip()]
                
                text = lines[0] if lines else "Untitled"
                subtext = lines[1].lower() if len(lines) > 1 else ""
                
                # Identify type: Prioritize visible subtext, then fallback to label
                item_type = "UNKNOWN"
                if "video" in subtext or "video" in label: 
                    item_type = "VIDEO"
                elif "reading" in subtext or "reading" in label: 
                    item_type = "READING"
                elif "quiz" in subtext or "quiz" in label or "assignment" in subtext or "assignment" in label: 
                    item_type = "QUIZ"
                elif "plugin" in subtext or "lab" in subtext or "plugin" in label or "lab" in label: 
                    item_type = "LAB"
                elif "peer" in subtext or "peer" in label: 
                    item_type = "ASSIGNMENT"
                
                # Check for filler in title or subtext
                # ONLY mark as filler if it's not a core content type or contains specific survey keywords
                for kw in FILLER_KEYWORDS:
                    if kw in text.lower() or kw in subtext:
                        # If it's a core type but also has a filler keyword (like 'Congratulations Video')
                        # we still treat it as the core type so it counts for discovery, 
                        # UNLESS it's explicitly a survey/feedback.
                        if "survey" in text.lower() or "how was the course" in text.lower():
                            item_type = "FILLER"
                        break

                # Identify duration (e.g., "15 min", "1h 10m")
                duration = ""
                # Search for digits followed by min or bits of time in full text
                time_match = re.search(r"(\d+\s*h\s*\d+\s*min|\d+\s*h|\d+\s*min|\d+\s*m)", full_text.lower())
                if time_match:
                    duration = time_match.group(0).strip()

                if href and (text, item_type, href, duration) not in lessons:
                    lessons.append((text, item_type, href, duration))
            
        if lessons:
            course_map[current_module] = lessons
            
    except Exception as e:
        print(f"[DEBUG] Map generation failed: {e}")
    return course_map

def print_course_map(course_map, course_title="Course"):
    """Prints a clean, tree-like terminal representation of the course structure."""
    if not course_map:
        print("[WARN] Course map is empty or could not be parsed.")
        return

    print("\n" + "╔" + "═"*68 + "╗")
    
    # Header Line 1: Title
    title_label = "GLOBAL COURSE STRUCTURE"
    pad1 = (68 - len(title_label)) // 2
    print("║" + " "*pad1 + title_label + " "*(68-len(title_label)-pad1) + "║")
    
    # Header Line 2: Course Name
    c_line = f"  TARGET: {course_title.upper()}"
    if len(c_line) > 66: c_line = c_line[:63] + "..."
    print(f"║{c_line}{' '*(68-len(c_line))}║")
    
    print("╠" + "═"*68 + "╣")
    
    m_list = list(course_map.items())
    for i, (mod, lessons) in enumerate(m_list):
        is_last_m = (i == len(m_list) - 1)
        m_prefix = "╚══" if is_last_m else "╠══"
        print(f"║ {m_prefix} 📦 {mod}")
        
        l_list = lessons
        for j, (title, itype, _, duration) in enumerate(l_list):
            is_last_l = (j == len(l_list) - 1)
            # Use vertical bar continuation for non-last modules
            v_bar = "    " if is_last_m else "║   "
            l_prefix = "└──" if is_last_l else "├──"
            
            icon = "🎬" if itype == "VIDEO" else "📖" if itype == "READING" else "📝" if itype == "QUIZ" else "💻" if itype == "LAB" else "🤝" if itype == "ASSIGNMENT" else "❓"
            
            # Print title and append duration if found
            line_content = f"{title[:50]}"
            if duration:
                line_content += f" ({duration})"
                
            print(f"║ {v_bar}{l_prefix} {icon} [{itype:10}] {line_content}")
            
    print("╚" + "═"*68 + "╝\n")

def get_sidebar_targets(page, force_print=False):
    """Scans the sidebar globally to find URLs for all core lesson types."""
    global GLOBAL_REQUIRED_TYPES
    targets = {}
    
    # 1. Expand and Map
    course_map = get_detailed_course_map(page)
    course_title = get_robust_course_name(page)
    
    # 2. Print summary if forced or's first time
    if force_print or not hasattr(get_sidebar_targets, "_printed"):
        print_course_map(course_map, course_title)
        setattr(get_sidebar_targets, "_printed", True)

    # 3. Extract targets and dynamically build REQUIRED_TYPES
    found_types = set()
    for mod, lessons in course_map.items():
        for _, itype, href, _ in lessons:
            if itype in CORE_TYPES:
                found_types.add(itype)
                if itype not in targets:
                    targets[itype] = href
    
    # Filter global requirement to only what's actually in the course
    GLOBAL_REQUIRED_TYPES = found_types
    print(f"[INFO] Dynamic Exit Targets: {sorted(list(GLOBAL_REQUIRED_TYPES))}")
    
    return targets

def auto_hop_smart(page, config, discovered_types):
    """Navigates intelligently via sidebar to find missing types."""
    print("\n[SMART-NAV] Analyzing sidebar for missing content types...")
    
    targets = get_sidebar_targets(page)
    missing = [t for t in GLOBAL_REQUIRED_TYPES if t not in discovered_types]
    
    if not missing:
        print("[SUCCESS] All core content types verified.")
        return False

    for mtype in missing:
        if mtype in targets:
            url = targets[mtype]
            print(f"[NAVIGATE] Target Found: {mtype}. Jumping to {url}...")
            page.goto(f"https://www.coursera.org{url}" if url.startswith("/") else url)
            return True

    print(f"[INFO] Missing {missing}. No direct sidebar path found. Using 'Next' button...")
    return auto_hop_next(page, config)

def discover_selectors(page, existing_config, discovered_types):
    """Refined discovery logic with professional logging and interactive confirmation."""
    print(f"\n[SCANNING] {page.title()} | {page.url[:60]}...")
    print("-" * 60)

    course_name_val = "N/A"
    course_sel = existing_config.get("course_metadata", {}).get("course_name", "a[title*='Home Page']")
    try:
        loc = page.locator(course_sel).first
        if loc.count() > 0: course_name_val = loc.inner_text().strip() or loc.get_attribute("title")
    except: pass
    
    module_name_val = get_robust_module_name(page)
    page_type = detect_page_type(page)
    
    print(f"COURSE: {course_name_val}")
    print(f"MODULE: {module_name_val}")
    print(f"TYPE:   {page_type}")

    # Update discovered checklist early to ensure exit logic progress
    if page_type != "UNKNOWN" and page_type != "FILLER":
        discovered_types.add(page_type)

    current_findings = {}
    pending_updates = False

    for category, elements in ELEMENTS_SCHEMA.items():
        current_findings[category] = existing_config.get(category, {})
        category_header_printed = False
        
        for el_name, el_info in elements.items():
            target_selector = None
            location_type = "main"

            for selector in el_info["selectors"]:
                loc, loc_type = find_element_in_frames(page, selector)
                if loc:
                    target_selector = selector
                    location_type = loc_type
                    
                    if location_type == "main":
                        try:
                            page.evaluate("(sel) => { \
                                const el = document.querySelector(sel); \
                                if(el) { \
                                    el.style.outline = '4px solid #00FFFF'; \
                                    el.style.boxShadow = '0 0 10px #00FFFF'; \
                                    setTimeout(() => { el.style.outline = ''; el.style.boxShadow = ''; }, 2000); \
                                } \
                            }", target_selector)
                        except: pass
                    break
            
            if target_selector:
                old_val = current_findings[category].get(el_name)
                if old_val and old_val != target_selector:
                    if not category_header_printed:
                        print(f"\n[{category.upper()}] updates:")
                        category_header_printed = True
                    print(f"  [MODIFIED] {el_name}: {old_val} -> {target_selector} ({location_type})")
                    if category in ["content", "course_metadata"]:
                        verify_scraping(page, target_selector, el_name)
                    current_findings[category][el_name] = target_selector
                    pending_updates = True
                elif not old_val or old_val == "NOT_FOUND_YET":
                    if not category_header_printed:
                        print(f"\n[{category.upper()}] new findings:")
                        category_header_printed = True
                    print(f"  [NEW] {el_name}: {target_selector} ({location_type})")
                    if category in ["content", "course_metadata"]:
                        verify_scraping(page, target_selector, el_name)
                    current_findings[category][el_name] = target_selector
                    pending_updates = True
                

    if pending_updates:
        print("\n[ACTION] Auto-updating config.yaml with new selectors.")
        backup_config()
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(current_findings, f, sort_keys=False)
        print("[OK] Configuration updated and backed up.")
    else:
        print("\n[OK] Selectors are stable. No changes needed.")

    print("\n[INFO] Pause for inspection (5s)...")
    time.sleep(5)

    continuing = auto_hop_smart(page, current_findings, discovered_types)
    return current_findings, discovered_types, continuing

def start_dynamic_observation():
    print(f"[CDP] Connecting to {CDP_URL}...")
    print("[INFO] Script observation active. Smart-Hop navigation engaged.")
    print("[EXIT] Press Ctrl+C to disconnect.")
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            context = browser.contexts[0]
            
            last_url = ""
            config = load_config()
            discovered_types = set()

            while True:
                page = None
                for p_obj in context.pages:
                    if "coursera.org" in p_obj.url:
                        page = p_obj
                        break
                
                if page:
                    # INITIAL STEP: If we haven't mapped yet, do it now
                    if not hasattr(get_sidebar_targets, "_printed"):
                        print("[INFO] Performing initial course mapping...")
                        get_sidebar_targets(page, force_print=True)

                    current_url = page.url.split('?')[0].split('#')[0]
                    if current_url != last_url:
                        target_url = current_url
                        # Ensure page is somewhat loaded
                        time.sleep(4) 
                        config, discovered_types, continuing = discover_selectors(page, config, discovered_types)
                        last_url = target_url
                        
                        if not continuing:
                            print("\n[COMPLETE] Discovery objective achieved. Closing session.")
                            break
                        
                        # Completion check for parallel loop
                        missing = [t for t in GLOBAL_REQUIRED_TYPES if t not in discovered_types]
                        if not missing and GLOBAL_REQUIRED_TYPES:
                            print("\n[COMPLETE] All identified course types verified. Closing session.")
                            break
                else:
                    if last_url != "WAITING":
                        print("\n[STATUS] Waiting for Coursera tab...")
                        last_url = "WAITING"
                
                time.sleep(2)

        except KeyboardInterrupt:
            print("\n[ABORT] Session terminated by user.")
        except Exception as e:
            print(f"[CRITICAL] Session error: {e}")
        finally:
            print("[FINISH] Discovery process stopped.")

if __name__ == "__main__":
    # Ensure pyyaml dependency
    try: import yaml
    except ImportError:
        import os, sys
        os.system(sys.executable + " -m pip install pyyaml")
        import yaml

    start_dynamic_observation()
