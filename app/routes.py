from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.services.xml_db import db
from app.services.entries import parse_entry_data, update_entry_from_form, parse_entry_header
from app.services.metadata import meta_service
from lxml import etree as ET
from app.config import NS
import locale
import re
from flask import jsonify
from app.services.dwds_service import fetch_dwds_entry

main_bp = Blueprint('main', __name__)

# --- ДОПОМІЖНА ФУНКЦІЯ ДЛЯ АЛФАВІТНОЇ НАВІГАЦІЇ ---
def get_sorted_neighbors(root, current_id):
    entries_list = []
    for entry in root.findall(".//tei:entry", NS):
        eid = entry.get(f"{{{NS['xml']}}}id")
        # Шукаємо лему для сортування
        orth_node = entry.find("tei:form[@type='lemma']/tei:orth", NS)
        orth = orth_node.text.strip() if orth_node is not None and orth_node.text else ""
        entries_list.append({'id': eid, 'orth': orth})
    
    # Сортуємо за алфавітом
    entries_list.sort(key=lambda x: locale.strxfrm(x['orth'].lower()))
    sorted_ids = [e['id'] for e in entries_list]
    
    try:
        curr_idx = sorted_ids.index(current_id)
        prev_id = sorted_ids[curr_idx - 1] if curr_idx > 0 else None
        next_id = sorted_ids[curr_idx + 1] if curr_idx < len(sorted_ids) - 1 else None
        return prev_id, next_id
    except ValueError:
        return None, None

def entry_matches_query(entry_el, query_str, root):
    """
    Універсальний пошуковий рушій по TEI XML
    """
    if not query_str:
        return True

    xml_id_key = f"{{{NS['xml']}}}id"
    tokens = query_str.strip().split()
    
    for token in tokens:
        token_matched = False
        
        # 1. ФІЛЬТР ЗА ДОМЕНАМИ (dom: / domain:)
        if token.startswith(('dom:', 'domain:')):
            val = token.split(':', 1)[1].lower().strip()
            for usg in entry_el.findall(".//tei:usg[@type='domain']", NS):
                if usg.text and (val in usg.text.lower() or val in usg.get('value', '').lower()):
                    token_matched = True
                    break

        # 2. ФІЛЬТР ЗА СТИЛЯМИ / РЕМАРКАМИ (style: / rem:)
        elif token.startswith(('style:', 'rem:')):
            val = token.split(':', 1)[1].lower().strip().rstrip('.')
            for usg in entry_el.findall(".//tei:usg[@type='style']", NS):
                if usg.text:
                    clean_usg = usg.text.lower().rstrip('.')
                    if val in clean_usg or clean_usg.startswith(val):
                        token_matched = True
                        break

        # 3. ФІЛЬТР ЗА ДЖЕРЕЛАМИ / БІБЛІОГРАФІЄЮ (bibl: / src:)
        elif token.startswith(('bibl:', 'src:')):
            val = token.split(':', 1)[1].lower().strip().rstrip('.')
            
            # Шукаємо ID джерела у <back> за його абревіатурою (напр. Желех. -> bibl_zhelekh)
            matched_bibl_ids = set()
            for b in root.findall(".//tei:back//tei:bibl", NS):
                b_id = (b.get(xml_id_key) or '').lower()
                b_abbr = (b.findtext("tei:abbr", default="", namespaces=NS) or '').lower().rstrip('.')
                if val == b_abbr or val in b_abbr or val == b_id or val in b_id:
                    matched_bibl_ids.add(b_id)

            # Шукаємо збіг у ВСІХ тегах <ref> статті (як type="source", так і type="bibliography")
            for ref in entry_el.findall(".//tei:ref", NS):
                target = (ref.get('target') or '').lower().lstrip('#').rstrip('.')
                ref_text = (ref.text or '').lower().strip().rstrip('.')
                
                # 1. Збіг за ID джерела (наприклад, target="#bibl_zhelekh")
                if target in matched_bibl_ids:
                    token_matched = True
                    break
                
                # 2. Прямий збіг за текстом або таргетом
                if val == ref_text or val in ref_text or val in target:
                    token_matched = True
                    break

                # 3. Перевірка вкладеного <abbr>
                abbr_node = ref.find("tei:abbr", NS)
                if abbr_node is not None and abbr_node.text:
                    clean_abbr = abbr_node.text.lower().strip().rstrip('.')
                    if val == clean_abbr or val in clean_abbr:
                        token_matched = True
                        break

        # 4. ФІЛЬТР ЗА РЕГІОНАМИ / ГЕО (geo: / reg:)
        elif token.startswith(('geo:', 'reg:')):
            val = token.split(':', 1)[1].lower().strip()
            for usg in entry_el.findall(".//tei:usg[@type='geo']", NS) + entry_el.findall(".//tei:usg[@type='region']", NS):
                if usg.text and val in usg.text.lower():
                    token_matched = True
                    break

        # 5. ФІЛЬТР ЗА ТИПОМ ЗАПОЗИЧЕННЯ (type:)
        elif token.startswith('type:'):
            val = token.split(':', 1)[1].lower().strip()
            trait = entry_el.find(".//tei:note[@type='borrowing']/tei:trait[@type='type']", NS)
            if trait is not None and trait.text and val in trait.text.lower():
                token_matched = True

        # 6. ФІЛЬТР ЗА ШЛЯХОМ ЗАПОЗИЧЕННЯ (path:)
        elif token.startswith('path:'):
            val = token.split(':', 1)[1].lower().strip()
            trait = entry_el.find(".//tei:note[@type='borrowing']/tei:trait[@type='path']", NS)
            if trait is not None and trait.text and val in trait.text.lower():
                token_matched = True

        # 7. ФІЛЬТР ЗА ЧАСТИНОЮ МОВИ (pos:)
        elif token.startswith('pos:'):
            val = token.split(':', 1)[1].lower().strip()
            for pos_node in entry_el.findall(".//tei:gramGrp/tei:pos", NS):
                if pos_node.text and val in pos_node.text.lower():
                    token_matched = True
                    break

