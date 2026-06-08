import re
import locale
import html
from collections import defaultdict
from lxml import etree as ET
from flask_babel import gettext
from app.config import NS
from app.utils import slugify
from app.services.metadata import meta_service
from app.tei_helpers import (tei_to_html, tei_to_markdown, markdown_to_tei, 
                             tei_note_to_html, tei_note_to_markdown, markdown_to_tei_note,
                             add_tooltips_to_text)

def build_gram_display(back_data, pos, gen, transitivity, aspect, lang):
    grammar_data = back_data.get('grammar', [])
    if not grammar_data:
        return ""

    def find_gram_item(category_id, item_value):
        category = next(
            (cat for cat in grammar_data if cat.get('id') == category_id), None)
        if category:
            item = next((child for child in category.get(
                'children', []) if child.get('value') == item_value), None)
            return item
        return None

    display_parts = []
    tooltip_parts = []

    for category_id, item_value in [
        ('DOM-GRAM-POS', pos),
        ('DOM-GRAM-GEN', gen),
        ('DOM-GRAM-VERBFEAT', transitivity),
        ('DOM-GRAM-VERBFEAT', aspect)
    ]:
        if item_value:
            item = find_gram_item(category_id, item_value)
            if item:
                display_parts.append(item['abbr'])
                tooltip_parts.append(item['term'])

    separator = " " if lang == 'de' else ", "
    return separator.join(display_parts), ", ".join(tooltip_parts)

def find_bibl_id_by_abbr(abbr, root):
    if not abbr: return None
    clean_abbr = abbr.split()[0].strip('.,') 
    xml_id_key = f"{{{NS['xml']}}}id"

    for bibl in root.findall(".//tei:back//tei:bibl", NS):
        current_abbr = bibl.findtext("tei:abbr", namespaces=NS)
        if current_abbr and (current_abbr == clean_abbr or abbr.startswith(current_abbr)):
            bibl_id = bibl.get(xml_id_key)
            return f"#{bibl_id}" if bibl_id else None
    return None

def format_translation_text(text, back_data):
    """Форматує текст перекладу: тултіпи + Markdown (жирний/курсив)."""
    if not text: return ""
    processed = add_tooltips_to_text(text, back_data)
    processed = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', processed)
    processed = re.sub(r'\*(.*?)\*', r'<em>\1</em>', processed)
    return processed

# --- ШВИДКА ФУНКЦІЯ (для списків) ---
def parse_entry_header(entry_element, target_lang='uk'):
    """
    Легковаговий парсер для списків та пошуку.
    target_lang: 'uk' (за замовчуванням) або 'de'.
    """
    if entry_element is None:
        return None

    xml_id_key = f"{{{NS['xml']}}}id"
    
    data = {
        'id': entry_element.get(xml_id_key),
        'status': entry_element.get('status'),
        'orth': '',
        'variants': []
    }

    # Визначаємо, яке слово шукати: Українське чи Німецьке
    if target_lang == 'de':
        # Шлях до німецького слова: etym[type='german'] -> form -> orth
        orth_node = entry_element.find(".//tei:etym[@type='german']/tei:form/tei:orth", NS)
    else:
        # Шлях до українського слова: form[type='lemma'] -> orth
        orth_node = entry_element.find("tei:form[@type='lemma']/tei:orth", NS)

    # Якщо слова немає в цій мові (наприклад, стаття без німецького відповідника),
    # повертаємо None, щоб не показувати пустий рядок у списку
    if orth_node is not None and orth_node.text:
        data['orth'] = orth_node.text.strip()
    else:
        # Якщо запитували німецьку, а її немає - пропускаємо статтю у списку
        if target_lang == 'de':
            return None
        # Якщо запитували українську і її немає (що дивно), можна залишити пустим
        
    # Варіанти (тільки для української, бо для німецької варіантів у такій структурі зазвичай немає)
    # Якщо потрібно шукати і по українських варіантах при німецькому списку, цей блок можна залишити
    for form_var in entry_element.findall("tei:form[@type='variant']/tei:orth", NS):
        if form_var.text:
            data['variants'].append({'orth': form_var.text.strip()})

    return data

