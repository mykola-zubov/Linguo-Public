import logging
import locale
from collections import defaultdict
from app.config import NS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MetadataService:
    def __init__(self):
        self._back_data_cache = None

    def clear_cache(self):
        self._back_data_cache = None

    def parse_back_matter(self, root):
        if self._back_data_cache is not None:
            return self._back_data_cache

        back_node = root.find(".//tei:back", NS)
        if back_node is None:
            logger.error("!!! METADATA ERROR: <back> section NOT FOUND in XML !!!")
            return {}

        back_data = defaultdict(list)
        xml_id_key = f"{{{NS['xml']}}}id"
        xml_lang_key = f"{{{NS['xml']}}}lang"

        # --- Helper for recursive parsing (Універсальний парсер) ---
        def parse_items(list_node):
            items = []
            if list_node is None:
                return items
            
            for item_node in list_node.findall("tei:item", NS):
                # 1. Спробуємо знайти вкладені теги TEI (правильний спосіб)
                abbr_tag = item_node.find("tei:abbr", NS)
                term_tag = item_node.find("tei:term", NS)
                expan_tag = item_node.find("tei:expan", NS)
                
                # Визначаємо "повну назву" (term)
                if term_tag is not None and term_tag.text:
                    main_text = term_tag.text.strip()
                elif expan_tag is not None and expan_tag.text:
                    main_text = expan_tag.text.strip()
                elif item_node.text:
                    main_text = item_node.text.strip()
                else:
                    main_text = ""

                # Визначаємо "абревіатуру" (abbr)
                if abbr_tag is not None and abbr_tag.text:
                    abbr_text = abbr_tag.text.strip()
                elif term_tag is not None and term_tag.get('abbr'):
                    abbr_text = term_tag.get('abbr')
                elif item_node.get('abbr'):
                    abbr_text = item_node.get('abbr')
                else:
                    abbr_text = main_text

                item_data = {
                    'id': item_node.get(xml_id_key), 
                    'value': item_node.get('value'),
                    'abbr': abbr_text, 
                    'term': main_text,
                    'code': item_node.get(xml_lang_key), 
                    'children': []
                }
                
                nested_list = item_node.find("tei:list", NS)
                if nested_list is not None:
                    item_data['children'] = parse_items(nested_list)
                items.append(item_data)
            return items

        # --- Parsing Sections ---
        abbreviations_div = back_node.find(".//tei:div[@type='abbreviations']", NS)
        if abbreviations_div is not None:
            if (node := abbreviations_div.find(".//tei:div[@type='borrowing_characteristics']", NS)) is not None:
                for list_node in node.findall("tei:list", NS):
                    back_data['borrowing_characteristics'].append({
                        'id': list_node.get('type'), 'children': parse_items(list_node)
                    })
            if (node := abbreviations_div.find(".//tei:div[@type='languages']/tei:list[@type='gloss']", NS)) is not None:
                back_data['languages'] = parse_items(node)
            if (node := abbreviations_div.find("./tei:list[@type='grammar']", NS)) is not None:
                back_data['grammar'] = parse_items(node)
            if (node := abbreviations_div.find("./tei:list[@type='domains']", NS)) is not None:
                back_data['domains'] = parse_items(node)
            if (node := abbreviations_div.find("./tei:list[@type='styles']", NS)) is not None:
                back_data['styles'] = parse_items(node)

        # --- НОВИЙ БЛОК: Зчитування регіонів ---
        regions_div = back_node.find(".//tei:div[@type='regions']", NS)
        if regions_div is not None:
            if (node := regions_div.find(".//tei:list[@type='region']", NS)) is not None:
                back_data['regions'] = parse_items(node)

        # --- Helper maps ---
        back_data['lang_map'] = {item['code']: item['abbr'] for item in back_data.get('languages', [])}
        back_data['lang_full_map'] = {item['code']: item['term'] for item in back_data.get('languages', [])}
        
        def add_to_map(target_map, item, parent_term=""):
            abbr_text = item.get('abbr') or item.get('term') or ""
            full_text = item.get('term') or item.get('abbr') or ""
            info_obj = {'abbr': abbr_text, 'full': full_text}
            
            keys = [item.get('term'), item.get('abbr'), item.get('value'), item.get('id')]
            for k in keys:
                if k:
                    target_map[k] = info_obj
                    target_map[k.lower()] = info_obj

        back_data['domain_info'] = {}
        for main_domain in back_data.get('domains', []):
            for sub_domain in main_domain.get('children', []):
                info_obj = {
                    'abbr': sub_domain.get('abbr', sub_domain['term']),
                    'full': f"{main_domain['term']}: {sub_domain['term']}"
                }
                if sub_domain.get('term'): back_data['domain_info'][sub_domain['term']] = info_obj
                if sub_domain.get('abbr'): back_data['domain_info'][sub_domain['abbr']] = info_obj

        back_data['style_info_map'] = {}
        back_data['region_info'] = {}

# 1. Заповнюємо стилі
        for main_style in back_data.get('styles', []):
            is_region_group = (main_style.get('id') == 'DOM-STYLE-TERR')
            
            # 1. Завжди додаємо в style_info_map (щоб працював пошук і відображення у статтях)
            add_to_map(back_data['style_info_map'], main_style)
            
            # 2. Якщо це група регіонів, ДОДАТКОВО записуємо в region_info (для ваших нових списків)
            if is_region_group:
                add_to_map(back_data['region_info'], main_style)

            for sub_style in main_style.get('children', []):
                # Так само для дочірніх елементів: спершу в загальний
                add_to_map(back_data['style_info_map'], sub_style, parent_term=main_style.get('term'))
                
                # Потім, якщо треба, в регіональний
                if is_region_group:
                    add_to_map(back_data['region_info'], sub_style, parent_term=main_style.get('term'))        
        # Регіони (з нового блоку)
        for region_item in back_data.get('regions', []):
            add_to_map(back_data['region_info'], region_item)

        # --- BIBLIOGRAPHY PARSING ---
        logger.info("--- METADATA: START PARSING BIBLIOGRAPHY ---")
        all_bibls = back_node.findall(".//tei:bibl", NS)
        for bibl_node in all_bibls:
            bibl_id = bibl_node.get(xml_id_key)
            title_node = bibl_node.find("tei:title", NS)
            abbr_node = bibl_node.find("tei:abbr", NS)
            
            title_text = title_node.text.strip() if title_node is not None and title_node.text else ""
            abbr_text = abbr_node.text.strip() if abbr_node is not None and abbr_node.text else ""
            
            if not abbr_text and bibl_id: abbr_text = bibl_id

            if abbr_text:
                back_data['bibliography'].append({
                    'id': bibl_id, 'title': title_text, 'abbr': abbr_text
                })

        if 'bibliography' in back_data:
            def bibl_sort_key(bibl_item):
                abbr = bibl_item.get('abbr', '')
                if not abbr: return (2, '')
                is_cyrillic = 'а' <= abbr[0].lower() <= 'я' or abbr[0].lower() == 'ґ'
                return (0 if is_cyrillic else 1, locale.strxfrm(abbr.lower()))
            back_data['bibliography'].sort(key=bibl_sort_key)

        bibl_map_direct = {}
        for item in back_data.get('bibliography', []):
            if item['abbr'] and item['title']:
                key = item['abbr'].strip().replace('\xa0', ' ')
                val = item['title'].replace('\n', ' ')
                bibl_map_direct[key] = val
        back_data['bibl_map_direct'] = bibl_map_direct
        
        self._back_data_cache = back_data
        return back_data

meta_service = MetadataService()