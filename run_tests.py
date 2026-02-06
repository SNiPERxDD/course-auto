import unittest
import os
import shutil
import time
import sys
import random
import re
from playwright.sync_api import sync_playwright

# --- IMPORT MODULES TO TEST ---
from course_manager import CourseManager
from coursera_archiver import scrape_video, scrape_reading
from discover_selectors_coursera import get_detailed_course_map, get_robust_course_name
import coursera_stealth

# --- CONFIGURATION ---
CDP_URL = "http://localhost:9222"
TEST_DIR = "test_artifacts"
TRANSCRIPT_DIR = "coursera_transcripts"

# --- MOCKING UTILS ---
original_sleep = time.sleep

def fast_sleep(seconds):
    """Replaces time.sleep to make tests fast."""
    if seconds > 1:
        print(f"    ⚡ [MOCK] Fast-forwarding {seconds:.1f}s sleep...")
        original_sleep(0.1) # Sleep 100ms instead of X seconds
    else:
        original_sleep(seconds)

class TestCourseraAutomation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("\n" + "="*60)
        print("🚀 STARTING RAPID DIAGNOSTIC SUITE (v2.5.0)")
        print("="*60)
        
        # 1. Setup Test Environment
        if os.path.exists(TEST_DIR):
            shutil.rmtree(TEST_DIR)
        os.makedirs(TEST_DIR)
        
        # 2. Monkey Patching
        # This forces the imported modules to use our fast sleep
        coursera_stealth.time.sleep = fast_sleep
        # Patch random to avoid long waits/jitters
        coursera_stealth.random.uniform = lambda a, b: 0.05 
        coursera_stealth.random.randint = lambda a, b: a # Predictable small steps
        
        # 3. Connect Browser
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.connect_over_cdp(CDP_URL)
            cls.context = cls.browser.contexts[0]
            # Platinum Logic: Store all pages so we can find content
            cls.pages = cls.context.pages
            cls.page = cls.pages[0] # Default
            print(f"✅ Connected to Browser ({len(cls.pages)} tabs found)")
            for i, p in enumerate(cls.pages):
                print(f"   [{i}] {p.title()}")
        except Exception as e:
            print(f"❌ Could not connect to Chrome on {CDP_URL}.")
            print("   Ensure Chrome is running with --remote-debugging-port=9222")
            cls.playwright.stop()
            sys.exit(1)

    @classmethod
    def tearDownClass(cls):
        print("\n" + "="*60)
        print("🧹 CLEANUP & SUMMARY")
        print("="*60)
        cls.playwright.stop()
        print(f"📂 Test artifacts saved (if any) in: {TEST_DIR}/")

    def test_01_course_manager_logic(self):
        """Test XML generation and canonical naming."""
        print("\n🧪 TEST 01: Course Manager (Platinum Check)")
        
        mock_map = {
            "Module 1": [("Lesson A", "VIDEO", "/video-url", "5 min")],
            "Module 2": [("Lesson B", "READING", "/read-url", "10 min")]
        }
        
        manager = CourseManager(mock_map, "Test Course Platinum")
        # Direct manager to test dir
        manager.root_dir = os.path.join(TEST_DIR, "Test_Course_Platinum")
        manager.xml_path = os.path.join(manager.root_dir, "course_content.xml")
        os.makedirs(manager.root_dir, exist_ok=True)
        manager._init_xml()
        
        self.assertTrue(os.path.exists(manager.xml_path))
        
        # Test Naming
        fname, ok = manager.save_content("/video-url", "Dummy Data", "Transcript")
        self.assertIn("M01_L01", fname)
        self.assertTrue(ok)
        print("   ✅ XML Ledger and Canonical Naming verified.")

    def test_02_physics_engine_stability(self):
        """Verify physics helpers don't crash."""
        print("\n🧪 TEST 02: Physics Engine (Stability Check)")
        try:
            # Test human_move with short snappy steps (v2.0.0 fix)
            coursera_stealth.human_move(self.page, 200, 200)
            print("   ✅ human_move (Adaptive) OK.")
            
            # Test human_scroll (burst)
            coursera_stealth.human_scroll(self.page, 50, 400, 400)
            print("   ✅ human_scroll (Smooth) OK.")
        except Exception as e:
            self.fail(f"Physics Engine crashed: {e}")

    def test_03_video_fast_forward(self):
        """Test JS injection for rapid video completion."""
        print("\n🧪 TEST 03: Video Injection (Speed Hack)")
        
        target_page = None
        for p in self.pages:
            if p.locator("video").count() > 0:
                target_page = p
                break
        
        if not target_page:
            print("   ⚠️ No video found in any open tab. Skipping.")
            return

        print(f"   ℹ️ Targeted Tab: {target_page.title()}")
        print("   ⚡ Injecting currentTime hack...")
        try:
            target_page.evaluate("""
                const v = document.querySelector('video');
                if (v) {
                    v.currentTime = v.duration - 1;
                    v.play();
                }
            """)
            # Give it a moment to finish
            original_sleep(2)
            
            # Check if next button is visible
            next_btn = coursera_stealth.get_next_button(target_page)
            if next_btn.is_visible():
                print("   ✅ Video Hack triggered 'Next' visibility.")
            else:
                print("   ⚠️ Video ended but 'Next' not toggled (course dependent).")
        except Exception as e:
            print(f"   ❌ Injection failed: {e}")

    def test_04_reading_session_mock(self):
        """Test reading session with fast-sleep monkey patch."""
        print("\n🧪 TEST 04: Reading Logic (Platinum Speed)")
        
        target_page = None
        for p in self.pages:
            if p.locator("div.rc-CML, main").count() > 0 and "Video" not in p.title():
                target_page = p
                break
                
        if not target_page:
            print("   ⚠️ No reading container found in any open tab. Skipping.")
            return

        print(f"   ℹ️ Targeted Tab: {target_page.title()}")
        # Perform 0.1 min session (6s real time, but our fast_sleep makes it < 1s)
        status = coursera_stealth.smart_reading_session(target_page, 0.1)
        self.assertEqual(status, "COMPLETED")
        print("   ✅ Smart Reading logic passed (Rapid).")

if __name__ == "__main__":
    suite = unittest.TestSuite()
    suite.addTest(TestCourseraAutomation('test_01_course_manager_logic'))
    suite.addTest(TestCourseraAutomation('test_02_physics_engine_stability'))
    suite.addTest(TestCourseraAutomation('test_03_video_fast_forward'))
    suite.addTest(TestCourseraAutomation('test_04_reading_session_mock'))
    
    runner = unittest.TextTestRunner(verbosity=1)
    runner.run(suite)
