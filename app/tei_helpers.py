import html
import re
import logging
from lxml import etree as ET
from app.config import NS
from app.services.metadata import meta_service
from app.services.xml_db import db

logger = logging.getLogger(__name__)

def add_tooltips_to_text(text, back_data):
    """
    Додає підказки для абревіатур мов та граматики.
    Екранує вхідний текст, щоб уникнути XSS, і вставляє HTML-теги для тултіпів.
    """
    if not text: 
        return ""

    def safe(t):
        return html.escape(t).replace('&amp;nbsp;', '&nbsp;')

    abbr_map = {}
    
    def collect_abbrs(items_list):
        for item in items_list:
            if item.get('abbr') and item.get('term') and item['abbr'] != item['term']:
                abbr_map[item['abbr']] = {'full': item['term']}
            if 'children' in item and item['children']:
                collect_abbrs(item['children'])
                
    for key in ['languages', 'grammar', 'styles', 'domains']:
        collect_abbrs(back_data.get(key, []))
        
    if not abbr_map: 
        return safe(text)
    
    ci_abbr_map = {k.lower(): v for k, v in abbr_map.items()}
    abbr_keys = sorted(abbr_map.keys(), key=len, reverse=True)
    pattern = re.compile(r'(?<!\w)(' + '|'.join(re.escape(key) for key in abbr_keys) + r')(?!\w)', re.IGNORECASE)
    
    parts = pattern.split(text)
    
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            result.append(safe(part))
        else:
            info = ci_abbr_map.get(part.lower())
            if info:
                full_text = safe(info.get('full', ''))
                result.append(f'<span class="has-tooltip" title="{full_text}">{safe(part)}</span>')
            else:
                result.append(safe(part))
                
    return "".join(result)

def tei_to_html(element, back_data=None):
    if element is None: return ""

    def process_text(txt):
        return add_tooltips_to_text(txt, back_data)

    content_parts = [process_text(element.text)]
    
    bibl_map = {}
    if back_data:
        if 'bibl_map_direct' in back_data:
            bibl_map = back_data['bibl_map_direct']
        elif 'bibliography' in back_data:
            for b in back_data['bibliography']:
                if b.get('abbr') and b.get('title'):
                    bibl_map[b['abbr'].strip()] = b['title']

    for child in element:
        tag_name = child.tag.split('}')[-1]
        
        if tag_name == 'hi':
            marker_tag = 'strong' if child.get('rend') == 'bold' else 'em'
            content_parts.append(f"<{marker_tag}>{process_text(child.text)}</{marker_tag}>")
            
        elif tag_name == 'ref' and 'target' in child.attrib:
            raw_url = child.get('target', '').strip()
            link_text = html.escape(child.text or raw_url).replace('&amp;nbsp;', '&nbsp;')
            
            if raw_url.lower() == '#bibl':
                lookup_key = (child.text or "").replace('\xa0', ' ').replace('[', '').replace(']', '').strip()
                raw_title = bibl_map.get(lookup_key, None)
                
                if raw_title:
                    clean_text = " ".join(raw_title.split())
                    safe_title = html.escape(clean_text, quote=True)
                    style = "border-bottom: 1px dotted #888; cursor: help; color: inherit;"
                else:
                    safe_title = f"Не знайдено в бібліографії: {lookup_key}"
                    style = "border-bottom: 1px dashed red; cursor: help; color: red;"

                content_parts.append(f'<span class="has-tooltip" title="{safe_title}" style="{style}">{link_text}</span>')
            
            elif re.match(r'^#?e\d+$', raw_url):
                entry_id = raw_url.lstrip('#')
                content_parts.append(f'<a href="#" class="entry-link" data-entry-id="{html.escape(entry_id)}">{link_text}</a>')
            
            else:
                target_attr = 'target="_blank"' if not raw_url.startswith('#') else ''
                content_parts.append(f'<a href="{html.escape(raw_url)}" {target_attr}>{link_text}</a>')
                
        elif tag_name == 'mentioned':
            content_parts.append(tei_to_html(child, back_data))
        elif tag_name == 'lb':
            content_parts.append(' ')
            
        if child.tail:
            content_parts.append(process_text(child.tail))

    return re.sub(r'\s+', ' ', "".join(content_parts)).strip()

def escape_markdown_chars(text):
    if not text: return ""
    return text.replace('*', r'\*')

