import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

DWDS_BASE_URL = "https://www.dwds.de/wb"
WBNETZ_BASE_URL = "https://woerterbuchnetz.de"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (DH Dictionary Lexicography Project)"
}

BORROWING_KEYWORDS = [
    "entlehnt", "entlehnung", "übernommen", "lehnwort", "fremdwort",
    "aus dem lateinischen", "aus dem altfranzösischen", "aus dem französischen",
    "aus dem italienischen", "aus dem niederländischen", "aus dem englischen",
    "aus dem griechischen", "aus dem slawischen", "aus dem polnischen",
    "aus dem arabischen", "aus dem hebräischen", "aus dem spanischen",
    "lat.", "afrz.", "frz.", "it.", "ital.", "engl.", "gr.", "griech.", "mnd.", "ahd."
]

def map_dwds_pos_and_gen(pos_raw_text):
    pos = ""
    gen = ""
    text = pos_raw_text.lower() if pos_raw_text else ""

    if "substantiv" in text or "nomen" in text:
        pos = "Substantiv"
        if "maskulinum" in text or "m." in text or "maskulin" in text:
            gen = "m"
        elif "femininum" in text or "f." in text or "feminin" in text:
            gen = "f"
        elif "neutrum" in text or "n." in text or "neutral" in text:
            gen = "n"
    elif "verb" in text:
        pos = "Verb"
    elif "adjektiv" in text:
        pos = "Adjektiv"
    elif "adverb" in text:
        pos = "Adverb"
    elif "interjektion" in text:
        pos = "Interjektion"
    elif "präposition" in text:
        pos = "Präposition"
    elif "konjunktion" in text:
        pos = "Konjunktion"
    return pos, gen

def detect_german_origin(soup):
    """
    Аналізує етимологічний блок DWDS.
    Повертає 'borrowing' (запозичення в німецьку) або 'native' (питоме).
    """
    etym_node = soup.select_one("#etymwb-1, .dwdswb-etymologie, .etymologie")
    if not etym_node:
        return "native"

    text = etym_node.get_text(" ", strip=True).lower()
    for kw in BORROWING_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', text):
            return "borrowing"
    return "native"

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

DWDS_BASE_URL = "https://www.dwds.de/wb"
WBNETZ_BASE_URL = "https://woerterbuchnetz.de"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (DH Dictionary Lexicography Project)"
}

BORROWING_KEYWORDS = [
    "entlehnt", "entlehnung", "übernommen", "lehnwort", "fremdwort",
    "aus dem lateinischen", "aus dem altfranzösischen", "aus dem französischen",
    "aus dem italienischen", "aus dem niederländischen", "aus dem englischen",
    "aus dem griechischen", "aus dem slawischen", "aus dem polnischen",
    "aus dem arabischen", "aus dem hebräischen", "aus dem spanischen",
    "lat.", "afrz.", "frz.", "it.", "ital.", "engl.", "gr.", "griech.", "mnd.", "ahd."
]

def map_dwds_pos_and_gen(pos_raw_text):
    pos = ""
    gen = ""
    text = pos_raw_text.lower() if pos_raw_text else ""

    if "substantiv" in text or "nomen" in text:
        pos = "Substantiv"
        if "maskulinum" in text or "m." in text or "maskulin" in text:
            gen = "m"
        elif "femininum" in text or "f." in text or "feminin" in text:
            gen = "f"
        elif "neutrum" in text or "n." in text or "neutral" in text:
            gen = "n"
    elif "verb" in text:
        pos = "Verb"
    elif "adjektiv" in text:
        pos = "Adjektiv"
    elif "adverb" in text:
        pos = "Adverb"
    elif "interjektion" in text:
        pos = "Interjektion"
    elif "präposition" in text:
        pos = "Präposition"
    elif "konjunktion" in text:
        pos = "Konjunktion"
    return pos, gen

def detect_german_origin(soup):
    etym_node = soup.select_one("#etymwb-1, .dwdswb-etymologie, .etymologie")
    if not etym_node:
        return "native"

    text = etym_node.get_text(" ", strip=True).lower()
    for kw in BORROWING_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', text):
            return "borrowing"
    return "native"

