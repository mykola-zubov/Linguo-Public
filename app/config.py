import os

# Ми знаходимось у app/config.py, тому піднімаємось на два рівні вгору до projekt_root
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_key_12345')
    # Шлях до файлу в корені проекту
    XML_FILE = os.path.join(BASE_DIR, "dictionary_base.xml")
    LANGUAGES = ['uk', 'de', 'en']
    BABEL_DEFAULT_LOCALE = 'uk'
    BABEL_TRANSLATION_DIRECTORIES = os.path.join(BASE_DIR, 'translations')

# Namespaces для XML
NS = {
    'tei': 'http://www.tei-c.org/ns/1.0',
    'xml': 'http://www.w3.org/XML/1998/namespace'
}