# --- ПОВНА ФУНКЦІЯ (для перегляду/редагування) ---
def parse_entry_data(entry_element, root):
    back_data = meta_service.parse_back_matter(root)
    lang_map = back_data.get('lang_map', {})
    lang_full_map = back_data.get('lang_full_map', {})

    terr_style_abbrs = set()
    if back_data.get('styles'):
        for style_grp in back_data['styles']:
            if style_grp['id'] == 'DOM-STYLE-TERR':
                for item in style_grp.get('children', []):
                    if item.get('abbr'):
                        terr_style_abbrs.add(item['abbr'])
                    if item.get('term'):
                        terr_style_abbrs.add(item['term'])

    lang_term_map = {}
    if 'languages' in back_data:
        for lang in back_data['languages']:
            term = lang.get('term')
            abbr = lang.get('abbr')
            if term:
                lang_term_map[term] = {'abbr': abbr if abbr else term, 'full': term}

    if entry_element is None:
        return None

    data = defaultdict(lambda: None, {
        'senses': [], 'german_senses': [], 'equivalents': [], 'bibliography': [],
        'variants': [], 
        'is_redirect': False, 'borrowing_mediators': [], 'alter_donors': [],
        'style': [], 'german_etym': {}, 'alter_german_etyms': [],
        'lemma_geo': [], 'lemma_style': [], 'lemma_region_style': [],
        'german_head_geo': [], 'german_head_style': [], 'german_head_region_style': []
    })

    grammar_map = {}
    grammar_abbr_map = {}
    if 'grammar' in back_data:
        for cat in back_data['grammar']:
            for child in cat.get('children', []):
                if child.get('value'):
                    grammar_map[child['value']] = child.get('term', child['value'])
                    grammar_abbr_map[child['value']] = child.get('abbr') or child.get('term') or child['value']
    
    data['grammar_map'] = grammar_map
    data['grammar_abbr_map'] = grammar_abbr_map

    xml_id_key = f"{{{NS['xml']}}}id"
    xml_lang_attr = f"{{{NS['xml']}}}lang"
    data['id'] = entry_element.get(xml_id_key)
    data['status'] = entry_element.get('status')
    data['entry_type'] = entry_element.get('type', 'normal')

    def get_text(element, path):
        node = element.find(path, NS)
        return node.text.strip() if node is not None and node.text else ""

    # --- BIBLIOGRAPHY ---
    bibl_path = ".//tei:back/tei:div[@type='bibliography']/tei:listBibl/tei:bibl"
    all_bibls_global = {b.get(xml_id_key): b for b in root.findall(bibl_path, NS) if b.get(xml_id_key)}

    bibl_abbr_map = {}
    bibl_norm_map = {}
    
    for b_id, b_node in all_bibls_global.items():
        abbr = get_text(b_node, 'tei:abbr')
        title = get_text(b_node, 'tei:title')
        if abbr:
            bibl_abbr_map[abbr] = title
            norm_key = abbr.lower().replace('.', '').strip()
            bibl_norm_map[norm_key] = title
    
    def get_bibl_title(bibl_id, abbr_text=None):
        if bibl_id and bibl_id in all_bibls_global:
            return get_text(all_bibls_global[bibl_id], 'tei:title')
        
        if abbr_text:
            clean_text = abbr_text.strip()
            if clean_text in bibl_abbr_map:
                return bibl_abbr_map[clean_text]
            
            norm_text = clean_text.lower().replace('.', '').strip()
            if norm_text in bibl_norm_map:
                return bibl_norm_map[norm_text]
                
            for key, val in bibl_abbr_map.items():
                if clean_text.startswith(key):
                    return val
            for key, val in bibl_norm_map.items():
                if norm_text.startswith(key):
                    return val
        return ""

    entry_bibliography = []
    for ref in entry_element.findall(".//tei:ref[@type='bibliography']", NS):
        target_id = ref.get("target", "").lstrip('#')
        bib_node = all_bibls_global.get(target_id)
        if target_id and bib_node is not None:
            local_abbr = get_text(ref, 'tei:abbr')
            url_node = bib_node.find("tei:ref", NS)
            bibl_data = {
                "id": target_id,
                "title": get_text(bib_node, 'tei:title'),
                "abbr": local_abbr if local_abbr else get_text(bib_node, 'tei:abbr'),
                "volume": get_text(ref, 'tei:volume'),
                "page": get_text(ref, 'tei:page'),
                "url": (url_node.get("target", "") if url_node is not None else "")
            }
            entry_bibliography.append(bibl_data)

    def bibl_sort_key(item):
        text = item.get('abbr', '')
        if not text: return (2, "")
        if re.match(r'^[а-яА-ЯіІїЇєЄґҐ]', text):
            return (0, text.lower())
        return (1, text.lower())

    entry_bibliography.sort(key=bibl_sort_key)
    data['bibliography'] = entry_bibliography

    def find_bibl_target_for_cit(c_node):
        source_abbr = get_text(c_node, ".//tei:abbr")
        if not source_abbr:
            return None
        ref_in_cit = c_node.find("tei:ref", NS)
        if ref_in_cit is not None and ref_in_cit.get('target'):
            return ref_in_cit.get('target').lstrip('#')
        
        author_candidate = source_abbr.split()[0].strip().rstrip('.,:')
        for bibl_entry in data['bibliography']:
            if bibl_entry.get('abbr') and bibl_entry['abbr'].startswith(author_candidate):
                return bibl_entry['id']
        return None

    domain_info_map = back_data.get('domain_info', {})
    region_info_map = back_data.get('region_info', {})
    style_info_map = back_data.get('style_info_map', {})

    # --- Parsing UKRAINIAN Headword (Lemma) ---
    form_uk = entry_element.find("tei:form[@type='lemma']", NS)
    if form_uk is not None:
        data.update({
            "orth": get_text(form_uk, 'tei:orth'),
            "stress": get_text(form_uk, 'tei:stress'),
            "lemma_time": get_text(form_uk, "tei:usg[@type='time']")
        })
        for usg in form_uk.findall("tei:usg", NS):
            usg_type = usg.get('type')
            if usg_type == 'geo':
                data['lemma_geo'].append(usg.text)
            elif usg_type == 'style':
                val = usg.text
                if val in terr_style_abbrs:
                    data['lemma_region_style'].append(val)
                else:
                    data['lemma_style'].append(val)

    # --- Parsing Variants (NESTED SENSES LOGIC) ---
    for form_var in entry_element.findall("tei:form[@type='variant']", NS):
        # Зчитуємо PoS для варіанту
        pos_val = ""
        gram_grp = form_var.find("tei:gramGrp", NS)
        if gram_grp is not None:
            pos_val = gram_grp.findtext("tei:pos", default="", namespaces=NS)

        var_data = {
            'orth': get_text(form_var, 'tei:orth'),
            'pos': pos_val, 
            'time': get_text(form_var, "tei:usg[@type='time']"),
            'senses': [] 
        }
        
        for var_sense in form_var.findall("tei:sense", NS):
            def_node = var_sense.find("tei:def", NS)
            
            sense_item = {
                'def': tei_to_markdown(def_node),
                'def_html': tei_to_html(def_node, back_data),
                'time': get_text(var_sense, "tei:usg[@type='time']"),
                'geo': [],          
                'geo_display': [],  
                'region_style': [],
                'style': [],
                'source': None
            }
            
            for usg in var_sense.findall("tei:usg", NS):
                usg_type = usg.get('type')
                val = usg.text.strip() if usg.text else None
                if val:
                    if usg_type == 'geo':
                        sense_item['geo'].append(val)
                        if val in region_info_map:
                            info = region_info_map[val]
                            sense_item['geo_display'].append({'abbr': info['abbr'], 'full': info['full']})
                        elif val in lang_term_map:
                            info = lang_term_map[val]
                            sense_item['geo_display'].append({'abbr': info['abbr'], 'full': info['full']})
                        else:
                            sense_item['geo_display'].append({'abbr': val, 'full': val})
                    elif usg_type == 'style':
                        if val in terr_style_abbrs:
                            sense_item['region_style'].append(val)
                        else:
                            sense_item['style'].append(val)
            
            ref = var_sense.find("tei:ref[@type='source']", NS)
            if ref is not None:
                sense_item['source'] = {
                    'id': ref.get('target', '').lstrip('#'),
                    'abbr': ref.text
                }
            
            var_data['senses'].append(sense_item)
            
        data['variants'].append(var_data)

    xr_node = entry_element.find("tei:xr", NS)
    if xr_node is not None:
        data['is_redirect'] = True
        data['redirect_label'] = get_text(xr_node, "tei:lbl") or "see"
        data['redirect_targets'] = [{'id': ref.get("target", "").lstrip(
            '#'), 'text': ref.text or ""} for ref in xr_node.findall("tei:ref", NS)]
        redirect_ids = [target['id'] for target in data.get(
            'redirect_targets', []) if target.get('id')]
        data['redirect_target'] = ", ".join(redirect_ids)

    gram_grp = entry_element.find('tei:gramGrp', NS)
    if gram_grp is not None:
        data.update({
            "pos": get_text(gram_grp, 'tei:pos'), "gram_gen": get_text(gram_grp, 'tei:gen'),
            "transitivity": get_text(gram_grp, "tei:trait[@type='transitivity']"),
            "aspect": get_text(gram_grp, "tei:trait[@type='aspect']"),
            'casus_gen': gram_grp.findtext("tei:casus[@type='genitive'][@subtype='singular']", default="", namespaces=NS)
        })

    # --- Parsing Ukrainian Senses ---
    for sense_el in entry_element.findall("tei:sense", NS):
        def_node = sense_el.find("tei:def[@xml:lang='uk']", NS)
        if def_node is None:
            non_german_defs = [d for d in sense_el.findall(
                "tei:def", NS) if d.get(xml_lang_attr) != 'de']
            if non_german_defs:
                def_node = non_german_defs[0]

        sense_data = {
            'style': [], 'examples': [], 'domain': [], 'usg_display_parts': [], 'translations': [], 
            'geo': [], 'geo_display': []
        }

        usg_display_parts = []

        for usg in sense_el.findall('tei:usg', NS):
            usg_type = usg.get("type")
            usg_text = usg.text.strip() if usg.text else ""
            if not usg_text:
                continue

            if usg_type == 'style':
                sense_data['style'].append(usg_text)
                info = style_info_map.get(usg_text, {})
                usg_display_parts.append({'type': 'abbr', 'value': info.get(
                    'abbr', usg_text), 'title': info.get('full', usg_text)})
            elif usg_type == 'domain':
                sense_data['domain'].append(usg_text)
                info = domain_info_map.get(usg_text, {})
                usg_display_parts.append({'type': 'abbr', 'value': info.get(
                    'abbr', usg_text), 'title': info.get('full', usg_text)})
            elif usg_type == 'region':
                sense_data['region'] = usg_text
                info = region_info_map.get(usg_text, {})
                usg_display_parts.append({'type': 'abbr', 'value': info.get(
                    'abbr', usg_text), 'title': info.get('full', usg_text)})
            elif usg_type == 'time':
                sense_data['time'] = usg_text
                usg_display_parts.append(
                    {'type': 'text', 'value': usg_text, 'title': gettext('Time of use')})
            
            elif usg_type == 'geo':
                if 'geo' not in sense_data or sense_data['geo'] is None:
                    sense_data['geo'] = []
                sense_data['geo'].append(usg_text)
                
                # Обробка для головних значень
                if usg_text in region_info_map:
                    info = region_info_map[usg_text]
                    sense_data['geo_display'].append({'abbr': info['abbr'], 'full': info['full']})
                elif usg_text in lang_term_map:
                    sense_data['geo_display'].append(lang_term_map[usg_text])
                else:
                    sense_data['geo_display'].append({'abbr': usg_text, 'full': usg_text})
            else:
                sense_data[usg_type] = usg_text
                usg_display_parts.append(
                    {'type': 'text', 'value': usg_text, 'title': usg_type})
        
        if sense_data['geo']:
            sense_data['geo'] = list(dict.fromkeys(sense_data['geo']))
        
        if sense_data['geo_display']:
             unique_geo = {item['full']: item for item in sense_data['geo_display']}.values()
             sense_data['geo_display'] = list(unique_geo)

        sense_data['usg_display_parts'] = usg_display_parts

        for c_node in sense_el.findall("tei:cit[@type='example']", NS):
            q_node = c_node.find('tei:quote', NS)
            if q_node is not None:
                bibl_target_id = find_bibl_target_for_cit(c_node)
                source_abbr = get_text(c_node, ".//tei:abbr")
                sense_data['examples'].append({
                    "quote_html": tei_to_html(q_node, back_data), 
                    "quote": tei_to_markdown(q_node),
                    "source_abbr": source_abbr, 
                    "bibl_target": bibl_target_id,
                    "source_title": get_bibl_title(bibl_target_id, source_abbr)
                })
        
        for trans_node in sense_el.findall("tei:cit[@type='translation']", NS):
            t_lang = trans_node.get(xml_lang_attr)
            t_quote = trans_node.findtext("tei:quote", default="", namespaces=NS)
            if t_lang and t_quote:
                sense_data['translations'].append({
                    'lang': t_lang,
                    'lang_display': lang_map.get(t_lang, t_lang),
                    'quote': t_quote,
                    'quote_html': format_translation_text(t_quote, back_data)
                })

        if def_node is not None:
            sense_data.update({
                "definition_html": tei_to_html(def_node, back_data),
                "definition": tei_to_markdown(def_node)
            })
        
        source_ref = sense_el.find("tei:ref[@type='source']", NS)
        if source_ref is not None:
            sense_data['def_source_abbr'] = source_ref.text
            raw_target = source_ref.get('target', '')
            if raw_target.startswith('http'):
                sense_data['def_source_url'] = raw_target
                sense_data['def_source_target'] = raw_target
                target_id = None
            else:
                target_id = raw_target.lstrip('#')
                sense_data['def_source_target'] = target_id
            
            sense_data['def_source_title'] = get_bibl_title(target_id, source_ref.text)
            sense_data['def_source_date'] = source_ref.get('accessDate', '')
        
        data['senses'].append(sense_data)

    # --- Parsing Equivalents ---
    for cit_el in entry_element.findall("./tei:cit[@type='translation']", NS):
        if word := cit_el.findtext("tei:quote", namespaces=NS):
            lang_code = cit_el.get(xml_lang_attr)
            
            region_val = cit_el.findtext("tei:usg[@type='region']", default="", namespaces=NS)
            pos_val = ""
            gram_grp_equiv = cit_el.find("tei:gramGrp", NS)
            if gram_grp_equiv is not None:
                pos_val = gram_grp_equiv.findtext("tei:pos", default="", namespaces=NS)

            defs_list = []
            for d in cit_el.findall('tei:def', NS):
                def_obj = {'text': d.text.strip() if d.text else ""}
                ref = d.find("tei:ref[@type='source']", NS)
                if ref is not None:
                    def_obj['source'] = ref.get('target', '').lstrip('#')
                    def_obj['source_abbr'] = ref.text
                defs_list.append(def_obj)

            data['equivalents'].append({
                "lang": lang_code,
                "lang_display": lang_map.get(lang_code, lang_code),
                "lang_full": lang_full_map.get(lang_code, lang_code),
                "word": word,
                "region": region_val,
                "pos": pos_val,
                "defs": defs_list
            })

    if data['equivalents']:
        data['equivalents'].sort(
            key=lambda x: locale.strxfrm(x['lang_display'] or ''))

    for note_type in ["variants", "entry"]:
        note_node = entry_element.find(f"tei:note[@type='{note_type}']", NS)
        if note_node is not None:
            data[f'{note_type}_note_html'] = tei_note_to_html(note_node)
            data[f'{note_type}_note_markdown'] = tei_note_to_markdown(
                note_node)

    etym_de = entry_element.find("tei:etym[@type='german']", NS)
    if etym_de is not None:
        form_de = etym_de.find("tei:form", NS)
        if form_de is not None:
            data.update({
                'german_orth': get_text(form_de, 'tei:orth'),
                'german_stress': get_text(form_de, 'tei:stress'),
                'german_form_usg_hist': get_text(form_de, "tei:usg[@type='hist']"),
                'german_head_time': get_text(form_de, "tei:usg[@type='time']") 
            })
            
            for usg in form_de.findall("tei:usg", NS):
                usg_type = usg.get('type')
                if usg_type == 'geo':
                    data['german_head_geo'].append(usg.text)
                elif usg_type == 'style':
                    val = usg.text
                    if val in terr_style_abbrs:
                        data['german_head_region_style'].append(val)
                    else:
                        data['german_head_style'].append(val)

            all_borrowed_els = form_de.findall("tei:borrowed", NS)

            borrowed_el = next(
                (el for el in all_borrowed_els if 'type' not in el.attrib), None)
            if borrowed_el is not None:
                data['german_etym']['borrowed'] = borrowed_el.text.strip(
                ) if borrowed_el.text else ""
                data['german_etym']['borrowed_lang'] = borrowed_el.get(
                    xml_lang_attr, "")
            else:
                data['german_etym']['borrowed'] = ""
                data['german_etym']['borrowed_lang'] = ""

            alter_borrowed_els = [
                el for el in all_borrowed_els if el.get('type') == 'alter']
            for el in alter_borrowed_els:
                data['alter_german_etyms'].append({
                    'word': el.text.strip() if el.text else "",
                    'lang': el.get(xml_lang_attr, "")
                })

        etym_comment_node = etym_de.find("tei:note[@type='etym_comment']", NS)
        if etym_comment_node is not None:
            data['etym_comment_html'] = tei_note_to_html(etym_comment_node)
            data['etym_comment_markdown'] = tei_note_to_markdown(
                etym_comment_node)

        gram_grp_de = etym_de.find('tei:gramGrp', NS)
        if gram_grp_de is not None:
            data.update({
                'german_pos': get_text(gram_grp_de, 'tei:pos'), 'german_gen': get_text(gram_grp_de, 'tei:gen'),
                'german_aspect': get_text(gram_grp_de, "tei:trait[@type='aspect']"),
                'german_transitivity': get_text(gram_grp_de, "tei:trait[@type='transitivity']")
            })

        data['lang_sourse'] = get_text(
            etym_de, "tei:note[@type='source_type']")
        borrowing_note = etym_de.find("tei:note[@type='borrowing']", NS)
        if borrowing_note is not None:
            for trait in borrowing_note.findall("tei:trait", NS):
                trait_type = trait.get("type")
                trait_text = trait.text.strip() if trait.text else ""
                if trait_type and trait_text:
                    if trait_type in ["type", "path", "certainty"]:
                        data[f"borrowing_{trait_type}"] = trait_text
                    elif trait_type == "mediator":
                        data['borrowing_mediators'].append(trait_text)
                    elif trait_type == "alter_donor":
                        data['alter_donors'].append(trait_text)

        german_sense_list = etym_de.find('tei:list[@type="ordered"]', NS)
        if german_sense_list is not None:
            for item_node in german_sense_list.findall('tei:item', NS):
                def_node_de = item_node.find("tei:def[@xml:lang='de']", NS)
                if def_node_de is not None:
                    german_sense_data = {
                        'style': [],
                        'examples': [],
                        'domain': [],
                        'translations': [],
                        'geo': [], 'geo_display': [],
                        'region_display': None
                    }
                    for usg in item_node.findall('tei:usg', NS):
                        if usg_type := usg.get("type"):
                            if usg_type == 'style':
                                # --- ВИПРАВЛЕНО: Шукаємо скорочення для стилів ---
                                val = usg.text.strip() if usg.text else ""
                                if val:
                                    info = style_info_map.get(val, {'abbr': val, 'full': val})
                                    german_sense_data['style'].append(info)
                            
                            elif usg_type == 'domain':
                                german_sense_data['domain'].append(
                                    usg.text or "")
                            
                            elif usg_type == 'geo':
                                val = usg.text
                                german_sense_data['geo'].append(val)
                                
                                if val in region_info_map:
                                    info = region_info_map[val]
                                    german_sense_data['geo_display'].append({
                                        'abbr': info['abbr'], 'full': info['full']
                                    })
                                elif val in lang_term_map:
                                    german_sense_data['geo_display'].append(lang_term_map[val])
                                else:
                                    german_sense_data['geo_display'].append({'abbr': val, 'full': val})

                            elif usg_type == 'region':
                                german_sense_data['region'] = usg.text or ""
                                info = region_info_map.get(german_sense_data['region'], {})
                                german_sense_data['region_display'] = {
                                    'abbr': info.get('abbr', german_sense_data['region']),
                                    'full': info.get('full', german_sense_data['region'])
                                }
                            else:
                                german_sense_data[usg_type] = usg.text or ""
                    
                    if german_sense_data['geo']:
                        german_sense_data['geo'] = list(dict.fromkeys(german_sense_data['geo']))
                    if german_sense_data['geo_display']:
                        unique_geo = {item['full']: item for item in german_sense_data['geo_display']}.values()
                        german_sense_data['geo_display'] = list(unique_geo)

                    for c_node in item_node.findall("tei:cit[@type='example']", NS):
                        q_node = c_node.find('tei:quote', NS)
                        if q_node is not None:
                            bibl_target_id = find_bibl_target_for_cit(c_node)
                            source_abbr = get_text(c_node, ".//tei:abbr")
                            german_sense_data['examples'].append({
                                "quote_html": tei_to_html(q_node, back_data), 
                                "quote": tei_to_markdown(q_node),
                                "source_abbr": source_abbr, 
                                "bibl_target": bibl_target_id,
                                "source_title": get_bibl_title(bibl_target_id, source_abbr)
                            })
                    
                    for trans_node in item_node.findall("tei:cit[@type='translation']", NS):
                        t_lang = trans_node.get(xml_lang_attr)
                        t_quote = trans_node.findtext("tei:quote", default="", namespaces=NS)
                        if t_lang and t_quote:
                            german_sense_data['translations'].append({
                                'lang': t_lang,
                                'lang_display': lang_map.get(t_lang, t_lang),
                                'quote': t_quote,
                                'quote_html': format_translation_text(t_quote, back_data)
                            })

                    german_sense_data.update({
                        "definition_html": tei_to_html(def_node_de, back_data),
                        "definition": tei_to_markdown(def_node_de)
                    })
                    
                    source_ref = item_node.find("tei:ref[@type='source']", NS)
                    if source_ref is not None:
                        german_sense_data['def_source_abbr'] = source_ref.text
                        raw_target = source_ref.get('target', '')
                        if raw_target.startswith('http'):
                            german_sense_data['def_source_url'] = raw_target
                            german_sense_data['def_source_target'] = raw_target
                            target_id = None
                        else:
                            target_id = raw_target.lstrip('#')
                            german_sense_data['def_source_target'] = target_id
                        
                        german_sense_data['def_source_title'] = get_bibl_title(target_id, source_ref.text)
                        german_sense_data['def_source_date'] = source_ref.get('accessDate', '')

                    data['german_senses'].append(german_sense_data)

    data['gram_display'], data['gram_tooltip'] = build_gram_display(back_data, data.get(
        'pos'), data.get('gram_gen'), data.get('transitivity'), data.get('aspect'), lang='uk')
    data['german_gram_display'], data['german_gram_tooltip'] = build_gram_display(back_data, data.get(
        'german_pos'), data.get('german_gen'), data.get('german_transitivity'), data.get('german_aspect'), lang='de')

    data['orth_stress'] = data.get('stress') or data.get('orth', '')

    main_info_parts = []
    if data.get('senses'):
        first_time_val = next((sense.get('time') for sense in data['senses'] if sense.get('time')), None)
        if first_time_val:
            data['first_sense_time'] = first_time_val

    if gram_display := data.get('gram_display'):
        main_info_parts.append(
            {'type': 'abbr', 'value': gram_display, 'title': data.get('gram_tooltip', '')})

    if casus_gen := data.get('casus_gen'):
        main_info_parts.append({'type': 'text', 'value': casus_gen})

    data['main_info_parts'] = main_info_parts
    data['german_orth_stress'] = data.get('german_stress', '')

    german_info_parts = []
    language_abbr_map = back_data.get('language_abbr_map', {})

    if val := data.get('german_form_usg_hist'):
        info = language_abbr_map.get(val, {})
        german_info_parts.append(
            {'type': 'abbr', 'value': val, 'title': info.get('full', val)})

    if data.get('german_senses') and (time_val := data['german_senses'][0].get('time')):
        german_info_parts.append({'type': 'text', 'value': time_val})

    if data.get('german_senses') and (domain_list := data['german_senses'][0].get('domain')):
        for domain_val in domain_list:
            domain_info = domain_info_map.get(domain_val)
            if domain_info and domain_info.get('abbr'):
                german_info_parts.append(
                    {'type': 'abbr', 'value': domain_info['abbr'], 'title': domain_info['full']})
            else:
                found_main_domain = next((d for d in back_data.get('domains', []) if d.get(
                    'abbr') == domain_val or d.get('term') == domain_val), None)
                if found_main_domain:
                    german_info_parts.append(
                        {'type': 'abbr', 'value': found_main_domain['abbr'], 'title': found_main_domain['term']})
                else:
                    german_info_parts.append(
                        {'type': 'text', 'value': domain_val})

    if val := data.get('german_gram_display'):
        german_info_parts.append(
            {'type': 'abbr', 'value': val, 'title': data.get('german_gram_tooltip', '')})

    if val := data.get('lang_sourse'):
        if val != 'native':
            german_info_parts.append({'type': 'text', 'value': val})

    if etym_data := data.get('german_etym'):
        lang_code = etym_data.get('borrowed_lang')
        etym_text = etym_data.get('borrowed')
        if lang_code and etym_text:
            abbr = lang_map.get(lang_code)
            full_name = lang_full_map.get(lang_code)
            if abbr and full_name:
                data['german_etym_info'] = {
                    'lang_abbr': abbr,
                    'lang_full': full_name,
                    'text': add_tooltips_to_text(html.escape(etym_text), back_data)
                }

    data['german_info_parts'] = german_info_parts

    borrowing_info_parts = []
    borrowing_chars = back_data.get('borrowing_characteristics', [])

    def find_term_in_b_chars(type_id, value):
        category = next(
            (cat for cat in borrowing_chars if cat.get('id') == type_id), None)
        if category:
            item = next((child for child in category.get(
                'children', []) if child.get('value') == value), None)
            return item['term'] if item else value
        return value

    if val := data.get('borrowing_type'):
        display_val = find_term_in_b_chars('borrowing_type', val)
        borrowing_info_parts.append(
            f"<strong>{gettext('Type')}:</strong> {display_val}")

    if val := data.get('borrowing_path'):
        display_val = find_term_in_b_chars('borrowing_path', val)
        borrowing_info_parts.append(
            f"<strong>{gettext('Path')}:</strong> {display_val}")

    if mediators := data.get('borrowing_mediators'):
        mediators_str = f" {gettext('or')} ".join(mediators)
        borrowing_info_parts.append(
            f"<strong>{gettext('мова-посередник')}:</strong> {mediators_str}")

    if alter_donors := data.get('alter_donors'):
        donors_str = f" {gettext('or')} ".join(alter_donors)
        borrowing_info_parts.append(
            f"<strong>{gettext('Alternative source language')}:</strong> {donors_str}")

    if val := data.get('borrowing_certainty'):
        display_val = find_term_in_b_chars('borrowing_certainty', val)
        borrowing_info_parts.append(
            f"<strong>{gettext('Certainty')}:</strong> {display_val}")

    data['borrowing_info_html'] = " • ".join(borrowing_info_parts)
    
    # --- СОРТУВАННЯ ВАРІАНТІВ (Ігноруючи наголоси) ---
    if data['variants']:
        def variant_sort_key(var_item):
            text = var_item.get('orth', '')
            clean_text = text.replace('\u0301', '')
            return locale.strxfrm(clean_text.lower())
        data['variants'].sort(key=variant_sort_key)

    return data