def clean_definition_text(text):
    """Очищає текст дефініції від номерів, маркерів списку та прикладів."""
    if not text:
        return ""
    # 1. Прибираємо префікси нумерації на початку: "1. ", "a) ", "● "
    cleaned = re.sub(r'^[\s\d\.\)\(\-a-zA-Z●•–—]+\s*', '', text)
    # 2. Прибираємо блоки прикладів: "Beispiel: ...", "Beispiele: ..."
    cleaned = re.split(r'\bBeispiel(e)?\s*:\s*', cleaned, flags=re.IGNORECASE)[0]
    # 3. Видаляємо зайві подвійні пробіли
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def fetch_dwds_entry(lemma: str):
    clean_lemma = lemma.strip()
    if not clean_lemma:
        return {"status": "error", "message": "Порожній запит"}

    url = f"{DWDS_BASE_URL}/{clean_lemma}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=8)
        if response.status_code == 404:
            return {
                "status": "not_found",
                "fallback_url": f"{WBNETZ_BASE_URL}/#/?lemid={clean_lemma}",
                "message": f"Слово '{clean_lemma}' не знайдено в DWDS. Відкриваємо Wörterbuchnetz."
            }
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"DWDS fetch error for {clean_lemma}: {e}")
        return {"status": "error", "message": f"Помилка з'єднання: {str(e)}"}

    soup = BeautifulSoup(response.content, 'html.parser')

    # 1. ПЕРЕВІРКА НА ОМОНІМИ
    homonym_tabs = soup.select(".dwdswb-homonym-selector a, ul.nav-tabs li a[href*='/wb/']")
    homonym_indicators = [t for t in homonym_tabs if re.search(r'^\s*[\d¹²³⁴⁵]', t.get_text(strip=True))]
    if len(homonym_indicators) > 1:
        return {
            "status": "homonyms",
            "url": url,
            "message": f"Слово '{clean_lemma}' має кілька омонімів у DWDS. Відкриваємо для вибору."
        }

    # 2. Базові дані (Орфографія, PoS, Рід)
    head_node = soup.select_one(".dwdswb-ft-lemma, .dwdswb-lemma, h1")
    orth = head_node.get_text(strip=True) if head_node else clean_lemma

    pos_node = soup.select_one(".dwdswb-ft-blocktext, .dwdswb-pos")
    pos_raw = pos_node.get_text(" ", strip=True) if pos_node else ""
    pos, gen = map_dwds_pos_and_gen(pos_raw)

    # 3. Визначення походження
    lang_sourse = detect_german_origin(soup)

    # 4. ТОЧНИЙ ПАРСИНГ ПУНКТІВ Bedeutungsübersicht
    senses = []
    today_str = datetime.now().strftime("%d.%m.%Y")

    # Шукаємо заголовок або контейнер Bedeutungsübersicht
    overview_header = soup.find(lambda tag: tag.name in ['h2', 'h3', 'div'] and 'Bedeutungsübersicht' in tag.get_text())
    
    if overview_header:
        # Контейнером зазвичай є наступний ol/ul/div
        container = overview_header.find_next_sibling(["ol", "ul", "div", "table"])
        if container:
            # Видаляємо всі внутрішні під-елементи з прикладами/цитатами до вилучення тексту
            for ex in container.select(".dwdswb-beleg, .dwdswb-belege, .dwdswb-mehrwortausdruck, .dwdswb-beispiel"):
                ex.decompose()

            # Кожен головний li розглядаємо як окреме значення
            # Використовуємо recursive=False або прямі li першого/другого рівня
            list_items = container.find_all("li")
            if not list_items:
                list_items = container.select(".dwdswb-uebersicht-item, tr")

            for li in list_items:
                # Отримуємо тільки безпосередній текст li (без вкладених дочірніх списків ul/ol, щоб не дублювати)
                # Клонуємо для безпечного очищення вкладених списків
                sub_lists = li.find_all(["ul", "ol"])
                for sl in sub_lists:
                    sl.decompose()

                raw_text = li.get_text(" ", strip=True)
                clean_def = clean_definition_text(raw_text)

                if clean_def and len(clean_def) > 1:
                    senses.append({
                        "definition": clean_def,
                        "def_source_abbr": "DWDS",
                        "def_source_url": url,
                        "def_source_date": today_str
                    })

    # Фолбек: якщо Bedeutungsübersicht не було або він порожній, беремо з головного блоку Bedeutungen
    if not senses:
        for d_node in soup.select(".dwdswb-definition-content, .dwdswb-lesart"):
            for ex in d_node.select(".dwdswb-beleg, .dwdswb-belege, .dwdswb-mehrwortausdruck, .dwdswb-beispiel"):
                ex.decompose()
            clean_def = clean_definition_text(d_node.get_text(" ", strip=True))
            if clean_def:
                senses.append({
                    "definition": clean_def,
                    "def_source_abbr": "DWDS",
                    "def_source_url": url,
                    "def_source_date": today_str
                })

    return {
        "status": "success",
        "url": url,
        "orth": orth,
        "pos": pos,
        "gen": gen,
        "lang_sourse": lang_sourse,
        "senses": senses
    }