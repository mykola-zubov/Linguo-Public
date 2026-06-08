import os
import logging
from lxml import etree as ET
from app.config import Config, NS

logger = logging.getLogger(__name__)

class XMLDatabase:
    def __init__(self):
        self._xml_cache = None

    def load_xml(self):
        if not os.path.exists(Config.XML_FILE):
            self._create_empty_xml()
        
        if self._xml_cache is None:
            try:
                parser = ET.XMLParser(remove_blank_text=False)
                tree = ET.parse(Config.XML_FILE, parser)
                tree.xinclude()
                self._xml_cache = tree
                logger.info("XML file loaded and XIncludes processed.")
            except ET.XMLSyntaxError as e:
                logger.error(f"XML Syntax Error: {e}")
                # Fallback logic or re-raise
                root = ET.Element(f"{{{NS['tei']}}}TEI", nsmap={None: NS['tei']})
                self._xml_cache = ET.ElementTree(root)
        
        return self._xml_cache, self._xml_cache.getroot()

    def save_xml(self):
        if self._xml_cache:
            try:
                self.cleanup_bibliography(self._xml_cache.getroot())
                self._xml_cache.write(Config.XML_FILE, pretty_print=True,
                                    encoding="utf-8", xml_declaration=True)
                # Clear cache to ensure next load is fresh or keep it updated
                self._xml_cache = None 
                logger.info("File saved successfully, cache cleared.")
                return True, None
            except Exception as e:
                logger.error(f"Error writing XML file: {e}")
                return False, str(e)
        return False, "No XML loaded"

    def _create_empty_xml(self):
        root = ET.Element(f"{{{NS['tei']}}}TEI", nsmap={None: NS['tei']})
        tei_header = ET.SubElement(root, "teiHeader")
        file_desc = ET.SubElement(tei_header, "fileDesc")
        ET.SubElement(ET.SubElement(file_desc, "titleStmt"), "title").text = "Dictionary"
        ET.SubElement(ET.SubElement(file_desc, "publicationStmt"), "p").text = "unpublished"
        ET.SubElement(ET.SubElement(file_desc, "sourceDesc"), "p").text = "born digital"
        text = ET.SubElement(root, "text")
        ET.SubElement(ET.SubElement(text, "body"), "div", {'type': 'dictionary'})
        ET.SubElement(ET.SubElement(text, "back"), "listBibl")
        ET.ElementTree(root).write(Config.XML_FILE, pretty_print=True,
                                   encoding="utf-8", xml_declaration=True)

    def cleanup_bibliography(self, root):
        all_bibl_refs = {ref.get('target').lstrip('#') for ref in root.findall(
            './/tei:entry//tei:ref[@type="bibliography"]', NS) if ref.get('target')}
        list_bibl = root.find(
            './/tei:back/tei:div[@type="bibliography"]/tei:listBibl', NS)
        if list_bibl is None:
            return
        bibls_to_remove = [bibl for bibl in list_bibl.findall(
            'tei:bibl', NS) if bibl.get(f"{{{NS['xml']}}}id") not in all_bibl_refs]
        for bibl in bibls_to_remove:
            list_bibl.remove(bibl)

# Global instance
db = XMLDatabase()