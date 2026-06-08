document.addEventListener('DOMContentLoaded', function () {
  console.log("Script loaded and DOM ready.");

  // ============================================================
  // 1. HELPER FUNCTIONS
  // ============================================================

  function escapeHtml(unsafe) {
    if (unsafe === null || typeof unsafe === 'undefined') return '';
    return String(unsafe)
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
  }

  function getTodayDate() {
      const today = new Date();
      const day = String(today.getDate()).padStart(2, '0');
      const month = String(today.getMonth() + 1).padStart(2, '0');
      const year = today.getFullYear();
      return `${day}.${month}.${year}`;
  }

  function disableBiblLinks() {
      const links = document.querySelectorAll('a[href^="#bibl"]');
      links.forEach(link => {
          link.removeAttribute('target');
          const newLink = link.cloneNode(true);
          if (link.parentNode) link.parentNode.replaceChild(newLink, link);
          newLink.addEventListener('click', function(event) {
              event.preventDefault();
              event.stopPropagation();
              return false;
          });
      });
  }

  // ============================================================
  // 2. EDITORS & CHOICES INITIALIZATION
  // ============================================================

  const editors = {};
  
  function initializeMarkdownEditor(textareaId) {
    const el = document.getElementById(textareaId);
    if (el && !editors[textareaId]) {
      try {
        if (el.tagName.toLowerCase() !== 'textarea') return;

        const easyMDE = new EasyMDE({
          element: el,
          spellChecker: false,
          minHeight: '80px',
          status: false, 
          forceSync: true, // Важливо: автоматично оновлює textarea
          toolbar: ['bold', 'italic', '|', 'link', 'quote', '|', 'preview', 'guide'],
        });
        editors[textareaId] = easyMDE;
      } catch (e) {
        console.error("Error initializing EasyMDE for:", textareaId, e);
      }
    }
  }

  // Глобальне сховище для екземплярів Choices
  const choicesInstances = {};

  function initializeChoices(elementOrSelector, selectedValues = []) {
      let element;
      if (typeof elementOrSelector === 'string') {
          element = document.querySelector(elementOrSelector);
          if (!element && !elementOrSelector.startsWith('#') && !elementOrSelector.startsWith('.')) {
             element = document.getElementById(elementOrSelector);
          }
      } else {
          element = elementOrSelector;
      }

      if (element) {
          if (element.classList.contains('choices__input') || element.closest('.choices')) {
              return null;
          }
          
          const choices = new Choices(element, {
              removeItemButton: true,
              allowHTML: false,
              itemSelectText: '',
              shouldSort: false,
              searchEnabled: true,
              placeholder: true,
              placeholderValue: element.getAttribute('placeholder') || ''
          });

          if (element.id) {
              choicesInstances[element.id] = choices;
          }

          if (selectedValues && selectedValues.length > 0) {
              const valArray = Array.isArray(selectedValues) ? selectedValues.filter(v => v) : [selectedValues];
              if (valArray.length > 0) {
                  setTimeout(() => choices.setChoiceByValue(valArray), 0);
              }
          }
          return choices;
      }
      return null;
  }

  function getLangOptions(selectedValue = '') {
      let options = '<option value="">(Оберіть мову)</option>';
      if (window.back_data && window.back_data.languages) {
          window.back_data.languages.forEach(lang => {
              const code = lang.code || lang.term; 
              const isSelected = code === selectedValue ? 'selected' : '';
              options += `<option value="${code}" ${isSelected}>${lang.term}</option>`;
          });
      }
      return options;
  }

  function getDialectOptionsHTML() {
      let options = ''; 
      if (window.back_data && window.back_data.regions) {
          options += '<optgroup label="Регіони">';
          window.back_data.regions.forEach(reg => {
              const label = reg.term || reg.abbr || reg.value;
              options += `<option value="${label}">${label}</option>`;
          });
          options += '</optgroup>';
      }
      return options;
  }

  // ============================================================
  // 3. CONDITIONAL UI (GENDER DISPLAY)
  // ============================================================

  function setupConditionalUI() {
      ['pos', 'german_pos'].forEach(id => {
          const originalSelect = document.getElementById(id);
          if (!originalSelect) return;

          const toggle = (value) => {
              const fs = originalSelect.closest('fieldset');
              if (!fs) return;
              
              const genderOptions = fs.querySelector('.gender-options');
              const casusOptions = fs.querySelector('.casus-options');
              const verbOptions = document.querySelector(`.verb-options[data-pos-select-id="${id}"]`);
              
              if (genderOptions) genderOptions.style.display = (value === 'Substantiv') ? '' : 'none';
              if (casusOptions) casusOptions.style.display = (value === 'Substantiv') ? '' : 'none';
              if (verbOptions) verbOptions.style.display = (value === 'Verb') ? '' : 'none';
          };

          if (choicesInstances[id]) {
              originalSelect.addEventListener('change', function(event) {
                  const val = event.detail ? event.detail.value : this.value;
                  toggle(val);
              });
              // Ініціалізація
              const currentVal = choicesInstances[id].getValue(true);
              // Перевірка, чи це масив (інколи Choices повертає масив)
              const valToToggle = Array.isArray(currentVal) ? currentVal[0] : currentVal;
              toggle(valToToggle);
          } else {
              originalSelect.addEventListener('change', function() {
                   toggle(this.value);
              });
              toggle(originalSelect.value);
          }
      });
      
      const entryTypeRadios = document.querySelectorAll('input[name="entry_type"]');
      if (entryTypeRadios.length) {
          const toggle = () => {
              const checked = document.querySelector('input[name="entry_type"]:checked');
              const type = checked ? checked.value : 'normal';
              const redirectFields = document.getElementById('redirect-fields');
              const toggleable = document.querySelector('.toggleable-section');
              if(redirectFields) redirectFields.style.display = type === 'redirect' ? 'block' : 'none';
              if(toggleable) toggleable.style.display = type === 'normal' ? 'block' : 'none';
          };
          entryTypeRadios.forEach(r => r.addEventListener('change', toggle));
          toggle();
      }

      const borrowingPathSel = document.getElementById('borrowing_path');
      if (borrowingPathSel) {
          const toggle = () => { 
              const mediatorFields = document.getElementById('mediator-fields');
              if(mediatorFields) mediatorFields.style.display = borrowingPathSel.value === 'mediated' ? 'block' : 'none'; 
          };
          borrowingPathSel.addEventListener('change', toggle);
          toggle();
      }
      
      const langSourceSel = document.getElementById('lang_sourse');
      if (langSourceSel) {
          const toggle = () => { 
              const condFields = document.getElementById('conditional-borrowing-fields');
              if(condFields) condFields.style.display = langSourceSel.value === 'borrowing' ? 'block' : 'none'; 
          };
          langSourceSel.addEventListener('change', toggle);
          toggle();
      }
  }

  // ============================================================
  // 4. DYNAMIC ITEM GENERATORS
  // ============================================================

  let senseCounter = 0, germanSenseCounter = 0, equivalentCounter = 0, biblCounter = 0, variantCounter = 0;
  let mediatorCounter = 1, alterDonorCounter = 0, alterGermanDonorCounter = 0;

  function createDynamicItem(containerId, templateHTML, counter, initCallback) {
    const container = document.getElementById(containerId);
    if (!container) {
        console.error(`Container #${containerId} not found!`);
        return counter;
    }
    const html = templateHTML
      .replace(/___INDEX___/g, `___${counter}___`)
      .replace(/__INDEX__/g, String(counter))
      .replace(/INDEX/g, String(counter));

    const wrapper = document.createElement('div');
    wrapper.innerHTML = html;
    const newItem = wrapper.firstElementChild;

    if (newItem) {
      container.appendChild(newItem);
      if (initCallback) initCallback(counter, newItem); 
    }
    return counter + 1;
  }

  // 5. STATIC FIELDS INIT
  document.querySelectorAll('textarea.markdown-editor').forEach(el => {
      initializeMarkdownEditor(el.id);
  });

  [
      '#lemma_region_style', '#lemma_geo', '#lemma_style',
      '#german_head_region_style', '#german_head_geo', '#german_head_style',
      '#pos', '#gram_gen', '#transitivity', '#aspect',
      '#german_pos', '#german_gen'
  ].forEach(id => initializeChoices(id));


  // ============================================================
  // 6. UKRAINIAN SENSES
  // ============================================================

  function addSenseTranslationItem(senseIndex, item = null, transIndexOverride = null) {
      const containerId = `senses-translations-container-${senseIndex}`;
      const container = document.getElementById(containerId);
      if (!container) return;

      let idx = transIndexOverride;
      if (idx === null) {
          let maxIndex = -1;
          const inputs = container.querySelectorAll(`[name^="senses___${senseIndex}___translations___"]`);
          inputs.forEach(input => {
              const match = input.name.match(/translations___(\d+)___/);
              if (match) {
                  const i = parseInt(match[1], 10);
                  if (i > maxIndex) maxIndex = i;
              }
          });
          idx = maxIndex + 1;
      }

      const langValue = item ? item.lang : 'de';
      const wordValue = item ? (item.quote || item.word) : '';
      const langOptions = getLangOptions(langValue);

      const template = `
        <div class="dynamic-list-item sub-item-block translation-block">
            <button type="button" class="delete-item-btn" title="Remove translation">×</button>
            <div class="form-row compact-row">
                <select name="senses___${senseIndex}___translations___${idx}___lang" style="width: 30%;">${langOptions}</select>
                <input type="text" name="senses___${senseIndex}___translations___${idx}___word" placeholder="Translation" value="" style="width: 70%;">
            </div>
        </div>`;
        
       const wrapper = document.createElement('div');
       wrapper.innerHTML = template;
       const newItem = wrapper.firstElementChild;
       container.appendChild(newItem);
       
       if (wordValue) {
           newItem.querySelector(`input[name$="word"]`).value = wordValue;
       }
  }

  function addSenseItem(sense = null, index = null) {
    const i = index !== null ? index : senseCounter;
    const definition = sense ? sense.definition : '';
    const examples = sense && sense.examples ? sense.examples : [];
    const translations = sense && sense.translations ? sense.translations : [];

    let stylesHTML = '';
    if (window.back_data && window.back_data.styles) {
        window.back_data.styles.forEach((main_style, loopIndex) => {
            if (main_style.id !== 'DOM-STYLE-TERR') { 
                let options = main_style.children.map(item => `<option value="${item.term}">${item.term}</option>`).join('');
                stylesHTML += `
                    <div class="form-group">
                        <label for="senses_${i}_style_${loopIndex}">${main_style.term}</label>
                        <select id="senses_${i}_style_${loopIndex}" name="senses___${i}___style" multiple>${options}</select>
                    </div>`;
            }
        });
    }

    const template = `
        <div class="dynamic-list-item item-block sense-block">
            <button type="button" class="delete-item-btn" title="Remove meaning">×</button>
            <h4>Meaning #${i + 1}</h4>
            <div class="form-row">
                <div class="form-group form-group--compact">
                    <label>Time of use</label>
                    <input id="senses_${i}_time" type="text" name="senses___${i}___time" value="">
                </div>
                <div class="form-group form-group--compact">
                    <label>Region</label>
                    <select id="senses_${i}_region" name="senses___${i}___region">
                        <option value="">(not specified)</option>
                        ${(window.back_data.styles.find(s => s.id === 'DOM-STYLE-TERR')?.children || []).map(item => `<option value="${item.term}">${item.term}</option>`).join('')}
                    </select>
                </div>
                <div class="form-group form-group--compact">
                    <label>Dialect/Area</label>
                    <select id="senses_${i}_geo" name="senses___${i}___geo" multiple>
                        ${getDialectOptionsHTML()}
                    </select>
                </div>
                <div class="form-group form-group--main">
                    <label>Domain(s)</label>
                    <select id="senses_${i}_domain" name="senses___${i}___domain" multiple>
                        ${(window.domainData || []).map(d => `<optgroup label="${d.term}">${d.children.map(s => `<option value="${s.term}">${s.term}</option>`).join('')}</optgroup>`).join('')}
                    </select>
                </div>
            </div>
            <fieldset class="form-section-inner">
                <legend>Stylistic characteristics</legend>
                <div class="form-row">${stylesHTML}</div>
            </fieldset>
            <textarea id="senses_${i}_definition" class="markdown-editor" name="senses___${i}___definition" placeholder="Definition"></textarea>
            
            <div class="form-row compact-row" style="margin-top: 5px; margin-bottom: 15px; align-items: flex-end;">
                <div class="form-group" style="width: 25%;">
                    <label style="font-size: 0.8em;">Source Name</label>
                    <select name="senses___${i}___def_source_abbr" style="height: 36px; width: 100%;">
                        <option value="">(Джерело)</option>
                        ${window.biblData ? window.biblData.map(b => `<option value="${b.abbr}" title="${b.title}">${b.abbr}</option>`).join('') : ''}
                    </select>
                </div>
                <div class="form-group" style="width: 50%;">
                    <label style="font-size: 0.8em;">URL</label>
                    <input type="text" name="senses___${i}___def_source_url" placeholder="https://..." value="">
                </div>
                <div class="form-group" style="width: 25%; display: flex; gap: 5px;">
                    <div style="flex-grow: 1;">
                        <label style="font-size: 0.8em;">Access Date</label>
                        <input type="text" name="senses___${i}___def_source_date" class="date-input" placeholder="DD.MM.YYYY" value="">
                    </div>
                    <button type="button" class="button set-today-btn" title="Set Today" style="height: 38px; margin-top: auto;">📅</button>
                </div>
            </div>

            <div class="sub-item-group" id="senses-translations-container-${i}">
                <label>Translations:</label>
            </div>
            <button type="button" class="add-item-btn add-sense-translation-btn" data-sense-index="${i}">➕ Add Translation</button>

            <div class="sub-item-group" id="examples-container-${i}"><label>Examples:</label></div>
            <button type="button" class="add-item-btn add-example-btn" data-sense-index="${i}">➕ Add Example</button>
        </div>`;

    senseCounter = createDynamicItem('senses-container', template, i, (newIndex, newItem) => {
        if (sense) {
            newItem.querySelector(`input[name="senses___${newIndex}___time"]`).value = sense.time || '';
            const sourceSelect = newItem.querySelector(`select[name="senses___${newIndex}___def_source_abbr"]`);
            if(sourceSelect && sense.def_source_abbr) sourceSelect.value = sense.def_source_abbr;
            newItem.querySelector(`input[name="senses___${newIndex}___def_source_url"]`).value = sense.def_source_url || '';
            newItem.querySelector(`input[name="senses___${newIndex}___def_source_date"]`).value = sense.def_source_date || '';
            
            const regionSelect = newItem.querySelector(`select[name="senses___${newIndex}___region"]`);
            if (regionSelect) regionSelect.value = sense.region || '';
            
            const defTextarea = newItem.querySelector(`#senses_${newIndex}_definition`);
            if (defTextarea) defTextarea.value = definition; 
        }

        initializeMarkdownEditor(`senses_${newIndex}_definition`);
        initializeChoices(`#senses_${newIndex}_domain`, sense ? sense.domain : []);
        initializeChoices(`#senses_${newIndex}_geo`, sense ? sense.geo : []); 
        
        window.back_data.styles.forEach((main_style, loopIndex) => {
            if (main_style.id !== 'DOM-STYLE-TERR') {
                const possibleTerms = new Set(main_style.children.map(c => c.term));
                let selectedValues = [];
                if (sense && sense.style) {
                     selectedValues = sense.style.map(s => (typeof s === 'object' && s !== null) ? s.full : s);
                }
                selectedValues = selectedValues.filter(s => possibleTerms.has(s));
                initializeChoices(`#senses_${newIndex}_style_${loopIndex}`, selectedValues);
            }
        });

        if (examples.length > 0) {
            examples.forEach(ex => addExampleItem(newIndex, ex));
        } else if (!sense) {
             addExampleItem(newIndex);
        }
        
        if (translations.length > 0) {
            translations.forEach((tr, trIdx) => addSenseTranslationItem(newIndex, tr, trIdx));
        }
    });
  }
  
  function addExampleItem(senseIndex, example = null) {
      const container = document.getElementById(`examples-container-${senseIndex}`);
      let maxIndex = -1;
      const inputs = container.querySelectorAll(`[name^="senses___${senseIndex}___examples___"]`);
      inputs.forEach(input => {
          const match = input.name.match(/examples___(\d+)___/);
          if (match) {
              const idx = parseInt(match[1], 10);
              if (idx > maxIndex) maxIndex = idx;
          }
      });
      const exIndex = maxIndex + 1;

      const template = `<div class="dynamic-list-item sub-item-block example-block"> <button type="button" class="delete-item-btn" title="Remove example">×</button> <textarea id="senses_${senseIndex}_examples_${exIndex}_quote" class="markdown-editor" name="senses___${senseIndex}___examples___${exIndex}___quote" placeholder="Example"></textarea> <input type="text" name="senses___${senseIndex}___examples___${exIndex}___source_abbr" placeholder="Source" value=""> </div>`;
      
      createDynamicItem(`examples-container-${senseIndex}`, template, exIndex, (idx, newItem) => {
          if (example) {
              newItem.querySelector('textarea').value = example.quote || '';
              newItem.querySelector('input').value = example.source_abbr || '';
          }
          initializeMarkdownEditor(`senses_${senseIndex}_examples_${exIndex}_quote`);
      });
  }
  
  // --- 6. GERMAN SENSES ---

  function addGermanSenseTranslationItem(senseIndex, item = null, transIndexOverride = null) {
      const containerId = `german-translations-container-${senseIndex}`;
      const container = document.getElementById(containerId);
      if (!container) return;

      let idx = transIndexOverride;
      if (idx === null) {
          let maxIndex = -1;
          const inputs = container.querySelectorAll(`[name^="german_senses___${senseIndex}___translations___"]`);
          inputs.forEach(input => {
              const match = input.name.match(/translations___(\d+)___/);
              if (match) {
                  const i = parseInt(match[1], 10);
                  if (i > maxIndex) maxIndex = i;
              }
          });
          idx = maxIndex + 1;
      }

      const langValue = item ? item.lang : 'uk';
      const wordValue = item ? (item.quote || item.word) : '';
      const langOptions = getLangOptions(langValue);
      
      const uniqueId = `german_senses_${senseIndex}_translations_${idx}_word`;

      const template = `
        <div class="dynamic-list-item sub-item-block translation-block">
            <button type="button" class="delete-item-btn" title="Remove translation">×</button>
            <div class="form-row compact-row">
                <select name="german_senses___${senseIndex}___translations___${idx}___lang" style="width: 30%;">${langOptions}</select>
                <textarea id="${uniqueId}" class="markdown-editor" name="german_senses___${senseIndex}___translations___${idx}___word" placeholder="Translation" style="width: 70%;">${escapeHtml(wordValue)}</textarea>
            </div>
        </div>`;
        
       const wrapper = document.createElement('div');
       wrapper.innerHTML = template;
       const newItem = wrapper.firstElementChild;
       container.appendChild(newItem);
       
       initializeMarkdownEditor(uniqueId);
  }

  function addGermanSenseItem(sense = null, index = null) {
      const i = index !== null ? index : germanSenseCounter;
      const definition = sense ? sense.definition : '';
      const examples = sense && sense.examples ? sense.examples : [];
      const translations = sense && sense.translations ? sense.translations : [];
      
      let stylesHTML = '';
      if (window.back_data && window.back_data.styles) {
          window.back_data.styles.forEach((main_style, loopIndex) => {
              if (main_style.id !== 'DOM-STYLE-TERR') {
                  let options = main_style.children.map(item => `<option value="${item.term}">${item.term}</option>`).join('');
                  stylesHTML += `
                      <div class="form-group">
                          <label for="german_senses_${i}_style_${loopIndex}">${main_style.term}</label>
                          <select id="german_senses_${i}_style_${loopIndex}" name="german_senses___${i}___style" multiple>${options}</select>
                      </div>`;
              }
          });
      }

      const template = `
          <div class="dynamic-list-item item-block sense-block">
              <button type="button" class="delete-item-btn" title="Remove meaning">×</button>
              <h4>German Meaning #${i + 1}</h4>
              <div class="form-row">
                   <div class="form-group form-group--compact">
                      <label>Time</label>
                      <input id="german_senses_${i}_time" type="text" name="german_senses___${i}___time" value="">
                  </div>
                  <div class="form-group form-group--compact">
                    <label>Region</label>
                    <select id="german_senses_${i}_region" name="german_senses___${i}___region">
                        <option value="">(not specified)</option>
                        ${(window.back_data.styles.find(s => s.id === 'DOM-STYLE-TERR')?.children || []).map(item => `<option value="${item.term}">${item.term}</option>`).join('')}
                    </select>
                  </div>
                  <div class="form-group form-group--compact">
                      <label>Dialect/Area</label>
                      <select id="german_senses_${i}_geo" name="german_senses___${i}___geo" multiple>
                          ${getDialectOptionsHTML()}
                      </select>
                  </div>
                  <div class="form-group form-group--main">
                      <label>Domain(s) (Ger.)</label>
                      <select id="german_senses_${i}_domain" name="german_senses___${i}___domain" multiple>
                          ${(window.domainData || []).map(main_domain => `
                              <optgroup label="${main_domain.term}">
                                  ${main_domain.children.map(sub_domain => `<option value="${sub_domain.term}">${sub_domain.term}</option>`).join('')}
                              </optgroup>
                          `).join('')}
                      </select>
                  </div>
              </div>
              <fieldset class="form-section-inner">
                  <legend>Stylistic characteristics</legend>
                  <div class="form-row">${stylesHTML}</div>
              </fieldset>
              <textarea id="german_senses_${i}_definition" class="markdown-editor" name="german_senses___${i}___definition" placeholder="Definition (Ger.)"></textarea>
              
              <div class="form-row compact-row" style="margin-top: 5px; margin-bottom: 15px; align-items: flex-end;">
                  <div class="form-group" style="width: 25%;">
                      <label style="font-size: 0.8em;">Source Name</label>
                      <select name="german_senses___${i}___def_source_abbr" style="height: 36px; width: 100%;">
                        <option value="">(Джерело)</option>
                        ${window.biblData ? window.biblData.map(b => `<option value="${b.abbr}" title="${b.title}">${b.abbr}</option>`).join('') : ''}
                      </select>
                  </div>
                  <div class="form-group" style="width: 50%;">
                      <label style="font-size: 0.8em;">URL</label>
                      <input type="text" name="german_senses___${i}___def_source_url" placeholder="https://..." value="">
                  </div>
                  <div class="form-group" style="width: 25%; display: flex; gap: 5px;">
                    <div style="flex-grow: 1;">
                        <label style="font-size: 0.8em;">Access Date</label>
                        <input type="text" name="german_senses___${i}___def_source_date" class="date-input" placeholder="DD.MM.YYYY" value="">
                    </div>
                    <button type="button" class="button set-today-btn" title="Set Today" style="height: 38px; margin-top: auto;">📅</button>
                  </div>
              </div>

              <div class="sub-item-group" id="german-translations-container-${i}">
                  <label>Translations (Ger.):</label>
              </div>
              <button type="button" class="add-item-btn add-german-sense-translation-btn" data-sense-index="${i}">➕ Add Translation</button>

              <div class="sub-item-group" id="german-examples-container-${i}"><label>Examples (Ger.):</label></div>
              <button type="button" class="add-item-btn add-german-example-btn" data-sense-index="${i}">➕ Add Example (Ger.)</button>
          </div>`;
      
      germanSenseCounter = createDynamicItem('german-senses-container', template, i, (newIndex, newItem) => {
        if (sense) {
            newItem.querySelector(`input[name="german_senses___${newIndex}___time"]`).value = sense.time || '';
            const sourceSelect = newItem.querySelector(`select[name="german_senses___${newIndex}___def_source_abbr"]`);
            if(sourceSelect && sense.def_source_abbr) sourceSelect.value = sense.def_source_abbr;
            newItem.querySelector(`input[name="german_senses___${newIndex}___def_source_url"]`).value = sense.def_source_url || '';
            newItem.querySelector(`input[name="german_senses___${newIndex}___def_source_date"]`).value = sense.def_source_date || '';
            const regionSelect = newItem.querySelector(`select[name="german_senses___${newIndex}___region"]`);
            if (regionSelect) regionSelect.value = sense.region || '';
            const defTextarea = newItem.querySelector(`#german_senses_${newIndex}_definition`);
            if (defTextarea) defTextarea.value = definition;
        }

        initializeMarkdownEditor(`german_senses_${newIndex}_definition`);
        initializeChoices(`#german_senses_${newIndex}_domain`, sense ? sense.domain : []);
        initializeChoices(`#german_senses_${newIndex}_geo`, sense ? sense.geo : []);
        
        window.back_data.styles.forEach((main_style, loopIndex) => {
            if (main_style.id !== 'DOM-STYLE-TERR') {
                const possibleTerms = new Set(main_style.children.map(c => c.term));
                let selectedValues = [];
                if (sense && sense.style) {
                     // Якщо це об'єкт - беремо full, якщо рядок - як є
                     selectedValues = sense.style.map(s => (typeof s === 'object' && s !== null) ? s.full : s);
                }
                selectedValues = selectedValues.filter(s => possibleTerms.has(s));
                initializeChoices(`#german_senses_${newIndex}_style_${loopIndex}`, selectedValues);
            }
        });

        if (examples.length > 0) examples.forEach(ex => addGermanExampleItem(newIndex, ex));
        else if (!sense) addGermanExampleItem(newIndex); 

        if (translations.length > 0) {
            translations.forEach((tr, trIdx) => addGermanSenseTranslationItem(newIndex, tr, trIdx));
        }
      });
  }
  
  function addGermanExampleItem(senseIndex, example = null) {
      const container = document.getElementById(`german-examples-container-${senseIndex}`);
      let maxIndex = -1;
      const inputs = container.querySelectorAll(`[name^="german_senses___${senseIndex}___examples___"]`);
      inputs.forEach(input => {
          const match = input.name.match(/examples___(\d+)___/);
          if (match) {
              const idx = parseInt(match[1], 10);
              if (idx > maxIndex) maxIndex = idx;
          }
      });
      const exIndex = maxIndex + 1;
      const template = `<div class="dynamic-list-item sub-item-block example-block"> <button type="button" class="delete-item-btn" title="Remove example">×</button> <textarea id="german_senses_${senseIndex}_examples_${exIndex}_quote" class="markdown-editor" name="german_senses___${senseIndex}___examples___${exIndex}___quote" placeholder="Example (Ger.)"></textarea> <input type="text" name="german_senses___${senseIndex}___examples___${exIndex}___source_abbr" placeholder="Source" value=""> </div>`;
      createDynamicItem(`german-examples-container-${senseIndex}`, template, exIndex, (idx, newItem) => {
          if (example) {
              newItem.querySelector('textarea').value = example.quote || '';
              newItem.querySelector('input').value = example.source_abbr || '';
          }
          initializeMarkdownEditor(`german_senses_${senseIndex}_examples_${exIndex}_quote`);
      });
  }
  
  // --- 7. VARIANTS & VARIANT SENSES ---

  function addVariantSenseItem(variantIndex, item = null) {
      const containerId = `variant-senses-container-${variantIndex}`;
      const container = document.getElementById(containerId);
      if (!container) return;

      const templateNode = document.getElementById('variant-sense-template');
      if (!templateNode) return;

      let maxIndex = -1;
      const regex = new RegExp(`variants___${variantIndex}___senses___(\\d+)___`);
      
      container.querySelectorAll('input, select, textarea').forEach(input => {
          const match = input.name.match(regex);
          if (match) {
              const idx = parseInt(match[1], 10);
              if (idx > maxIndex) maxIndex = idx;
          }
      });
      const senseIndex = maxIndex + 1;

      let html = templateNode.innerHTML
          .replace(/VAR_IDX/g, variantIndex)
          .replace(/SENSE_IDX/g, senseIndex);

      const wrapper = document.createElement('div');
      wrapper.innerHTML = html;
      const newItem = wrapper.firstElementChild;
      container.appendChild(newItem);

      // 1. Ініціалізація Choices.js для нового значення
      initializeChoices(newItem.querySelector(`select[name*="region_style"]`), item ? item.region_style : []);
      initializeChoices(newItem.querySelector(`select[name*="geo"]`), item ? item.geo : []);
      initializeChoices(newItem.querySelector(`select[name*="style"]`), item ? item.style : []);

      // 2. Заповнення даними
      if (item) {
          const defInput = newItem.querySelector(`textarea[name*="def"]`);
          if (defInput) defInput.value = item.def || '';

          const timeInput = newItem.querySelector(`input[name*="time"]`);
          if (timeInput) timeInput.value = item.time || '';

          const sourceSelect = newItem.querySelector(`select[name*="source"]`);
          if (sourceSelect && item.source) sourceSelect.value = item.source.id;
          
          const abbrInput = newItem.querySelector(`input[name*="source_abbr"]`);
          if (abbrInput && item.source) abbrInput.value = item.source.abbr || '';
      }

      // 3. Слухач для джерела
      const sourceSelect = newItem.querySelector(`select[name*="source"]`);
      const hiddenAbbr = newItem.querySelector(`input[name*="source_abbr"]`);
      if (sourceSelect && hiddenAbbr) {
          sourceSelect.addEventListener('change', function() {
              const selectedOption = this.options[this.selectedIndex];
              hiddenAbbr.value = (selectedOption && selectedOption.value) ? selectedOption.text : '';
          });
          if (sourceSelect.value) {
             const selectedOption = sourceSelect.options[sourceSelect.selectedIndex];
             hiddenAbbr.value = selectedOption.text;
          }
      }

      // 4. Ініціалізація Markdown редактора
      const editorId = `variants___${variantIndex}___senses___${senseIndex}___def`;
      initializeMarkdownEditor(editorId);
  }

function addVariantItem(item = null) {
      const templateNode = document.getElementById('variant-template');
      if (!templateNode) return;

      variantCounter = createDynamicItem('variants-container', templateNode.innerHTML, variantCounter, (idx, newItem) => {
          
          if (item) {
              const orthInput = newItem.querySelector(`input[name="variants___${idx}___orth"]`);
              if (orthInput) orthInput.value = item.orth || '';

              // Заповнення PoS (частини мови)
              const posSelect = newItem.querySelector(`select[name="variants___${idx}___pos"]`);
              if (posSelect) posSelect.value = item.pos || '';
          }
          
          // Додаємо вкладені значення
          if (item && item.senses && item.senses.length > 0) {
              item.senses.forEach(sense => {
                  addVariantSenseItem(idx, sense);
              });
          } else {
              addVariantSenseItem(idx); 
          }
      });
  }

  // --- 8. EQUIVALENTS ---
  function addEquivDefItem(equivIndex, defData = null) {
    const container = document.getElementById(`equiv-defs-container-${equivIndex}`);
    if (!container) return;
    
    let maxIndex = -1;
    const inputs = container.querySelectorAll(`[name^="equivalents___${equivIndex}___defs___"]`);
    inputs.forEach(input => {
        const parts = input.name.split('___');
        // equivalents___0___defs___1___text (або source) -> parts[3] це індекс
        if (parts.length >= 4) {
            const idx = parseInt(parts[3], 10);
            if (!isNaN(idx) && idx > maxIndex) maxIndex = idx;
        }
    });
    const defIndex = maxIndex + 1;

    let sourceOptions = '<option value="">(Джерело)</option>';
    if (window.biblData) {
        window.biblData.forEach(b => {
            const isSelected = (defData && defData.source === b.id) ? 'selected' : '';
            sourceOptions += `<option value="${b.id}" title="${b.title}" ${isSelected}>${b.abbr}</option>`;
        });
    }

    const defValue = (defData && defData.text) ? defData.text.replace(/"/g, '&quot;') : '';
    const sourceAbbrValue = (defData && defData.source_abbr) ? defData.source_abbr : '';

    const template = `
        <div class="dynamic-list-item sub-item-block equiv-def-block" style="display: flex; gap: 5px; align-items: center; padding: 3px 0;"> 
            <button type="button" class="delete-item-btn" style="position: static; margin-right: 5px; color: #dc3545;">×</button> 
            <input type="text" name="equivalents___${equivIndex}___defs___${defIndex}___text" 
                   placeholder="Meaning" value="${defValue}" style="flex-grow: 1;">
            <select name="equivalents___${equivIndex}___defs___${defIndex}___source" 
                    class="equiv-source-select" style="width: 120px; font-size: 0.85em;">
                ${sourceOptions}
            </select>
            <input type="hidden" name="equivalents___${equivIndex}___defs___${defIndex}___source_abbr" value="${sourceAbbrValue}">
        </div>`;
    
    const wrapper = document.createElement('div');
    wrapper.innerHTML = template;
    const newItem = wrapper.firstElementChild;
    container.appendChild(newItem);

    const select = newItem.querySelector('select');
    const hidden = newItem.querySelector('input[type="hidden"]');
    select.addEventListener('change', function() {
        const option = this.options[this.selectedIndex];
        if (option.value) { hidden.value = option.text; } else { hidden.value = ''; }
    });
  }

  function addEquivalentItem(item = null, index = null) {
      const i = index !== null ? index : equivalentCounter;
      const templateNode = document.getElementById('equivalent-template');
      if (!templateNode) return;
      
      equivalentCounter = createDynamicItem('equivalents-container', templateNode.innerHTML, i, (idx, newItem) => {
          if (item) {
              const itemBlock = document.querySelector(`#equivalents-container .equivalent-block:nth-last-child(1)`);
              if (itemBlock) {
                  const langSelect = itemBlock.querySelector('select[name$="lang"]');
                  const wordInput = itemBlock.querySelector('input[name$="word"]');
                  const regionSelect = itemBlock.querySelector('select[name$="region"]');
                  const posSelect = itemBlock.querySelector('select[name$="pos"]');

                  if (langSelect) langSelect.value = item.lang;
                  if (wordInput) wordInput.value = item.word;
                  if (regionSelect) regionSelect.value = item.region || '';
                  if (posSelect) posSelect.value = item.pos || '';

                  if (item.defs) item.defs.forEach(def => addEquivDefItem(idx, def));
              }
          }
      });
  }
  
  function addBiblItem(item = null, index = null) {
      const i = index !== null ? index : biblCounter;
      let options = '<option value="">(Select abbreviation)</option>';
      if (window.biblData) {
          window.biblData.forEach(b => {
              options += `<option value="${b.id}" ${item && item.id === b.id ? 'selected' : ''}>${b.abbr}</option>`;
          });
      }
      options += '<option value="new">-- Add new source --</option>';

      const template = `
        <div class="dynamic-list-item item-block bibl-block" style="padding: 10px; margin-bottom: 10px; border: 1px solid #ddd; background: #fafafa;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <h4 style="margin: 0; font-size: 1rem;">Source #${i + 1}</h4>
                <button type="button" class="delete-item-btn" title="Remove" style="position: static; color: #dc3545;">×</button>
            </div>
            
            <div class="form-group">
                <label>Abbreviation</label>
                <select name="bibliography___${i}___id" class="bibl-abbr-select" required style="width: 100%;">
                    ${options}
                </select>
            </div>
            
            <!-- Поля для нового джерела -->
            <div class="new-bibl-fields" style="display: none; border-left: 3px solid #28a745; padding-left: 10px; margin: 10px 0;">
                <div class="form-group">
                    <label>New Abbreviation</label>
                    <input type="text" name="bibliography___${i}___new_abbr" placeholder="e.g., ESUM">
                </div>
                <div class="form-group">
                    <label>Full Title</label>
                    <input type="text" name="bibliography___${i}___new_title" placeholder="Etymological Dictionary...">
                </div>
                 <div class="form-group">
                    <label>URL</label>
                    <input type="url" name="bibliography___${i}___new_url" placeholder="http://...">
                </div>
            </div>
            
            <div class="form-row" style="display: flex; gap: 10px;">
                <div class="form-group form-group--compact" style="flex: 1;">
                    <label>Volume</label>
                    <input type="text" name="bibliography___${i}___volume" placeholder="т. 1" value="">
                </div>
                <div class="form-group form-group--compact" style="flex: 1;">
                    <label>Page</label>
                    <input type="text" name="bibliography___${i}___page" placeholder="с. 123" value="">
                </div>
            </div>
        </div>`;
        
      const wrapper = document.createElement('div');
      wrapper.innerHTML = template;
      const newItem = wrapper.firstElementChild;
      
      const container = document.getElementById('bibl-container');
      if (container) {
          container.appendChild(newItem);
      } else {
          console.error("Container #bibl-container not found!");
      }

      biblCounter = i + 1;
      
      if (item) {
          const select = newItem.querySelector('select[name$="_id"]');
          if (select) select.value = item.id;
          const volInput = newItem.querySelector(`input[name$="volume"]`);
          const pageInput = newItem.querySelector(`input[name$="page"]`);
          if (volInput) volInput.value = item.volume || '';
          if (pageInput) pageInput.value = item.page || '';
      }
  }

  function addMediatorItem(value = '') {
    let optionsHTML = '<option value="">(не вказано)</option>';
    if (window.back_data && window.back_data.languages) {
        window.back_data.languages.forEach(lang => {
            const selected = (lang.term === value) ? 'selected' : '';
            optionsHTML += `<option value="${lang.term}" ${selected}>${lang.term}</option>`;
        });
    }
    const template = `<div class="dynamic-list-item sub-item-block mediator-item"><button type="button" class="delete-item-btn" title="Remove">×</button><select name="borrowing_mediators">${optionsHTML}</select></div>`;
    createDynamicItem('alternative-mediators-container', template, mediatorCounter++);
  }

  function addAlterDonorItem(value = '') {
      const template = `<div class="dynamic-list-item sub-item-block alter-donor-item"> <button type="button" class="delete-item-btn" title="Remove">×</button> <input type="text" name="alter_donors" value="" placeholder="Alternative source language"> </div>`;
      const container = document.getElementById('alter-donors-container');
      const wrapper = document.createElement('div');
      wrapper.innerHTML = template;
      const newItem = wrapper.firstElementChild;
      container.appendChild(newItem);
      if (value) newItem.querySelector('input').value = value;
      alterDonorCounter++;
  }

  function addAlterGermanDonorItem(item = null) {
    const templateNode = document.getElementById('alter-german-donor-template');
    if (!templateNode) return;
    alterGermanDonorCounter = createDynamicItem('alter-german-donors-container', templateNode.innerHTML, alterGermanDonorCounter, (idx) => {
        if (item) {
            const itemBlock = document.querySelector(`#alter-german-donors-container .alter-german-donor-item:nth-last-child(1)`);
            if (itemBlock) {
                itemBlock.querySelector('select[name$="lang"]').value = item.lang;
                itemBlock.querySelector('input[name$="word"]').value = item.word;
            }
        }
    });
  }

  // --- 9. POPULATE & EVENTS ---
  const entryForm = document.getElementById('entry-form');
  const entryData = window.entryData || null;
  
  if (entryForm) {
      setupConditionalUI();
      if (entryData && Object.keys(entryData).length > 0) {
          populateFormForEditing();
      } else {
          addSenseItem();
      }
      
      // SUBMIT HANDLER (STANDARD FORM SUBMISSION)
      entryForm.addEventListener('submit', function (e) {
          // НЕ використовуємо preventDefault(), щоб форма відправилася стандартно.
          
          if (typeof editors === 'object') {
              Object.values(editors).forEach(ed => {
                  if (ed && typeof ed.value === 'function' && ed.element) {
                      ed.element.value = ed.value();
                  }
              });
          }
      });
  }

  function populateFormForEditing() {
    if (entryData.senses && entryData.senses.length > 0) entryData.senses.forEach(addSenseItem); else if (entryData.entry_type !== 'redirect') addSenseItem();
    if (entryData.variants) entryData.variants.forEach(addVariantItem);
    if (entryData.german_senses) entryData.german_senses.forEach(addGermanSenseItem);
    if (entryData.bibliography) entryData.bibliography.forEach(addBiblItem);
    if (entryData.equivalents) entryData.equivalents.forEach(addEquivalentItem);
    if (entryData.borrowing_mediators && entryData.borrowing_mediators.length > 1) {
        entryData.borrowing_mediators.slice(1).forEach(addMediatorItem);
    }
    if (entryData.alter_donors) entryData.alter_donors.forEach(addAlterDonorItem);
    if (entryData.alter_german_etyms) entryData.alter_german_etyms.forEach(addAlterGermanDonorItem);
  }
  
  // Event Listeners
  document.body.addEventListener('click', function (event) {
      const btn = event.target.closest('button');
      if (!btn) return;

      if (btn.classList.contains('set-today-btn')) {
          event.preventDefault();
          let dateInput = btn.parentElement.querySelector('input');
          if (!dateInput) {
              const group = btn.closest('.form-group');
              if (group) dateInput = group.querySelector('.date-input');
          }
          if (dateInput) dateInput.value = getTodayDate();
          return;
      }

      if (btn.classList.contains('add-item-btn') || 
          btn.classList.contains('add-variant-sense-btn') || 
          btn.classList.contains('add-equiv-def-btn') ||
          // Перевірка ID для кнопок, що можуть не мати класу add-item-btn
          btn.id === 'add-alter-donor-btn' ||
          btn.id === 'add-alter-german-donor-btn' ||
          btn.id === 'add-bibl-btn' || // ТУТ БУЛА ПОМИЛКА: додано add-bibl-btn
          btn.id === 'add-alternative-mediator-btn') {
          
          event.preventDefault();
          
          if (btn.id === 'add-sense-item-btn') addSenseItem();
          else if (btn.id === 'add-variant-btn') addVariantItem();
          else if (btn.classList.contains('add-variant-sense-btn')) {
              const variantIndex = btn.dataset.variantIndex;
              addVariantSenseItem(variantIndex);
          }
          else if (btn.id === 'add-german-sense-item-btn') addGermanSenseItem();
          else if (btn.id === 'add-bibl-btn') addBiblItem();
          else if (btn.id === 'add-equivalent-btn') addEquivalentItem();
          else if (btn.id === 'add-alternative-mediator-btn') addMediatorItem();
          else if (btn.id === 'add-alter-donor-btn') addAlterDonorItem();
          else if (btn.id === 'add-alter-german-donor-btn') addAlterGermanDonorItem();
          
          if (btn.classList.contains('add-example-btn')) addExampleItem(btn.dataset.senseIndex);
          if (btn.classList.contains('add-german-example-btn')) addGermanExampleItem(btn.dataset.senseIndex);
          if (btn.classList.contains('add-sense-translation-btn')) addSenseTranslationItem(btn.dataset.senseIndex);
          if (btn.classList.contains('add-german-sense-translation-btn')) addGermanSenseTranslationItem(btn.dataset.senseIndex);
          if (btn.classList.contains('add-equiv-def-btn')) addEquivDefItem(btn.dataset.equivIndex);
      }

      if (btn.classList.contains('delete-item-btn')) {
          event.preventDefault();
          const itemToRemove = btn.closest('.dynamic-list-item');
          if (itemToRemove) {
              itemToRemove.classList.add('fade-out');
              setTimeout(() => itemToRemove.remove(), 300);
          }
      }
  });
  
  // Допоміжні функції для селектів
  document.body.addEventListener('change', function(event) {
      if (event.target.classList.contains('bibl-abbr-select')) {
          const block = event.target.closest('.bibl-block');
          const newFields = block.querySelector('.new-bibl-fields');
          const isNew = event.target.value === 'new';
          
          newFields.style.display = isNew ? 'block' : 'none';
          
          // Робимо обов'язковими тільки Абревіатуру та Назву. URL - опціональний.
          const reqInputs = newFields.querySelectorAll('input[name$="_new_abbr"], input[name$="_new_title"]');
          reqInputs.forEach(input => input.required = isNew);
      }
      
      if (event.target.classList.contains('domain-main-select')) {
          const subSelectId = event.target.dataset.subSelectId;
          if (subSelectId) setupCascadingSelects(event.target.id, subSelectId, window.domainData, null);
      }
  });

  // --- 11. SIDEBAR & SEARCH ---
  const mainLayout = document.querySelector('.main-layout');
  if (mainLayout) {
      mainLayout.addEventListener('click', e => {
          const link = e.target.closest('.entry-link');
          if (link) {
              e.preventDefault();
              const id = link.getAttribute('data-entry-id');
              history.pushState({ entryId: id }, '', `#${id}`);
              loadEntry(id);
          }
      });

      window.addEventListener('popstate', e => {
          if (e.state && e.state.entryId) loadEntry(e.state.entryId);
          else if (window.location.hash) loadEntry(window.location.hash.substring(1));
      });
      if (window.location.hash) {
          loadEntry(window.location.hash.substring(1));
      }
  }

  function loadEntry(entryId) {
    if (!entryId) return;
    const entryViewPanel = document.querySelector('.entry-view-panel');
    if (entryViewPanel) {
        entryViewPanel.innerHTML = '<p style="color:#666; margin-top:20px; text-align:center;">Loading...</p>';
        fetch(`/entry/${entryId}?partial=1`)
            .then(r => r.text())
            .then(html => {
                entryViewPanel.innerHTML = html;
                disableBiblLinks();
            })
            .catch(() => entryViewPanel.innerHTML = '<p>Error loading entry.</p>');
    }
    setTimeout(() => {
        const sidebar = document.querySelector('.main-layout');
        if (sidebar) {
            sidebar.querySelectorAll('.entry-link.active').forEach(l => l.classList.remove('active'));
            const activeLink = sidebar.querySelector(`.entry-link[data-entry-id="${entryId}"]`);
            if (activeLink) {
                activeLink.classList.add('active');
                activeLink.scrollIntoView({ block: 'center', behavior: 'smooth' });
            }
        }
    }, 100);
  }

  const searchForm = document.getElementById('search-form');
  const searchInput = document.getElementById('search-input');
  const wordListContent = document.getElementById('word-list-content');
  const filterGroup = document.getElementById('filter-group');
  const langSwitchBtn = document.getElementById('lang-switch-btn');
  let debounceTimeout;

  function updateWordList() {
      if (!searchInput || !searchForm || !wordListContent || !filterGroup) return;
      const query = searchInput.value;
      const langInput = searchForm.querySelector('input[name="lang"]');
      const lang = langInput ? langInput.value : 'uk';
      const showStatus = filterGroup.querySelector('input[name="show"]:checked').value;
      const url = `/?q=${encodeURIComponent(query)}&lang=${lang}&show=${showStatus}&partial_list=1`;

      fetch(url)
        .then(response => response.text())
        .then(html => {
            wordListContent.innerHTML = html;
        })
        .catch(error => console.error('Error updating word list:', error));
  }

  if (searchInput && searchForm && wordListContent && filterGroup) {
      searchInput.addEventListener('input', function() {
          clearTimeout(debounceTimeout);
          debounceTimeout = setTimeout(updateWordList, 300);
      });
      filterGroup.addEventListener('change', function(event) {
          if (event.target.name === 'show') updateWordList();
      });
      searchForm.addEventListener('submit', function(event) {
          event.preventDefault();
          clearTimeout(debounceTimeout);
          updateWordList();
      });
  }

  if (langSwitchBtn) {
      langSwitchBtn.addEventListener('click', function() {
          const baseUrl = this.dataset.baseUrl;
          const newLang = this.dataset.langSwitch;
          const query = searchInput ? searchInput.value : '';
          const showStatus = filterGroup ? filterGroup.querySelector('input[name="show"]:checked').value : 'all';
          const params = new URLSearchParams({ lang: newLang, q: query, show: showStatus });
          window.location.href = `${baseUrl}?${params.toString()}`;
      });
  }
});