def update_entry_from_form(entry_element, root, form_data):
    original_attributes = dict(entry_element.attrib)
    xml_lang_attr = f"{{{NS['xml']}}}lang"

    entry_element.clear()
    entry_element.attrib.update(original_attributes)

    def get(key, default=""): return form_data.get(key, default).strip()

    entry_element.set('status', 'complete' if get(
        'status') == 'complete' else 'incomplete')

    if orth_text := get('orth'):
        form_uk = ET.SubElement(entry_element, f"{{{NS['tei']}}}form", {
                                'type': "lemma", xml_lang_attr: "uk"})
        ET.SubElement(form_uk, f"{{{NS['tei']}}}orth").text = orth_text
        if stress_text := get('stress'):
            ET.SubElement(form_uk, f"{{{NS['tei']}}}stress").text = stress_text
        
        for geo in form_data.getlist('lemma_geo'):
            if geo: ET.SubElement(form_uk, f"{{{NS['tei']}}}usg", {'type': 'geo'}).text = geo
        
        for r_style in form_data.getlist('lemma_region_style'):
            if r_style: ET.SubElement(form_uk, f"{{{NS['tei']}}}usg", {'type': 'style'}).text = r_style
            
        if lemma_time := get('lemma_time'):
            ET.SubElement(form_uk, f"{{{NS['tei']}}}usg", {'type': 'time'}).text = lemma_time
            
        for style in form_data.getlist('lemma_style'):
            if style: ET.SubElement(form_uk, f"{{{NS['tei']}}}usg", {'type': 'style'}).text = style

    # --- Saving Variants ---
    variants_data = defaultdict(lambda: {'senses': defaultdict(dict)})
    
    for key, value in form_data.items():
        if not key.startswith('variants___'): continue
        parts = key.split('___')
        var_idx = int(parts[1])
        
        if len(parts) == 3:
            field = parts[2]
            # ПРАВИЛЬНА ЛОГІКА ДЛЯ POS:
            if field == 'pos':
                variants_data[var_idx][field] = value # Зберігаємо як рядок
            elif field in ['geo', 'style', 'region_style']:
                variants_data[var_idx][field] = form_data.getlist(key)
            else:
                variants_data[var_idx][field] = value
        elif len(parts) == 5 and parts[2] == 'senses':
            sense_idx = int(parts[3])
            field = parts[4]
            if field in ['geo', 'style', 'region_style']:
                variants_data[var_idx]['senses'][sense_idx][field] = form_data.getlist(key)
            else:
                variants_data[var_idx]['senses'][sense_idx][field] = value

    for i in sorted(variants_data.keys()):
        v_data = variants_data[i]
        orth = v_data.get('orth', '').strip()
        
        if orth:
            form_var = ET.SubElement(entry_element, f"{{{NS['tei']}}}form", {'type': 'variant'})
            ET.SubElement(form_var, f"{{{NS['tei']}}}orth").text = orth
            
            # Зберігаємо PoS, якщо є (з перевіркою типу)
            if pos_val := v_data.get('pos'):
                if isinstance(pos_val, list):
                    pos_val = pos_val[0] if pos_val else ""
                
                gg = ET.SubElement(form_var, f"{{{NS['tei']}}}gramGrp")
                ET.SubElement(gg, f"{{{NS['tei']}}}pos").text = pos_val

            if val := v_data.get('time'):
                ET.SubElement(form_var, f"{{{NS['tei']}}}usg", {'type': 'time'}).text = val

            for geo in v_data.get('geo', []):
                if geo: ET.SubElement(form_var, f"{{{NS['tei']}}}usg", {'type': 'geo'}).text = geo
            for rs in v_data.get('region_style', []):
                if rs: ET.SubElement(form_var, f"{{{NS['tei']}}}usg", {'type': 'style'}).text = rs
            for st in v_data.get('style', []):
                if st: ET.SubElement(form_var, f"{{{NS['tei']}}}usg", {'type': 'style'}).text = st
            
            if s_id := v_data.get('source'):
                ref = ET.SubElement(form_var, f"{{{NS['tei']}}}ref", {'type': 'source', 'target': f"#{s_id}"})
                if s_abbr := v_data.get('source_abbr'):
                    ref.text = s_abbr

            senses_dict = v_data.get('senses', {})
            for j in sorted(senses_dict.keys()):
                s_data = senses_dict[j]
                if s_data.get('def') or s_data.get('time') or s_data.get('geo') or s_data.get('source'):
                    sense_el = ET.SubElement(form_var, f"{{{NS['tei']}}}sense")
                    if def_text := s_data.get('def'):
                        markdown_to_tei(def_text, ET.SubElement(sense_el, f"{{{NS['tei']}}}def"))
                    if time_val := s_data.get('time'):
                        ET.SubElement(sense_el, f"{{{NS['tei']}}}usg", {'type': 'time'}).text = time_val
                    for geo in s_data.get('geo', []):
                        if geo: ET.SubElement(sense_el, f"{{{NS['tei']}}}usg", {'type': 'geo'}).text = geo
                    for rs in s_data.get('region_style', []):
                        if rs: ET.SubElement(sense_el, f"{{{NS['tei']}}}usg", {'type': 'style'}).text = rs
                    for st in s_data.get('style', []):
                        if st: ET.SubElement(sense_el, f"{{{NS['tei']}}}usg", {'type': 'style'}).text = st
                    if s_id := s_data.get('source'):
                        ref = ET.SubElement(sense_el, f"{{{NS['tei']}}}ref", {'type': 'source', 'target': f"#{s_id}"})
                        if s_abbr := s_data.get('source_abbr'):
                            ref.text = s_abbr

    entry_element.set('type', get('entry_type', 'normal'))

    if get('entry_type') == 'redirect':
        if redirect_input := get('redirect_target'):
            xr_el = ET.SubElement(entry_element, f"{{{NS['tei']}}}xr")
            ET.SubElement(xr_el, f"{{{NS['tei']}}}lbl").text = "див."
            for target_id in redirect_input.split(','):
                if target_id := target_id.strip():
                    ET.SubElement(xr_el, f"{{{NS['tei']}}}ref", {
                                  'target': f'#{target_id}'}).text = target_id
        return entry_element

    gram_fields = ['pos', 'gram_gen', 'casus_gen', 'transitivity', 'aspect']
    if any(get(k) for k in gram_fields):
        gram_grp = ET.SubElement(entry_element, f"{{{NS['tei']}}}gramGrp")
        if val := get('pos'):
            ET.SubElement(gram_grp, f"{{{NS['tei']}}}pos").text = val
        if val := get('gram_gen'):
            ET.SubElement(gram_grp, f"{{{NS['tei']}}}gen").text = val
        if val := get('casus_gen'):
            ET.SubElement(gram_grp, f"{{{NS['tei']}}}casus", {
                          'type': "genitive", 'subtype': "singular"}).text = val
        if val := get('transitivity'):
            ET.SubElement(gram_grp, f"{{{NS['tei']}}}trait", {
                          'type': "transitivity"}).text = val
        if val := get('aspect'):
            ET.SubElement(gram_grp, f"{{{NS['tei']}}}trait", {
                          'type': "aspect"}).text = val

    senses_data = defaultdict(lambda: {
        'examples': defaultdict(dict),
        'translations': defaultdict(dict) 
    })
    sense_indices = sorted(list(set([int(re.search(r'senses___(\d+)___', key).group(1))
                           for key in form_data if re.search(r'senses___(\d+)___', key)])))

    for i in sense_indices:
        sense_data_item = senses_data[i]
        sense_data_item['definition'] = get(f'senses___{i}___definition')
        sense_data_item['def_source_abbr'] = get(f'senses___{i}___def_source_abbr')
        sense_data_item['def_source_url'] = get(f'senses___{i}___def_source_url')
        sense_data_item['def_source_date'] = get(f'senses___{i}___def_source_date') 
        sense_data_item['time'] = get(f'senses___{i}___time')
        sense_data_item['region'] = get(f'senses___{i}___region')
        raw_geo = form_data.getlist(f'senses___{i}___geo')
        sense_data_item['geo'] = list(dict.fromkeys(raw_geo))
        
        sense_data_item['domain'] = form_data.getlist(f'senses___{i}___domain')
        sense_data_item['style'] = form_data.getlist(f'senses___{i}___style')

        example_keys = [k for k in form_data if re.match(
            f'senses___{i}___examples___\d+___quote', k)]
        example_indices = sorted(list(
            set([int(re.search(r'examples___(\d+)___', k).group(1)) for k in example_keys])))
        for j in example_indices:
            sense_data_item['examples'][j] = {
                'quote': get(f'senses___{i}___examples___{j}___quote'),
                'source_abbr': get(f'senses___{i}___examples___{j}___source_abbr')
            }
        
        trans_keys = [k for k in form_data if re.match(
            f'senses___{i}___translations___\d+___word', k)]
        trans_indices = sorted(list(
            set([int(re.search(r'translations___(\d+)___', k).group(1)) for k in trans_keys])))
        for j in trans_indices:
            sense_data_item['translations'][j] = {
                'lang': get(f'senses___{i}___translations___{j}___lang'),
                'word': get(f'senses___{i}___translations___{j}___word')
            }

    for i in sorted(senses_data.keys()):
        sense_data_item = senses_data[i]
        if (definition := sense_data_item.get('definition', '').strip()) \
            or sense_data_item.get('domain') \
            or sense_data_item.get('translations'):

            sense_el = ET.SubElement(entry_element, f"{{{NS['tei']}}}sense")

            for usg_type in ['time', 'region']:
                if val := sense_data_item.get(usg_type):
                    ET.SubElement(sense_el, f"{{{NS['tei']}}}usg", {
                                  'type': usg_type}).text = val
            
            for geo_val in sense_data_item.get('geo', []):
                if geo_val:
                    ET.SubElement(sense_el, f"{{{NS['tei']}}}usg", {
                                  'type': 'geo'}).text = geo_val

            for domain_val in sense_data_item.get('domain', []):
                if domain_val:
                    ET.SubElement(sense_el, f"{{{NS['tei']}}}usg", {
                                  'type': 'domain'}).text = domain_val

            for style_val in sense_data_item.get('style', []):
                if style_val:
                    ET.SubElement(sense_el, f"{{{NS['tei']}}}usg", {
                                  'type': 'style'}).text = style_val

            if definition:
                markdown_to_tei(definition, ET.SubElement(
                    sense_el, f"{{{NS['tei']}}}def", {xml_lang_attr: "uk"}))
            
            if def_source_abbr := sense_data_item.get('def_source_abbr'):
                ref_attrs = {'type': 'source'}
                if def_source_url := sense_data_item.get('def_source_url'):
                    ref_attrs['target'] = def_source_url
                elif target := find_bibl_id_by_abbr(def_source_abbr, root):
                    ref_attrs['target'] = target
                
                if def_source_date := sense_data_item.get('def_source_date'):
                    ref_attrs['accessDate'] = def_source_date

                ref_el = ET.SubElement(sense_el, f"{{{NS['tei']}}}ref", ref_attrs)
                ref_el.text = def_source_abbr

            for j in sorted(sense_data_item['translations'].keys()):
                tr = sense_data_item['translations'][j]
                if tr.get('word'):
                    cit = ET.SubElement(sense_el, f"{{{NS['tei']}}}cit", {
                        'type': 'translation', xml_lang_attr: tr.get('lang', 'de')})
                    ET.SubElement(cit, f"{{{NS['tei']}}}quote").text = tr.get('word')

            for j in sorted(sense_data_item['examples'].keys()):
                ex = sense_data_item['examples'][j]
                if (quote := ex.get('quote', '').strip()):
                    cit = ET.SubElement(sense_el, f"{{{NS['tei']}}}cit", {
                                        'type': "example"})
                    markdown_to_tei(quote, ET.SubElement(
                        cit, f"{{{NS['tei']}}}quote"))
                    if source := ex.get('source_abbr', '').strip():
                        ET.SubElement(ET.SubElement(
                            cit, f"{{{NS['tei']}}}ref"), f"{{{NS['tei']}}}abbr").text = source

    # --- Saving Equivalents ---
    equivalents_data = defaultdict(lambda: {'defs': defaultdict(dict)})
    
    equiv_pattern = re.compile(
        r'^equivalents___(\d+)___(lang|word|region|pos|defs___(\d+)___(text|source|source_abbr))$')
    
    for key, value in form_data.items():
        match = equiv_pattern.match(key)
        if match:
            idx = int(match.group(1))
            field_type = match.group(2)
            
            if field_type in ['lang', 'word', 'region', 'pos']:
                equivalents_data[idx][field_type] = value
            else:
                # Поля дефініції
                def_idx = int(match.group(3))
                sub_field = match.group(4)
                equivalents_data[idx]['defs'][def_idx][sub_field] = value

    for i in sorted(equivalents_data.keys()):
        equiv = equivalents_data[i]
        lang = (equiv.get('lang') or "").strip()
        word = (equiv.get('word') or "").strip()
        
        if lang and word:
            cit = ET.SubElement(entry_element, f"{{{NS['tei']}}}cit", {
                'type': 'translation', xml_lang_attr: lang
            })
            ET.SubElement(cit, f"{{{NS['tei']}}}quote").text = word
            
            if val := equiv.get('region'):
                ET.SubElement(cit, f"{{{NS['tei']}}}usg", {'type': 'region'}).text = val
            
            if val := equiv.get('pos'):
                gg = ET.SubElement(cit, f"{{{NS['tei']}}}gramGrp")
                ET.SubElement(gg, f"{{{NS['tei']}}}pos").text = val

