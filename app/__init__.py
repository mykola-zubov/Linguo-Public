import logging
import locale
import os
from flask import Flask, request, session
from flask_babel import Babel
from app.config import Config
# Імпорти сервісів
from app.services.xml_db import db
from app.services.metadata import meta_service

babel = Babel()

def create_app():
    # 1. Створення екземпляру
    app = Flask(__name__)
    app.config.from_object(Config)

    # 2. Налаштування логування
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 3. Налаштування локалі
    try:
        locale.setlocale(locale.LC_COLLATE, 'uk_UA.UTF-8')
    except locale.Error:
        logging.warning("Locale 'uk_UA.UTF-8' not found.")

    # 4. Налаштування Babel (мови)
    def get_locale():
        lang = request.args.get('ui_lang', session.get('ui_lang', 'uk'))
        if lang not in app.config['LANGUAGES']:
            lang = 'uk'
        session['ui_lang'] = lang
        return lang

    babel.init_app(app, locale_selector=get_locale)

    # 5. Context Processors (змінні для шаблонів)
    @app.context_processor
    def inject_locale():
        return dict(current_ui_lang=get_locale())

    @app.context_processor
    def inject_back_data():
        try:
            # Тут ми звертаємось до бази
            _, root = db.load_xml()
            data = meta_service.parse_back_matter(root)
            return dict(back_data=data)
        except Exception as e:
            logging.error(f"Error loading metadata: {e}")
            # Повертаємо пустий словник, щоб сайт не впав
            return dict(back_data={})

    # 6. Реєстрація маршрутів
    # Імпорт робимо тут, щоб уникнути кільцевої залежності!
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    return app