# 8. СУВОРИЙ ПОШУК ЗА ГОЛОВНИМИ ГАСЛАМИ (Тільки українська лема або німецький етимон)
        else:
            val = token.lower().strip().replace('\u0301', '')

            def is_headword_match(target_text):
                if not target_text:
                    return False
                clean_target = target_text.lower().replace('\u0301', '').strip()
                # Гасло починається з пошукового запиту
                if clean_target.startswith(val):
                    return True
                # Якщо гасло складається з кількох слів (наприклад, "новий вал")
                words = clean_target.replace('-', ' ').replace(',', ' ').replace('/', ' ').split()
                return any(w.startswith(val) for w in words if w)

            # А. Перевірка ВИКЛЮЧНО української головної леми
            uk_node = entry_el.find("tei:form[@type='lemma']/tei:orth", NS)
            if uk_node is not None and uk_node.text:
                if is_headword_match(uk_node.text):
                    token_matched = True

            # Б. Перевірка ВИКЛЮЧНО німецького головного етимона
            if not token_matched:
                de_node = entry_el.find(".//tei:etym[@type='german']/tei:form/tei:orth", NS)
                if de_node is not None and de_node.text:
                    if is_headword_match(de_node.text):
                        token_matched = True

        if not token_matched:
            return False

    return True    

@main_bp.route("/")
def index():
    query = request.args.get("q", "").strip()
    lang = request.args.get("lang", "uk") # 'uk' або 'de'
    show_status = request.args.get("show", "all")
    letter_filter = request.args.get("letter", "all")

    tree, root = db.load_xml()
    
    # 1. ОТРИМУЄМО ВСІ ЗАПИСИ
    all_entries = root.findall(".//tei:entry", NS)
    
    # 2. РАХУЄМО СТАТИСТИКУ (Всього / Готово)
    total_count = len(all_entries)
    total_complete_count = sum(1 for e in all_entries if e.get('status') == 'complete')

    entries_to_process = []
    
    # 3. ФІЛЬТРАЦІЯ
    for entry in all_entries:
        # --- ЗМІНА: Передаємо lang у парсер ---
        data = parse_entry_header(entry, target_lang=lang)
        
        # Якщо в цій мові слова немає (наприклад, немає нім. відповідника), пропускаємо
        if not data or not data.get('orth'): 
            continue

        # Фільтр по статусу
        if show_status == 'complete' and data.get('status') != 'complete':
            continue
        if show_status == 'incomplete' and data.get('status') == 'complete':
            continue

