import xml.etree.ElementTree as ET

# 1. Реєструємо простір імен TEI, щоб зберегти правильний вигляд файлу при записі
ET.register_namespace('', 'http://www.tei-c.org/ns/1.0')

# Назви вхідного та вихідного файлів
input_file = 'dictionary_base_copy.xml'
output_file = 'dictionary_complete_only.xml'

# Простір імен TEI для пошуку елементів
ns = {'tei': 'http://www.tei-c.org/ns/1.0'}

try:
    print("Зчитування та аналіз XML-файлу...")
    tree = ET.parse(input_file)
    root = tree.getroot()

    # 2. Знаходимо контейнер, де лежать наші статті <entry>
    # За стандартом TEI це: TEI -> text -> body -> div[@type="dictionary"]
    dictionary_div = root.find('.//tei:div[@type="dictionary"]', ns)
    
    if dictionary_div is None:
        # Резервний пошук в тілі документа, якщо структура спрощена
        dictionary_div = root.find('.//tei:body', ns)

    if dictionary_div is not None:
        # Тег елемента <entry> з урахуванням простору імен
        entry_tag = '{http://www.tei-c.org/ns/1.0}entry'
        
        # Знаходимо всі статті
        entries = dictionary_div.findall(entry_tag)
        total_entries = len(entries)
        removed_count = 0
        
        print(f"Знайдено всього словникових статей: {total_entries}")
        
        # 3. Фільтруємо статті
        for entry in entries:
            status = entry.get('status')
            
            # Якщо статус не дорівнює "complete", видаляємо статтю з батьківського тегу <div>
            if status != 'complete':
                dictionary_div.remove(entry)
                removed_count += 1
        
        # 4. Зберігаємо оновлений чистий XML-дерево у новий файл
        # Зберігаємо кодування UTF-8 та XML-декларацію вгорі
        tree.write(output_file, encoding='utf-8', xml_declaration=True)
        
        print("\n--- ОБРОБКУ ЗАВЕРШЕНО ---")
        print(f"Вилучено неповних статей: {removed_count}")
        print(f"Збережено завершених статей (status='complete'): {total_entries - removed_count}")
        print(f"Результат записано у файл: {output_file}")
        
    else:
        print("Помилка: Не вдалося знайти контейнер для словникових статей (div type='dictionary').")

except FileNotFoundError:
    print(f"Помилка: Файл '{input_file}' не знайдено у цій папці.")
except Exception as e:
    print(f"Сталася помилка під час обробки: {e}")