# --- НОВА ФУНКЦІЯ ДЛЯ ОЧИЩЕННЯ ПРОБІЛІВ ---
def clean_xml_text(text):
    """Замінює всі переноси рядків і табуляції на один пробіл."""
    if not text: return ""
    return re.sub(r'\s+', ' ', text)

def tei_to_markdown(element):
    if element is None: return ""
    
    # 1. Чистимо текст самого елемента від зайвих відступів XML
    text_content = clean_xml_text(element.text)
    content_parts = [escape_markdown_chars(text_content)]
    
    for child in element:
        tag_name = child.tag.split('}')[-1]
        
        if tag_name == 'hi':
            inner_text = child.text or ""
            # Тут теж чистимо, хоча всередині тегів зазвичай менше сміття
            escaped_inner = escape_markdown_chars(clean_xml_text(inner_text))
            if child.get('rend') == 'bold': content_parts.append(f"**{escaped_inner}**")
            else: content_parts.append(f"*{escaped_inner}*")
            
        elif tag_name == 'ref' and 'target' in child.attrib:
            link_text = escape_markdown_chars(clean_xml_text(child.text))
            content_parts.append(f"[{link_text}]({child.get('target', '')})")
            
        elif tag_name == 'mentioned': 
            content_parts.append(tei_to_markdown(child))
            
        elif tag_name == 'lb': 
            content_parts.append('\n')
            
        # 2. Чистимо "хвіст" (текст після закриваючого тегу дочірнього елемента)
        if child.tail: 
            tail_content = clean_xml_text(child.tail)
            content_parts.append(escape_markdown_chars(tail_content))
            
    # Зшиваємо і прибираємо пробіли по краях параграфа
    return "".join(content_parts).strip()

def markdown_to_tei(text, parent_element):
    parent_element.text = None
    for child in list(parent_element): parent_element.remove(child)
    if not text: return
    
    pattern = r'(\\.)|(\[([^\[\]]*?)\]\(([^)]*?)\))|(\*\*([^*]+?)\*\*)|(\*([^*]+?)\*)|(_([^_]+?)_)|(\n)'
    
    last_end = 0
    
    def append_text(parent, txt):
        if not txt: return
        if len(parent) and parent[-1].tag != f"{{{NS['tei']}}}lb": parent[-1].tail = (parent[-1].tail or "") + txt
        else: parent.text = (parent.text or "") + txt
        
    for match in re.finditer(pattern, text):
        start, end = match.span()
        append_text(parent_element, text[last_end:start])
        
        if match.group(1): 
            append_text(parent_element, match.group(1)[1])
        elif match.group(2): 
            target = match.group(4).strip()
            text_link = match.group(3)
            ET.SubElement(parent_element, f"{{{NS['tei']}}}ref", {'target': target}).text = text_link
        elif match.group(5): 
            ET.SubElement(parent_element, f"{{{NS['tei']}}}hi", {'rend': 'bold'}).text = match.group(6)
        elif match.group(7): 
            content = match.group(8).replace(r'\*', '*')
            ET.SubElement(parent_element, f"{{{NS['tei']}}}hi", {'rend': 'italic'}).text = content
        elif match.group(9): 
            ET.SubElement(parent_element, f"{{{NS['tei']}}}hi", {'rend': 'italic'}).text = match.group(10)
        elif match.group(11): 
            ET.SubElement(parent_element, f"{{{NS['tei']}}}lb")
            
        last_end = end
        
    append_text(parent_element, text[last_end:])

def tei_note_to_html(note_element):
    if note_element is None: return ""
    _, root = db.load_xml()
    back_data = meta_service.parse_back_matter(root)
    return "".join([f"<p>{tei_to_html(p, back_data)}</p>" for p in note_element.findall('tei:p', NS)])

def tei_note_to_markdown(note_element):
    if note_element is None: return ""
    return "\n\n".join(tei_to_markdown(p) for p in note_element.findall('tei:p', NS))

def markdown_to_tei_note(markdown_text, note_element):
    if markdown_text:
        for child in list(note_element):
            note_element.remove(child)
        for p_text in markdown_text.strip().split('\n\n'):
            if p_text.strip():
                markdown_to_tei(p_text.strip(), ET.SubElement(note_element, f"{{{NS['tei']}}}p"))