# Універсальний пошук (з підтримкою dom:, style:, bibl:, geo: тощо)
        if query:
            if not entry_matches_query(entry, query, root):
                continue

        # Фільтр по літері
        if not query and letter_filter != 'all':
            first_char = (data.get('orth') or '').strip()
            # Перевірка першої літери (враховуємо регістр)
            if not first_char or first_char[0].upper() != letter_filter.upper():
                continue

        entries_to_process.append(data)

    # 4. СОРТУВАННЯ СПИСКУ
    entries_to_process.sort(key=lambda x: locale.strxfrm(x.get('orth', '').lower()))

    # Якщо обрано німецьку мову — групуємо однакові німецькі етимони в один елемент
    if lang == 'de':
        grouped_entries = []
        entries_by_orth = {}

        for item in entries_to_process:
            key = item['orth'].lower()
            if key not in entries_by_orth:
                grouped_item = {
                    'orth': item['orth'],
                    'sub_entries': []
                }
                entries_by_orth[key] = grouped_item
                grouped_entries.append(grouped_item)
            
            entries_by_orth[key]['sub_entries'].append({
                'id': item['id'],
                'status': item['status'],
                'uk_orth': item.get('uk_orth', ''),
                'variants': item.get('variants', [])
            })
        
        entries_to_process = grouped_entries

    # 5. ГЕНЕРАЦІЯ АЛФАВІТУ (Адаптовано під мову)
    # Ми не можемо просто брати українські леми, треба брати ті слова, які ми витягли
    # Найефективніше - пройтися по вже сформованому (але ще не відфільтрованому по літері) списку
    # Але оскільки ми фільтруємо в циклі, зробимо окремий прохід або використаємо XML xpath залежно від мови.
    
    letters_set = set()
    
    # Щоб алфавіт був повним (з усіх слів бази, а не тільки відфільтрованих), 
    # нам треба знати перші літери всіх слів обраної мови.
    if lang == 'de':
        xpath_query = ".//tei:etym[@type='german']/tei:form/tei:orth"
    else:
        xpath_query = "tei:form[@type='lemma']/tei:orth"

    for e in all_entries:
        node = e.find(xpath_query, NS)
        if node is not None and node.text:
            first_char = node.text.strip()[0].upper()
            if first_char.isalpha(): # Беремо тільки літери
                letters_set.add(first_char)

    alphabet = sorted(list(letters_set), key=locale.strxfrm)

    # 6. ВІДПОВІДЬ ДЛЯ AJAX
    if request.args.get('partial_list'):
        return render_template("_word_list.html", entries=entries_to_process)

    # 7. ПОВНА ВІДПОВІДЬ
    stats = {
        'total': total_count,
        'complete': total_complete_count
    }

    return render_template(
        "index.html", 
        entries=entries_to_process, 
        alphabet=alphabet, 
        query=query, 
        lang=lang, 
        stats=stats,
        show_status=show_status,
        current_letter=letter_filter,
        current_lang=lang
    )

@main_bp.route("/entry/<entry_id>")
def view_entry(entry_id):
    tree, root = db.load_xml()
    clean_target = entry_id.strip().lstrip('#')
    xml_id_key = f"{{{NS['xml']}}}id"

    # 1. Прямий пошук за xml:id (наприклад, e338)
    entry_el = root.find(f".//tei:entry[@{xml_id_key}='{clean_target}']", NS)
    
    # 2. Якщо не знайдено за ID — шукаємо за українським або німецьким словом!
    if entry_el is None:
        target_lower = clean_target.lower().replace('\u0301', '')
        for e in root.findall(".//tei:entry", NS):
            # Перевіряємо українську лему
            uk_node = e.find("tei:form[@type='lemma']/tei:orth", NS)
            if uk_node is not None and uk_node.text:
                if uk_node.text.strip().lower().replace('\u0301', '') == target_lower:
                    entry_el = e
                    clean_target = e.get(xml_id_key)
                    break
            
            # Перевіряємо німецький етимон
            de_node = e.find(".//tei:etym[@type='german']/tei:form/tei:orth", NS)
            if de_node is not None and de_node.text:
                if de_node.text.strip().lower() == target_lower:
                    entry_el = e
                    clean_target = e.get(xml_id_key)
                    break
    
    if entry_el is None:
        return f"Entry '{entry_id}' not found", 404
        
    entry_data = parse_entry_data(entry_el, root)
    prev_id, next_id = get_sorted_neighbors(root, clean_target)

    if request.args.get('partial'):
        return render_template("entry_partial.html", entry=entry_data, prev_entry_id=prev_id, next_entry_id=next_id)
        
    return render_template("entry.html", entry=entry_data, prev_entry_id=prev_id, next_entry_id=next_id)

