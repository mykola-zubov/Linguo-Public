from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.services.xml_db import db
from app.services.entries import parse_entry_data, update_entry_from_form, parse_entry_header
from app.services.metadata import meta_service
from lxml import etree as ET
from app.config import NS
import locale

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

        # Пошук
        if query:
            q_low = query.lower()
            found = False
            # Шукаємо в основному слові (яке зараз залежить від мови)
            if q_low in data.get('orth', '').lower(): found = True
            
            # Шукаємо у варіантах (вони поки що тільки українські)
            if not found:
                for v in data.get('variants', []):
                    if q_low in v.get('orth', '').lower():
                        found = True; break
            if not found: continue

        # Фільтр по літері
        if not query and letter_filter != 'all':
            first_char = (data.get('orth') or '').strip()
            # Перевірка першої літери (враховуємо регістр)
            if not first_char or first_char[0].upper() != letter_filter.upper():
                continue

        entries_to_process.append(data)

    # 4. СОРТУВАННЯ СПИСКУ
    entries_to_process.sort(key=lambda x: locale.strxfrm(x.get('orth', '').lower()))

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
    entry_el = root.find(f".//tei:entry[@xml:id='{entry_id}']", NS)
    
    if entry_el is None:
        return f"Entry {entry_id} not found", 404
        
    entry_data = parse_entry_data(entry_el, root)
    prev_id, next_id = get_sorted_neighbors(root, entry_id)

    if request.args.get('partial'):
        return render_template("entry_partial.html", entry=entry_data, prev_entry_id=prev_id, next_entry_id=next_id)
        
    return render_template("entry.html", entry=entry_data, prev_entry_id=prev_id, next_entry_id=next_id)

@main_bp.route("/add", methods=["GET", "POST"])
# def add_entry():
#     tree, root = db.load_xml()
#     back_data = meta_service.parse_back_matter(root)
    
#     if request.method == "POST":
#         # Генерація нового ID
#         all_ids = [int(e.get(f"{{{NS['xml']}}}id")[1:]) for e in root.findall(".//tei:entry", NS) if e.get(f"{{{NS['xml']}}}id", "").startswith("e")]
#         new_id = f"e{max(all_ids) + 1 if all_ids else 1}"
        
#         new_entry = ET.Element(f"{{{NS['tei']}}}entry", {f"{{{NS['xml']}}}id": new_id})
#         new_entry = update_entry_from_form(new_entry, root, request.form)
        
#         body = root.find(".//tei:body", NS)
#         if body is None:
#             text_node = root.find(".//tei:text", NS)
#             body = ET.SubElement(text_node, f"{{{NS['tei']}}}body")
        
#         body.append(new_entry)
#         db.save_xml() # Зберігаємо без аргументів
        
#         flash(f"Статтю {new_id} створено!", "success")
        
#         # Переадресація
#         action = request.form.get('action')
#         if action == 'save_view':
#             return redirect(url_for('main.index', _anchor=new_id))
#         else:
#             return redirect(url_for('main.edit_entry', entry_id=new_id))

#     return render_template("add.html", back_data=back_data, entry={})

@main_bp.route("/edit/<entry_id>", methods=["GET", "POST"])
# def edit_entry(entry_id):
#     tree, root = db.load_xml()
#     entry_el = root.find(f".//tei:entry[@xml:id='{entry_id}']", NS)
    
#     if entry_el is None:
#         return "Not found", 404

#     if request.method == "POST":
#         update_entry_from_form(entry_el, root, request.form)
#         db.save_xml() # Зберігаємо без аргументів
        
#         flash("Зміни збережено!", "success")
        
#         # Переадресація
#         action = request.form.get('action')
#         if action == 'save_view':
#             return redirect(url_for('main.index', _anchor=entry_id))
#         else:
#             return redirect(url_for('main.edit_entry', entry_id=entry_id))

#     entry_data = parse_entry_data(entry_el, root)
#     back_data = meta_service.parse_back_matter(root)
#     prev_id, next_id = get_sorted_neighbors(root, entry_id)
    
#     return render_template("edit.html", entry=entry_data, back_data=back_data, prev_entry_id=prev_id, next_entry_id=next_id)

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