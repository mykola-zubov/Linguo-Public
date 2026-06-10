# Словник німецьких запозичень в українській мові (Демо-версія)
## German Loanwords in the Ukrainian Language (Demo Version)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20630853.svg)](https://zenodo.org/record/20630853)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)

---

### 🇺🇦 Українською

Цей репозиторій містить вихідний код та демонстраційну базу даних веб-застосунку для інтерактивного словника слів німецького походження в українській мові. Проєкт укладено відповідно до сучасних лінгвістичних та цифрових стандартів гуманітарних наук (Digital Humanities).

*   **Демо-версія застосунку**: [https://zubov.pythonanywhere.com](https://zubov.pythonanywhere.com)

#### Особливості проєкту:
*   **Стандартизація даних**: База даних словника укладена у форматі **TEI XML** з дотриманням рекомендацій консорціуму **TEI Lex-0**.
*   **Безпека**: З міркувань цифрової безпеки у публічній версії коду вимкнено адміністративні функції додавання, редагування та видалення записів, а база даних представлена у вигляді демонстраційного зразка (понад 300 завершених словникових статей).

---

### 🇬🇧 English

This repository contains the source code and a demonstration database for the interactive web application of the Dictionary of German Loanwords in the Ukrainian Language.

*   **Live Web Demo**: [https://zubov.pythonanywhere.com](https://zubov.pythonanywhere.com)

#### Key Features:
*   **Data Standardization**: The dictionary database is structured in **TEI XML** format, strictly complying with the international **TEI Lex-0** guidelines.
*   **Security**: For public deployment, admin features (add, edit, delete) have been disabled, and the database contains a curated subset of ca. 300 fully completed lexicographical entries.

---

## 📁 Структура проєкту / Project Structure

```text
Linguo-Public/
│
├── app/                      # Ядро веб-застосунку (Flask Application)
│   ├── services/             # Логіка обробки XML бази даних та метаданих
│   │   ├── __init__.py
│   │   ├── entries.py
│   │   ├── metadata.py
│   │   └── xml_db.py         # Модуль парсингу та роботи з TEI XML
│   │
│   ├── static/               # Статичні файли (стилі CSS, JS-скрипти, логотип)
│   │   ├── logo.svg
│   │   ├── script.js
│   │   └── styles.css
│   │
│   ├── templates/            # HTML-шаблони інтерфейсу (Jinja2 templates)
│   │   ├── _word_list.html
│   │   ├── entry_partial.html
│   │   ├── entry.html
│   │   └── index.html
│   │
│   ├── __init__.py           # Ініціалізація додатку та налаштувань мов
│   ├── config.py             # Конфігурація застосунку
│   ├── routes.py             # Маршрутизація сторінок (URL-адреси)
│   ├── tei_helpers.py        # Допоміжні функції для роботи з TEI тегами
│   └── utils.py
│
├── translations/             # Файли локалізації інтерфейсу (UA/DE/EN)
├── .gitignore                # Файл виключення системного сміття з репозиторію
├── dictionary_base.xml       # База даних словника (TEI XML — 100 статей)
├── filter_xml.py             # Скрипт для фільтрації завершених статей
├── requirements.txt          # Список залежностей Python (бібліотеки)
└── run.py                    # Головний файл для запуску локального сервера

**Локальний запуск / Local Setup**
1. Клонування репозиторію (Clone)
git clone https://github.com/mykola-zubov/Linguo-Public.git
cd Linguo-Public

2. Налаштування віртуального оточення (Virtual Environment)
Рекомендується використовувати Python версії 3.9 або вище.
# Створення оточення
python3 -m venv my_env

# Активація (для macOS/Linux)
source my_env/bin/activate

# Активація (для Windows)
my_env\Scripts\activate


3. Встановлення бібліотек (Dependencies)
pip install -r requirements.txt

4. Запуск локального сервера (Run)
python run.py

Ліцензування / Licensing
Вихідний програмний код (Python, HTML, CSS, JS) розповсюджується під ліцензією MIT License.
Текстовий контент словника та база даних (dictionary_base.xml) розповсюджуються під міжнародною ліцензією Creative Commons Attribution 4.0 International (CC BY 4.0).

Контакти / Contact: nikolaji.zubov@gmail.com