@main_bp.route("/add", methods=["GET", "POST"])
def add_entry():
    tree, root = db.load_xml()
    back_data = meta_service.parse_back_matter(root)
    
    if request.method == "POST":
        # Генерація нового ID
        all_ids = [int(e.get(f"{{{NS['xml']}}}id")[1:]) for e in root.findall(".//tei:entry", NS) if e.get(f"{{{NS['xml']}}}id", "").startswith("e")]
        new_id = f"e{max(all_ids) + 1 if all_ids else 1}"
        
        new_entry = ET.Element(f"{{{NS['tei']}}}entry", {f"{{{NS['xml']}}}id": new_id})
        new_entry = update_entry_from_form(new_entry, root, request.form)
        
        body = root.find(".//tei:body", NS)
        if body is None:
            text_node = root.find(".//tei:text", NS)
            body = ET.SubElement(text_node, f"{{{NS['tei']}}}body")
        
        body.append(new_entry)
        db.save_xml() # Зберігаємо без аргументів
        
        flash(f"Статтю {new_id} створено!", "success")
        
        # Переадресація
        action = request.form.get('action')
        if action == 'save_view':
            return redirect(url_for('main.index', _anchor=new_id))
        else:
            return redirect(url_for('main.edit_entry', entry_id=new_id))

    return render_template("add.html", back_data=back_data, entry={})

@main_bp.route("/edit/<entry_id>", methods=["GET", "POST"])
def edit_entry(entry_id):
    tree, root = db.load_xml()
    entry_el = root.find(f".//tei:entry[@xml:id='{entry_id}']", NS)
    
    if entry_el is None:
        return "Not found", 404

    if request.method == "POST":
        update_entry_from_form(entry_el, root, request.form)
        db.save_xml() # Зберігаємо без аргументів
        
        flash("Зміни збережено!", "success")
        
        # Переадресація
        action = request.form.get('action')
        if action == 'save_view':
            return redirect(url_for('main.index', _anchor=entry_id))
        else:
            return redirect(url_for('main.edit_entry', entry_id=entry_id))

    entry_data = parse_entry_data(entry_el, root)
    back_data = meta_service.parse_back_matter(root)
    prev_id, next_id = get_sorted_neighbors(root, entry_id)
    
    return render_template("edit.html", entry=entry_data, back_data=back_data, prev_entry_id=prev_id, next_entry_id=next_id)

@main_bp.route("/delete/<entry_id>")
def delete_entry(entry_id):
    tree, root = db.load_xml()
    entry_el = root.find(f".//tei:entry[@xml:id='{entry_id}']", NS)
    
    if entry_el is not None:
        parent = entry_el.getparent()
        if parent is not None:
            parent.remove(entry_el)
            db.save_xml()
            flash(f"Статтю {entry_id} видалено.", "success")
        else:
            flash("Помилка: неможливо видалити.", "error")
    else:
        flash("Статтю не знайдено.", "error")
        
    return redirect(url_for('main.index'))

@main_bp.route("/download")
def download_xml():
    return redirect(url_for('static', filename='dictionary.xml'))

@main_bp.route("/api/dwds-fetch")
def api_dwds_fetch():
    lemma = request.args.get("lemma", "").strip()
    if not lemma:
        return jsonify({"status": "error", "message": "Параметр 'lemma' обов'язковий"}), 400
    
    result = fetch_dwds_entry(lemma)
    return jsonify(result)

