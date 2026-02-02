import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime

class CourseManager:
    def __init__(self, course_map, course_name):
        self.course_map = course_map
        self.course_name = course_name
        sanitized = re.sub(r'[\\/*?:"<>|]', "", course_name).strip()
        self.safe_course_name = sanitized[:250] if len(sanitized) > 250 else sanitized
        self.root_dir = os.path.join("coursera_transcripts", self.safe_course_name)
        self.xml_path = os.path.join(self.root_dir, "course_content.xml")
        
        # Ensure directories exist
        os.makedirs(self.root_dir, exist_ok=True)
        self._init_xml()

    def _init_xml(self):
        """Creates the skeleton XML if it doesn't exist."""
        if not os.path.exists(self.xml_path):
            root = ET.Element("course", name=self.course_name, updated=str(datetime.now()))
            
            # Pre-populate structure from Map
            for module_name, lessons in self.course_map.items():
                m_node = ET.SubElement(root, "module", title=module_name)
                
                for title, l_type, url, duration in lessons:
                    # Only include Reading and Video in the XML ledger
                    if l_type not in ["VIDEO", "READING"]:
                        continue
                        
                    l_node = ET.SubElement(m_node, "item")
                    l_node.set("title", title)
                    l_node.set("type", l_type)
                    l_node.set("url", url)
                    # Content tag is empty initially
                    ET.SubElement(l_node, "content").text = ""

            tree = ET.ElementTree(root)
            if hasattr(ET, "indent"): # Python 3.9+
                ET.indent(tree, space="  ", level=0)
            tree.write(self.xml_path, encoding="utf-8", xml_declaration=True)

    def resolve_location(self, current_url):
        """
        Returns (Module_Index, Lesson_Index, Safe_Title, Module_Name) 
        by finding the URL in the map.
        """
        # Normalize URL for matching (remove domain if map has relative paths)
        rel_url = current_url.replace("https://www.coursera.org", "")
        rel_url = rel_url.split("?")[0].split("#")[0] # Strip query/hash
        
        m_idx = 1
        for module_name, lessons in self.course_map.items():
            l_idx = 1
            for title, l_type, map_url, _ in lessons:
                # Compare strict relative paths
                if map_url in rel_url or rel_url in map_url:
                    safe_title = re.sub(r'[\\/*?:"<>|]', "", title).replace(" ", "_")
                    return (m_idx, l_idx, safe_title, module_name)
                l_idx += 1
            m_idx += 1
        
        return (0, 0, "Unknown_Item", "Unknown_Module")

    def save_content(self, current_url, content_text, content_type):
        """
        Saves content to TXT and updates the XML database.
        """
        m_idx, l_idx, title, m_name = self.resolve_location(current_url)
        
        # 1. Save TXT File (Grouped)
        prefix = f"M{m_idx:02d}_L{l_idx:02d}"
        filename = f"{prefix}_{title}_{content_type}.txt"
        file_path = os.path.join(self.root_dir, filename)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content_text)
            
        # 2. Update XML
        try:
            tree = ET.parse(self.xml_path)
            root = tree.getroot()
            
            # Normalize current URL for lookup
            rel_url = current_url.replace("https://www.coursera.org", "").split("?")[0].split("#")[0]
            
            found = False
            for item in root.findall(".//item"):
                item_url = item.get("url")
                if item_url and (item_url in rel_url or rel_url in item_url):
                    content_node = item.find("content")
                    if content_node is None:
                        content_node = ET.SubElement(item, "content")
                    
                    content_node.text = content_text
                    found = True
                    break
            
            if found:
                if hasattr(ET, "indent"): # Python 3.9+
                    ET.indent(tree, space="  ", level=0)
                tree.write(self.xml_path, encoding="utf-8", xml_declaration=True)
                return filename, True
        except Exception as e:
            print(f"XML Update Failed: {e}")
            
        return filename, False

    def get_next_url(self, current_url):
        """Smart Fallback: Calculates the mathematical next URL from the map."""
        rel_url = current_url.replace("https://www.coursera.org", "").split("?")[0].split("#")[0]
        
        flattened_urls = []
        for _, lessons in self.course_map.items():
            for _, _, url, _ in lessons:
                flattened_urls.append(url)
        
        try:
            curr_idx = -1
            for i, u in enumerate(flattened_urls):
                if u in rel_url or rel_url in u:
                    curr_idx = i
                    break
            
            if curr_idx != -1 and curr_idx + 1 < len(flattened_urls):
                next_path = flattened_urls[curr_idx + 1]
                return f"https://www.coursera.org{next_path}"
        except: pass
        return None