# ... всередині циклу for i in sorted(equivalents_data.keys()): ...
            
            # Зберігаємо Дефініції
            for k in sorted(equiv['defs'].keys()):
                d_data = equiv['defs'][k]
                def_text = d_data.get('text', '').strip()
                source_id = d_data.get('source') # Отримуємо ID джерела
                
                # ВИПРАВЛЕННЯ: Зберігаємо, якщо є текст АБО джерело
                if def_text or source_id:
                    def_el = ET.SubElement(cit, f"{{{NS['tei']}}}def")
                    
                    if def_text:
                        def_el.text = def_text
                    
                    if source_id:
                        ref = ET.SubElement(def_el, f"{{{NS['tei']}}}ref", {
                            'type': 'source', 
                            'target': f"#{source_id}"
                        })
                        if s_abbr := d_data.get('source_abbr'):
                            ref.text = s_abbr

    for note_type in ["variants", "entry"]:
        if md_text := get(f"{note_type}_note_markdown"):
            markdown_to_tei_note(md_text, ET.SubElement(
                entry_element, f"{{{NS['tei']}}}note", {'type': note_type}))

    # --- 1. Оновлена логіка створення etym_de ---
    # Перевіряємо, чи є хоч якісь дані для німецького блоку
    german_gram_fields = ['german_pos', 'german_gen', 'german_transitivity', 'german_aspect']
    has_german_form = bool(get('german_orth'))
    has_german_gram = any(get(k) for k in german_gram_fields)
    has_borrowing = any([get(f'borrowing_{t}') for t in ['type', 'path', 'certainty']]) or \
                    any(get(k) for k in ['lang_sourse', 'borrowing_mediator']) or \
                    form_data.getlist('borrowing_mediators') or \
                    form_data.getlist('alter_donors')
    has_etym_notes = bool(get('etym_comment') or get('german_etym_borrowed'))
    
    # Також перевіряємо, чи є німецькі значення
    german_sense_keys = [k for k in form_data.keys() if 'german_senses___' in k]
    has_german_senses = len(german_sense_keys) > 0

    # Створюємо etym_de, якщо є будь-які дані
    etym_de = None
    if has_german_form or has_german_gram or has_borrowing or has_etym_notes or has_german_senses:
        etym_de = ET.SubElement(entry_element, f"{{{NS['tei']}}}etym", {'type': "german"})

    # Тепер заповнюємо дані, якщо etym_de створено
    if etym_de is not None:
        if get('german_orth'):
            form_de = ET.SubElement(etym_de, f"{{{NS['tei']}}}form")
            ET.SubElement(form_de, f"{{{NS['tei']}}}orth").text = get('german_orth')
            if val := get('german_stress'):
                ET.SubElement(form_de, f"{{{NS['tei']}}}stress").text = val
            if val := get('german_form_usg_hist'):
                ET.SubElement(form_de, f"{{{NS['tei']}}}usg", {'type': 'hist'}).text = val

            for geo in form_data.getlist('german_head_geo'):
                if geo: ET.SubElement(form_de, f"{{{NS['tei']}}}usg", {'type': 'geo'}).text = geo
            
            for r_style in form_data.getlist('german_head_region_style'):
                if r_style: ET.SubElement(form_de, f"{{{NS['tei']}}}usg", {'type': 'style'}).text = r_style
                
            if g_time := get('german_head_time'):
                ET.SubElement(form_de, f"{{{NS['tei']}}}usg", {'type': 'time'}).text = g_time
                
            for style in form_data.getlist('german_head_style'):
                if style: ET.SubElement(form_de, f"{{{NS['tei']}}}usg", {'type': 'style'}).text = style

            if borrowed := get('german_etym_borrowed'):
                borrowed_el = ET.SubElement(form_de, f"{{{NS['tei']}}}borrowed")
                borrowed_el.text = borrowed
                if borrowed_lang := get('german_etym_borrowed_lang'):
                    borrowed_el.set(xml_lang_attr, borrowed_lang)

            alter_etym_data = defaultdict(dict)
            alter_etym_pattern = re.compile(r'^alter_german_etym___(\d+)___(lang|word)$')
            for key, value in form_data.items():
                match = alter_etym_pattern.match(key)
                if match:
                    idx, field = match.groups()
                    alter_etym_data[int(idx)][field] = value

            for i in sorted(alter_etym_data.keys()):
                item_data = alter_etym_data[i]
                lang = item_data.get('lang')
                word = item_data.get('word', '').strip()
                if lang and word:
                    ET.SubElement(form_de, f"{{{NS['tei']}}}borrowed", {
                        'type': 'alter',
                        xml_lang_attr: lang
                    }).text = word

        if any(get(k) for k in german_gram_fields):
            gram_grp_de = ET.SubElement(etym_de, f"{{{NS['tei']}}}gramGrp")
            for field in german_gram_fields:
                if val := get(field):
                    tag_name = 'pos' if field == 'german_pos' else 'gen' if field == 'german_gen' else 'trait'
                    el = ET.SubElement(gram_grp_de, f"{{{NS['tei']}}}{tag_name}")
                    el.text = val
                    if tag_name == 'trait':
                        el.set('type', 'transitivity' if 'transitivity' in field else 'aspect')

        if etym_comment_md := get('etym_comment'):
            markdown_to_tei_note(etym_comment_md, ET.SubElement(
                etym_de, f"{{{NS['tei']}}}note", {'type': 'etym_comment'}))

        # --- German Senses ---
        german_senses_data = defaultdict(lambda: {
            'examples': defaultdict(dict),
            'translations': defaultdict(dict)
        })
        german_sense_indices = sorted(list(set([int(re.search(r'german_senses___(\d+)___', key).group(
            1)) for key in form_data if re.search(r'german_senses___(\d+)___', key)])))

        for i in german_sense_indices:
            sense_data_item = german_senses_data[i]
            sense_data_item['definition'] = get(f'german_senses___{i}___definition')
            sense_data_item['def_source_abbr'] = get(f'german_senses___{i}___def_source_abbr')
            sense_data_item['def_source_url'] = get(f'german_senses___{i}___def_source_url')
            sense_data_item['def_source_date'] = get(f'german_senses___{i}___def_source_date') 
            sense_data_item['time'] = get(f'german_senses___{i}___time')
            sense_data_item['region'] = get(f'german_senses___{i}___region')
            raw_geo = form_data.getlist(f'german_senses___{i}___geo')
            sense_data_item['geo'] = list(dict.fromkeys(raw_geo))
            sense_data_item['domain'] = form_data.getlist(f'german_senses___{i}___domain')
            
            # --- ВИПРАВЛЕННЯ: Зчитуємо стилі з форми ---
            sense_data_item['style'] = form_data.getlist(f'german_senses___{i}___style')

            example_keys = [k for k in form_data if re.match(
                f'german_senses___{i}___examples___\d+___quote', k)]
            example_indices = sorted(list(
                set([int(re.search(r'examples___(\d+)___', k).group(1)) for k in example_keys])))

            for j in example_indices:
                sense_data_item['examples'][j] = {
                    'quote': get(f'german_senses___{i}___examples___{j}___quote'),
                    'source_abbr': get(f'german_senses___{i}___examples___{j}___source_abbr')
                }
            
            trans_keys = [k for k in form_data if re.match(
                f'german_senses___{i}___translations___\d+___word', k)]
            trans_indices = sorted(list(
                set([int(re.search(r'translations___(\d+)___', k).group(1)) for k in trans_keys])))
            for j in trans_indices:
                sense_data_item['translations'][j] = {
                    'lang': get(f'german_senses___{i}___translations___{j}___lang'),
                    'word': get(f'german_senses___{i}___translations___{j}___word')
                }

        if german_senses_data:
            list_el = ET.SubElement(etym_de, f"{{{NS['tei']}}}list", {'type': "ordered"})
            for i in sorted(german_senses_data.keys()):
                sense_data_item = german_senses_data[i]
                if (definition := sense_data_item.get('definition', '').strip()) \
                   or sense_data_item.get('translations'):
                    item_el = ET.SubElement(list_el, f"{{{NS['tei']}}}item")

                    if val := sense_data_item.get('time'):
                        ET.SubElement(item_el, f"{{{NS['tei']}}}usg", {'type': 'time'}).text = val
                    if val := sense_data_item.get('region'):
                        ET.SubElement(item_el, f"{{{NS['tei']}}}usg", {'type': 'region'}).text = val
                    
                    for geo_val in sense_data_item.get('geo', []):
                        if geo_val:
                            ET.SubElement(item_el, f"{{{NS['tei']}}}usg", {'type': 'geo'}).text = geo_val

                    for domain_val in sense_data_item.get('domain', []):
                        if domain_val:
                            ET.SubElement(item_el, f"{{{NS['tei']}}}usg", {'type': 'domain'}).text = domain_val

                    # --- ВИПРАВЛЕННЯ: Зберігаємо стилі як текст ---
                    for style_val in sense_data_item.get('style', []):
                        if style_val:
                            ET.SubElement(item_el, f"{{{NS['tei']}}}usg", {'type': 'style'}).text = style_val
                    
                    if definition:
                        markdown_to_tei(definition, ET.SubElement(
                            item_el, f"{{{NS['tei']}}}def", {xml_lang_attr: "de"}))
                    
                    if def_source_abbr := sense_data_item.get('def_source_abbr'):
                        ref_attrs = {'type': 'source'}
                        if def_source_url := sense_data_item.get('def_source_url'):
                            ref_attrs['target'] = def_source_url
                        elif target := find_bibl_id_by_abbr(def_source_abbr, root):
                            ref_attrs['target'] = target
                        if def_source_date := sense_data_item.get('def_source_date'):
                            ref_attrs['accessDate'] = def_source_date
                        ref_el = ET.SubElement(item_el, f"{{{NS['tei']}}}ref", ref_attrs)
                        ref_el.text = def_source_abbr

                    for j in sorted(sense_data_item['translations'].keys()):
                        tr = sense_data_item['translations'][j]
                        if tr.get('word'):
                            cit = ET.SubElement(item_el, f"{{{NS['tei']}}}cit", {
                                'type': 'translation', xml_lang_attr: tr.get('lang', 'uk')})
                            ET.SubElement(cit, f"{{{NS['tei']}}}quote").text = tr.get('word')

                    for j in sorted(sense_data_item['examples'].keys()):
                        ex = sense_data_item['examples'][j]
                        if (quote := ex.get('quote', '').strip()):
                            cit = ET.SubElement(item_el, f"{{{NS['tei']}}}cit", {
                                                'type': "example"})
                            markdown_to_tei(quote, ET.SubElement(
                                cit, f"{{{NS['tei']}}}quote"))
                            if source := ex.get('source_abbr', '').strip():
                                ET.SubElement(ET.SubElement(
                                    cit, f"{{{NS['tei']}}}ref"), f"{{{NS['tei']}}}abbr").text = source

        if get('lang_sourse'):
            ET.SubElement(etym_de, f"{{{NS['tei']}}}note", {'type': 'source_type'}).text = get('lang_sourse')

        all_mediators = [m for m in [get('borrowing_mediator')] + form_data.getlist('borrowing_mediators') if m]
        all_donors = [d for d in form_data.getlist('alter_donors') if d]
        
        if any([get(f'borrowing_{t}') for t in ['type', 'path', 'certainty']]) or all_mediators or all_donors:
            note = ET.SubElement(etym_de, f"{{{NS['tei']}}}note", {'type': "borrowing"})
            for t in ['type', 'path', 'certainty']:
                if val := get(f'borrowing_{t}'):
                    ET.SubElement(note, f"{{{NS['tei']}}}trait", {'type': t}).text = val
            for m in all_mediators:
                ET.SubElement(note, f"{{{NS['tei']}}}trait", {'type': 'mediator'}).text = m
            for d in all_donors:
                ET.SubElement(note, f"{{{NS['tei']}}}trait", {'type': 'alter_donor'}).text = d

    bibl_data = defaultdict(dict)
    bibl_pattern = re.compile(r'^bibliography___(\d+)___(.*)$')
    for key, value in form_data.items():
        match = bibl_pattern.match(key)
        if match:
            idx, field = match.groups()
            bibl_data[int(idx)][field] = value

    if bibl_data:
        listBibl = root.find(
            ".//tei:div[@type='bibliography']/tei:listBibl", NS)
        if listBibl is None:
            back_node = root.find(".//tei:back", NS) or ET.SubElement(
                root.find(".//tei:text", NS), f"{{{NS['tei']}}}back")
            bibl_div = ET.SubElement(back_node, f"{{{NS['tei']}}}div", {
                                     'type': 'bibliography'})
            listBibl = ET.SubElement(bibl_div, f"{{{NS['tei']}}}listBibl")

        xml_id_key = f"{{{NS['xml']}}}id"
        for i in sorted(bibl_data.keys()):
            item_data = bibl_data[i]
            bibl_id = item_data.get('id')
            target_id = None
            if bibl_id == 'new':
                new_abbr, new_title, new_url = item_data.get(
                    'new_abbr'), item_data.get('new_title'), item_data.get('new_url')
                if new_abbr and new_title:
                    target_id = "bibl_" + slugify(new_abbr)
                    if listBibl.find(f"tei:bibl[@{xml_id_key}='{target_id}']", NS) is None:
                        new_bibl_el = ET.SubElement(listBibl, f"{{{NS['tei']}}}bibl", {
                                                    xml_id_key: target_id})
                        ET.SubElement(
                            new_bibl_el, f"{{{NS['tei']}}}abbr").text = new_abbr
                        ET.SubElement(
                            new_bibl_el, f"{{{NS['tei']}}}title").text = new_title
                        if new_url:
                            ET.SubElement(new_bibl_el, f"{{{NS['tei']}}}ref", {
                                          'target': new_url})
            else:
                target_id = bibl_id

            if target_id:
                ref = ET.SubElement(entry_element, f"{{{NS['tei']}}}ref", {
                                    'type': 'bibliography', 'target': f"#{target_id}"})
                if val := item_data.get('volume'):
                    ET.SubElement(ref, f"{{{NS['tei']}}}volume").text = val
                if val := item_data.get('page'):
                    ET.SubElement(ref, f"{{{NS['tei']}}}page").text = val
    return entry_element