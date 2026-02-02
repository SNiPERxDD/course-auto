import time
import os
import re
import random
import sys
import argparse
import urllib.parse
from playwright.sync_api import sync_playwright
from course_manager import CourseManager
from discover_selectors_coursera import get_detailed_course_map, get_robust_course_name

# --- CONFIGURATION ---
CDP_URL = "http://localhost:9222"
os.environ["NODE_OPTIONS"] = "--no-deprecation"

def check_and_handle_modal(page):
    """Checks for and handles common modals (Honor Code, Polls) during archival."""
    try:
        if page.locator("h2, h1", has_text="Coursera Honor Code").is_visible():
            print("   └── 🛡️ Honor Code detected. Accepting...")
            page.locator("button:has-text('Continue')").click(force=True)
            time.sleep(1)

        if page.locator("h1, h2, h3", has_text="Reflect").is_visible():
             print("   └── ⏸️ Video Interrupt detected. Resuming...")
             page.locator("button:has-text('Continue')").click(force=True)
             time.sleep(1)
             
        # Generic "Continue" buttons that might block visibility
        continue_btn = page.locator("button:has-text('Continue')").first
        if continue_btn.is_visible():
            continue_btn.click()
            time.sleep(1)
    except: pass

def scrape_video(page, manager):
    """Scrapes video transcript."""
    try:
        # Toggle transcript if not visible
        transcript_btn = page.locator("button:has-text('Transcript')").first
        if transcript_btn.is_visible():
            transcript_btn.click()
            time.sleep(1)
        
        page.wait_for_selector(".rc-Transcript, .rc-TranscriptHighlighter", timeout=8000)
        transcript_text = page.locator(".rc-Transcript, .rc-TranscriptHighlighter").first.inner_text()
        
        if len(transcript_text.strip()) > 50:
            fname, ok = manager.save_content(page.url, transcript_text, "Transcript")
            print(f"   └── ✅ Archived Transcript: {fname}")
            return True
    except Exception as e:
        print(f"   └── ⚠️ Transcript scrape failed: {e}")
    return False

def scrape_reading(page, manager):
    """Scrapes reading content."""
    try:
        page.wait_for_selector("div.rc-CML", timeout=8000)
        reading_body = page.locator("div.rc-CML")
        if reading_body.count() > 0:
            content = reading_body.inner_text()
            if len(content.strip()) > 20:
                fname, ok = manager.save_content(page.url, content, "Reading")
                print(f"   └── ✅ Archived Reading: {fname}")
                return True
    except Exception as e:
        print(f"   └── ⚠️ Reading scrape failed: {e}")
    return False

def run_archiver(force=False):
    print("🚀 Initializing Dedicated Coursera Archiver...")
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            context = browser.contexts[0]
            
            # Find/Ensure Coursera Tab
            page = None
            for p_obj in context.pages:
                if "coursera.org" in p_obj.url:
                    page = p_obj
                    page.bring_to_front()
                    break
            
            if not page:
                print("❌ No Coursera tab found. Please open Coursera in Chrome (9222).")
                return

            # 1. Map the Course
            course_name = get_robust_course_name(page)
            print(f"🌍 Targeted Course: {course_name}")
            
            print("🔍 Generating global course map (this may take a moment)...")
            course_map = get_detailed_course_map(page)
            if not course_map:
                print("❌ Global discovery failed. Aborting.")
                return

            manager = CourseManager(course_map, course_name)
            print(f"📂 Archiving to: {manager.root_dir}")
            print(f"📄 Ledger: {manager.xml_path}")
            print("-" * 50)

            # 2. Iterate Strategy
            targets = []
            for module_name, lessons in course_map.items():
                for title, l_type, url, duration in lessons:
                    if l_type in ["VIDEO", "READING"]:
                        targets.append((title, l_type, url))

            print(f"🎯 Total High-Value Targets: {len(targets)}")
            
            for i, (title, l_type, url) in enumerate(targets, 1):
                full_url = f"https://www.coursera.org{url}"
                
                # Resumption Check
                rel_url = url.split("?")[0].split("#")[0]
                is_archived = False
                
                if not force:
                    # 1. Check XML Ledger
                    if os.path.exists(manager.xml_path):
                        import xml.etree.ElementTree as ET
                        try:
                            tree = ET.parse(manager.xml_path)
                            for item in tree.getroot().findall(".//item"):
                                if item.get("url") == rel_url:
                                    content_node = item.find("content")
                                    if content_node is not None and content_node.text and len(content_node.text.strip()) > 0:
                                        is_archived = True
                                        break
                        except: pass
                    
                    # 2. Check Physical Filesystem (Backup check)
                    if not is_archived:
                        m_idx, l_idx, s_title, _ = manager.resolve_location(full_url)
                        if m_idx > 0:
                            content_type = "Transcript" if l_type == "VIDEO" else "Reading"
                            prefix = f"M{m_idx:02d}_L{l_idx:02d}"
                            filename = f"{prefix}_{s_title}_{content_type}.txt"
                            file_path = os.path.join(manager.root_dir, filename)
                            if os.path.exists(file_path) and os.path.getsize(file_path) > 20:
                                is_archived = True

                if is_archived:
                    print(f"[{i}/{len(targets)}] ⏩ Skipping (Already Archived): {title}")
                    continue

                print(f"[{i}/{len(targets)}] 📡 Navigating to: {title} ({l_type})")
                try:
                    page.goto(full_url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(random.uniform(2, 4)) # Human settle
                    check_and_handle_modal(page)
                    
                    success = False
                    if l_type == "VIDEO":
                        success = scrape_video(page, manager)
                    elif l_type == "READING":
                        success = scrape_reading(page, manager)
                    
                    if not success:
                        print(f"   └── ⚠️ Could not scrape {title}. Moving on.")
                    
                    # Anti-detection/Rate-limit breathing
                    time.sleep(random.uniform(1, 3))

                except Exception as e:
                    print(f"   └── ❌ Navigation/Scrape Error: {e}")
                    time.sleep(2)

            print("\n✅ Archival process complete!")

        except KeyboardInterrupt:
            print("\n🛑 Process interrupted by user.")
        except Exception as e:
            print(f"❌ Critical Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dedicated Coursera Targeted Archiver")
    parser.add_argument("--force", action="store_true", help="Force re-scrape already archived items")
    args = parser.parse_args()
    
    run_archiver(force=args.force)
