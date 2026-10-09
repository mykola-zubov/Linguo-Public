import os
import socket
from dotenv import load_dotenv

# Завантажуємо змінні з файлу .env (якщо він існує, наприклад, на сервері)
load_dotenv()

# Ми знаходимось у app/config.py, тому піднімаємось на два рівні вгору до кореня проєкту
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    # Базові налаштування
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_key_12345')
    
    # Шлях до файлу в корені проєкту
    XML_FILE = os.path.join(BASE_DIR, "dictionary_base.xml")
    
    # Інтернаціоналізація
    LANGUAGES = ['uk', 'de', 'en']
    BABEL_DEFAULT_LOCALE = 'uk'
    BABEL_TRANSLATION_DIRECTORIES = os.path.join(BASE_DIR, 'translations')
    
    # 🔒 РЕЖИМ ПУБЛІЧНОГО ДОСТУПУ (READ_ONLY)
    # Якщо на сервері у файлі .env є READ_ONLY=True, або якщо ми на сервері PythonAnywhere 
    # (автоматичне визначення за ім'ям хоста), то редагування вимикається.
    is_production = 'pythonanywhere' in socket.gethostname()
    READ_ONLY = os.environ.get('READ_ONLY', str(is_production)).lower() in ('true', '1', 't')

# Namespaces для XML
NS = {
    'tei': 'http://www.tei-c.org/ns/1.0',
    'xml': 'http://www.w3.org/XML/1998/namespace'
}