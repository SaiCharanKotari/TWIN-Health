/**
 * form.js — TwinHealth AI Form Engine
 *
 * Handles:
 *  - Basic / Advanced mode sections
 *  - Manual form rendering with all clinical fields
 *  - CSV / Excel upload via SheetJS
 *  - Live BMI calculation
 *  - Field validation (clinical ranges)
 *  - "Add Missing Data" mode (highlight specific fields)
 *  - Template CSV generation/download
 */
'use strict';

/* ═══════════════════════════════════════════════════════════════
   FIELD DEFINITIONS
   ═══════════════════════════════════════════════════════════════ */

const FORM_SECTIONS = [
  {
    id: 'basic_info', level: 1, icon: '👤',
    title: 'Basic Information',
    subtitle: 'Age, sex, height, weight — Level 1',
    badge: 'badge-l1', badgeText: 'Level 1 — Required',
    defaultOpen: true,
    fields: [
      { id:'age',       label:'Age',    type:'number', unit:'yrs',  min:0,  max:120, step:1,   placeholder:'42', required:true },
      { id:'sex',       label:'Sex',    type:'radio',  options:[{v:'male',l:'♂ Male'},{v:'female',l:'♀ Female'},{v:'other',l:'Other'}] },
      { id:'height_cm', label:'Height', type:'number', unit:'cm',   min:50, max:300, step:0.1, placeholder:'172' },
      { id:'weight_kg', label:'Weight', type:'number', unit:'kg',   min:10, max:700, step:0.1, placeholder:'70' },
      { id:'_bmi',      label:'BMI (auto-calculated)', type:'bmi' },
    ],
  },
  {
    id: 'lifestyle', level: 1, icon: '🏃',
    title: 'Lifestyle',
    subtitle: 'Smoking, alcohol, physical activity — Level 1',
    badge: 'badge-l1', badgeText: 'Level 1',
    defaultOpen: false,
    fields: [
      { id:'smoking_status',    label:'Smoking Status',    type:'select', options:[
          {v:'',l:'— Select —'},{v:'never',l:'Never smoked'},{v:'former',l:'Former smoker'},{v:'current',l:'Current smoker'},{v:'unknown',l:'Unknown'}
        ]},
      { id:'alcohol_use',       label:'Alcohol Use',       type:'select', options:[
          {v:'',l:'— Select —'},{v:'none',l:'None'},{v:'occasional',l:'Occasional'},{v:'regular',l:'Regular'},{v:'unknown',l:'Unknown'}
        ]},
      { id:'physical_activity', label:'Physical Activity', type:'select', options:[
          {v:'',l:'— Select —'},{v:'low',l:'Low (sedentary)'},{v:'moderate',l:'Moderate (3-4×/week)'},{v:'high',l:'High (5+ days/week)'},{v:'unknown',l:'Unknown'}
        ]},
    ],
  },
  {
    id: 'medical_history', level: 1, icon: '🏥',
    title: 'Medical History',
    subtitle: 'Existing diagnosed conditions — Level 1',
    badge: 'badge-l1', badgeText: 'Level 1',
    defaultOpen: false,
    fields: [
      { id:'_conditions', label:'Existing Conditions', type:'toggle-group', toggles: [
          {id:'hypertension',          label:'🩸 Hypertension'},
          {id:'diabetes_history',      label:'🩺 Diabetes'},
          {id:'heart_disease_history', label:'❤️  Heart Disease'},
          {id:'kidney_disease_history',label:'🫘 Kidney Disease'},
          {id:'liver_disease_history', label:'🟤 Liver Disease'},
          {id:'previous_stroke',       label:'🧠 Previous Stroke / TIA'},
        ]},
    ],
  },
  {
    id: 'family_history', level: 1, icon: '🧬',
    title: 'Family History',
    subtitle: 'First-degree relatives — Level 1',
    badge: 'badge-l1', badgeText: 'Level 1',
    defaultOpen: false,
    fields: [
      { id:'_fam', label:'Family History of:', type:'toggle-group', toggles: [
          {id:'family_history_diabetes',      label:'🩺 Diabetes'},
          {id:'family_history_heart_disease', label:'❤️  Heart Disease'},
          {id:'family_history_kidney_disease',label:'🫘 Kidney Disease'},
          {id:'family_history_liver_disease', label:'🟤 Liver Disease'},
          {id:'family_history_stroke',        label:'🧠 Stroke'},
        ]},
    ],
  },

  /* ── Level 2 — Advanced only ── */
  {
    id: 'vitals', level: 2, icon: '💓',
    title: 'Vital Signs',
    subtitle: 'Blood pressure, heart rate — Level 2',
    badge: 'badge-l2', badgeText: 'Level 2',
    defaultOpen: true,
    advancedOnly: true,
    fields: [
      { id:'systolic_bp',  label:'Systolic BP',        type:'number', unit:'mmHg', min:60,  max:260, placeholder:'120' },
      { id:'diastolic_bp', label:'Diastolic BP',       type:'number', unit:'mmHg', min:40,  max:160, placeholder:'80'  },
      { id:'heart_rate',   label:'Resting Heart Rate', type:'number', unit:'bpm',  min:30,  max:220, placeholder:'72'  },
    ],
  },
  {
    id: 'blood_sugar', level: 2, icon: '🩸',
    title: 'Blood Sugar',
    subtitle: 'Glucose, HbA1c, insulin — Level 2',
    badge: 'badge-l2', badgeText: 'Level 2',
    defaultOpen: true,
    advancedOnly: true,
    fields: [
      { id:'fasting_glucose', label:'Fasting Blood Glucose', type:'number', unit:'mg/dL', min:20,  max:700,  placeholder:'95',  step:0.1 },
      { id:'random_glucose',  label:'Random Blood Glucose',  type:'number', unit:'mg/dL', min:20,  max:700,  placeholder:'120', step:0.1 },
      { id:'hba1c',           label:'HbA1c',                 type:'number', unit:'%',     min:2,   max:20,   placeholder:'5.4', step:0.1 },
      { id:'insulin',         label:'Serum Insulin',         type:'number', unit:'μU/mL', min:0,   max:500,  placeholder:'',    step:0.1 },
    ],
  },
  {
    id: 'cholesterol', level: 2, icon: '🫀',
    title: 'Cholesterol Panel',
    subtitle: 'Total cholesterol, HDL, LDL, triglycerides — Level 2',
    badge: 'badge-l2', badgeText: 'Level 2',
    defaultOpen: false,
    advancedOnly: true,
    fields: [
      { id:'total_cholesterol', label:'Total Cholesterol', type:'number', unit:'mg/dL', min:50,  max:700, placeholder:'190' },
      { id:'hdl',               label:'HDL Cholesterol',   type:'number', unit:'mg/dL', min:5,   max:150, placeholder:'55'  },
      { id:'ldl',               label:'LDL Cholesterol',   type:'number', unit:'mg/dL', min:20,  max:500, placeholder:'110' },
      { id:'triglycerides',     label:'Triglycerides',     type:'number', unit:'mg/dL', min:20,  max:2000,placeholder:'130' },
    ],
  },

  /* ── Level 3 — Advanced only ── */
  {
    id: 'kidney', level: 3, icon: '🫘',
    title: 'Kidney Panel',
    subtitle: 'Required for CKD assessment — Level 3',
    badge: 'badge-l3', badgeText: 'Level 3',
    defaultOpen: false,
    advancedOnly: true,
    note: 'Required for <strong>CKD assessment</strong>. Early CKD has no symptoms — testing is the only reliable way to detect it (NIDDK).',
    fields: [
      { id:'creatinine',    label:'Serum Creatinine',       type:'number', unit:'mg/dL',          min:0.1,  max:20,    step:0.01, placeholder:'0.9' },
      { id:'egfr',          label:'eGFR',                   type:'number', unit:'mL/min/1.73m²',  min:1,    max:200,   placeholder:'95'  },
      { id:'bun',           label:'BUN / Urea',             type:'number', unit:'mg/dL',          min:1,    max:200,   placeholder:'14'  },
      { id:'uacr',          label:'UACR (Urine Albumin/Cr)',type:'number', unit:'mg/g',           min:0,    max:10000, placeholder:'10'  },
      { id:'urine_protein', label:'Urine Protein',          type:'number', unit:'mg/dL',          min:0,    max:5000,  placeholder:''    },
      { id:'sodium',        label:'Sodium',                 type:'number', unit:'mEq/L',          min:100,  max:180,   placeholder:'140' },
      { id:'potassium',     label:'Potassium',              type:'number', unit:'mEq/L',          min:1,    max:10,    step:0.1,  placeholder:'4.0' },
    ],
  },
  {
    id: 'liver', level: 3, icon: '🟤',
    title: 'Liver Panel',
    subtitle: 'Required for liver disease assessment — Level 3',
    badge: 'badge-l3', badgeText: 'Level 3',
    defaultOpen: false,
    advancedOnly: true,
    note: 'Required for <strong>liver disease assessment</strong>.',
    fields: [
      { id:'alt',              label:'ALT (SGPT)',           type:'number', unit:'U/L',   min:1,   max:5000,  placeholder:'25'  },
      { id:'ast',              label:'AST (SGOT)',           type:'number', unit:'U/L',   min:1,   max:5000,  placeholder:'22'  },
      { id:'alp',              label:'Alkaline Phosphatase', type:'number', unit:'U/L',   min:1,   max:2000,  placeholder:'80'  },
      { id:'total_bilirubin',  label:'Total Bilirubin',      type:'number', unit:'mg/dL', min:0,   max:50,    step:0.01, placeholder:'0.8' },
      { id:'direct_bilirubin', label:'Direct Bilirubin',     type:'number', unit:'mg/dL', min:0,   max:30,    step:0.01, placeholder:'0.2' },
      { id:'albumin',          label:'Albumin',              type:'number', unit:'g/dL',  min:0.5, max:10,    step:0.1,  placeholder:'4.2' },
      { id:'total_protein',    label:'Total Protein',        type:'number', unit:'g/dL',  min:1,   max:15,    step:0.1,  placeholder:'7.2' },
    ],
  },
  {
    id: 'cbc', level: 3, icon: '🧪',
    title: 'General Blood Tests (CBC)',
    subtitle: 'Hemoglobin, hematocrit — Level 3',
    badge: 'badge-l3', badgeText: 'Level 3',
    defaultOpen: false,
    advancedOnly: true,
    fields: [
      { id:'hemoglobin', label:'Hemoglobin',  type:'number', unit:'g/dL',    min:1,   max:25,  step:0.1, placeholder:'14' },
      { id:'hematocrit', label:'Hematocrit',  type:'number', unit:'%',       min:5,   max:70,  step:0.1, placeholder:'42' },
      { id:'wbc',        label:'WBC Count',   type:'number', unit:'10³/µL',  min:0.5, max:100, step:0.1, placeholder:'7.0'},
    ],
  },
];

/* CSV → schema field name mapping */
const CSV_FIELD_MAP = {};
FORM_SECTIONS.forEach(s => s.fields.forEach(f => {
  if (!f.id.startsWith('_')) CSV_FIELD_MAP[f.id] = f.id;
  if (f.toggles) f.toggles.forEach(t => { CSV_FIELD_MAP[t.id] = t.id; });
}));

/* ═══════════════════════════════════════════════════════════════
   FORM STATE
   ═══════════════════════════════════════════════════════════════ */

window.formState = {
  mode:           'basic',   // 'basic' | 'advanced'
  inputMethod:    'form',    // 'form'  | 'upload'
  data:           {},        // accumulated patient data
  highlightFields: [],       // for "add missing data" mode
};

/* ═══════════════════════════════════════════════════════════════
   RENDER FORM
   ═══════════════════════════════════════════════════════════════ */

function renderForm(highlightFields = []) {
  formState.highlightFields = highlightFields;
  const container = document.getElementById('form-container');
  container.innerHTML = '';

  const sectionsToShow = FORM_SECTIONS.filter(s =>
    formState.mode === 'advanced' ? true : !s.advancedOnly
  );

  sectionsToShow.forEach(section => {
    container.appendChild(buildSection(section));
  });

  wireUpBMI();
  wireUpFieldCounts();

  // Highlight missing fields
  if (highlightFields.length > 0) {
    highlightFields.forEach(fid => {
      const el = document.getElementById(`f_${fid}`);
      if (el) el.classList.add('missing-highlight');
      // Also scroll to first highlighted
    });
    const first = document.getElementById(`f_${highlightFields[0]}`);
    if (first) first.scrollIntoView({behavior:'smooth', block:'center'});
  }
}

function buildSection(section) {
  const div = document.createElement('div');
  div.className = `form-section${section.defaultOpen ? ' open' : ''}`;
  div.id = `section_${section.id}`;

  const noteHtml = section.note
    ? `<div class="error-toast" style="margin:0 0 12px;border-color:rgba(6,182,212,.2);background:rgba(6,182,212,.05)">
         <span class="et-icon">💡</span>
         <div class="et-text" style="font-size:12px">${section.note}</div>
       </div>`
    : '';

  div.innerHTML = `
    <div class="section-header" onclick="toggleSection('${section.id}')">
      <span class="section-icon">${section.icon}</span>
      <div class="section-title-wrap">
        <div class="section-title">${section.title}</div>
        <div class="section-subtitle">${section.subtitle}</div>
      </div>
      <span class="section-level-badge ${section.badge}">${section.badgeText}</span>
      <span class="section-chevron">▼</span>
    </div>
    <div class="section-body">
      ${noteHtml}
      <div class="fields-grid" id="grid_${section.id}"></div>
    </div>
  `;

  const grid = div.querySelector(`#grid_${section.id}`);
  section.fields.forEach(field => renderField(field, grid));
  return div;
}

function toggleSection(id) {
  const el = document.getElementById(`section_${id}`);
  if (el) el.classList.toggle('open');
}

/* ═══════════════════════════════════════════════════════════════
   FIELD RENDERERS
   ═══════════════════════════════════════════════════════════════ */

function renderField(field, parent) {
  if (field.type === 'bmi') {
    const wrap = document.createElement('div');
    wrap.className = 'field-wrap full';
    wrap.innerHTML = `
      <span class="field-label">BMI <span class="field-optional-marker">(auto-calculated from height + weight)</span></span>
      <div class="bmi-chip" id="bmi-chip">
        <div class="bmi-val" id="bmi-val">—</div>
        <div class="bmi-meta">
          <div class="bmi-lbl">Body Mass Index</div>
          <div class="bmi-cat" id="bmi-cat">Enter height &amp; weight</div>
        </div>
      </div>`;
    parent.appendChild(wrap);
    return;
  }

  if (field.type === 'toggle-group') {
    const wrap = document.createElement('div');
    wrap.className = 'field-wrap full';
    const tg = document.createElement('div');
    tg.className = 'toggle-group';
    field.toggles.forEach(t => {
      const lbl = document.createElement('label');
      lbl.className = 'toggle-item';
      lbl.innerHTML = `
        <span class="toggle-lbl">${t.label}</span>
        <input type="checkbox" class="t-input" id="f_${t.id}" data-field="${t.id}"
          ${formState.data[t.id] === true ? 'checked' : ''}>
        <span class="t-switch"></span>`;
      lbl.addEventListener('change', collectData);
      tg.appendChild(lbl);
    });
    wrap.innerHTML = `<span class="field-label">${field.label}</span>`;
    wrap.appendChild(tg);
    parent.appendChild(wrap);
    return;
  }

  if (field.type === 'radio') {
    const wrap = document.createElement('div');
    wrap.className = 'field-wrap full';
    const rg = document.createElement('div');
    rg.className = 'radio-group';
    field.options.forEach(opt => {
      const uid = `radio_${field.id}_${opt.v}`;
      rg.innerHTML += `
        <input type="radio" class="radio-option" name="${field.id}" id="${uid}"
               value="${opt.v}" data-field="${field.id}"
               ${formState.data[field.id] === opt.v ? 'checked' : ''}>
        <label class="radio-lbl" for="${uid}">
          <span class="radio-dot"></span>${opt.l}
        </label>`;
    });
    rg.querySelectorAll('input').forEach(i => i.addEventListener('change', collectData));
    wrap.innerHTML = `<span class="field-label">${field.label}${field.required ? ' <span class="field-required">*</span>' : ''}</span>`;
    wrap.appendChild(rg);
    parent.appendChild(wrap);
    return;
  }

  if (field.type === 'select') {
    const wrap = document.createElement('div');
    wrap.className = 'field-wrap';
    const opts = field.options.map(o =>
      `<option value="${o.v}" ${formState.data[field.id] === o.v ? 'selected':''}>${o.l}</option>`
    ).join('');
    wrap.innerHTML = `
      <label class="field-label" for="f_${field.id}">${field.label}</label>
      <select class="field-input" id="f_${field.id}" data-field="${field.id}">${opts}</select>`;
    wrap.querySelector('select').addEventListener('change', collectData);
    parent.appendChild(wrap);
    return;
  }

  // number input
  const wrap = document.createElement('div');
  wrap.className = 'field-wrap';
  const stepAttr = field.step ? `step="${field.step}"` : '';
  const savedVal = formState.data[field.id] !== undefined ? formState.data[field.id] : '';
  const unitHtml = field.unit
    ? `<div class="input-unit-wrap">
         <input class="field-input${formState.highlightFields.includes(field.id) ? ' missing-highlight' : ''}"
                type="number" id="f_${field.id}" data-field="${field.id}"
                placeholder="${field.placeholder||''}"
                min="${field.min||''}" max="${field.max||''}" ${stepAttr}
                value="${savedVal}">
         <span class="field-unit">${field.unit}</span>
       </div>`
    : `<input class="field-input" type="number" id="f_${field.id}" data-field="${field.id}"
              placeholder="${field.placeholder||''}"
              min="${field.min||''}" max="${field.max||''}" ${stepAttr}
              value="${savedVal}">`;

  wrap.innerHTML = `
    <label class="field-label" for="f_${field.id}">
      ${field.label}${field.required ? ' <span class="field-required">*</span>' : ''}
    </label>
    ${unitHtml}`;
  wrap.querySelector('input').addEventListener('input', e => { collectData(); updateBMI(); });
  parent.appendChild(wrap);
}

/* ═══════════════════════════════════════════════════════════════
   DATA COLLECTION
   ═══════════════════════════════════════════════════════════════ */

function collectData() {
  FORM_SECTIONS.forEach(section => {
    section.fields.forEach(field => {
      if (field.type === 'toggle-group') {
        field.toggles.forEach(t => {
          const el = document.getElementById(`f_${t.id}`);
          if (el) formState.data[t.id] = el.checked;
        });
      } else if (field.type === 'radio') {
        const anyRadio = document.querySelector(`input[name="${field.id}"]`);
        if (anyRadio) {
          const checked = document.querySelector(`input[name="${field.id}"]:checked`);
          if (checked) formState.data[field.id] = checked.value;
          else delete formState.data[field.id];
        }
      } else if (field.type === 'select') {
        const el = document.getElementById(`f_${field.id}`);
        if (el) {
          if (el.value) formState.data[field.id] = el.value;
          else delete formState.data[field.id];
        }
      } else if (field.type === 'number') {
        const el = document.getElementById(`f_${field.id}`);
        if (el) {
          if (el.value !== '') formState.data[field.id] = parseFloat(el.value);
          else delete formState.data[field.id];
        }
      }
    });
  });
  wireUpFieldCounts();
}

function buildPayload() {
  collectData();
  const payload = { ...formState.data };
  // Auto-compute BMI
  if (!payload.bmi && payload.height_cm && payload.weight_kg) {
    const h = payload.height_cm / 100;
    payload.bmi = parseFloat((payload.weight_kg / (h * h)).toFixed(2));
  }
  // Remove internal keys
  delete payload['_bmi'];
  return payload;
}

/* ═══════════════════════════════════════════════════════════════
   BMI LIVE CALCULATION
   ═══════════════════════════════════════════════════════════════ */

function wireUpBMI() {
  const hEl = document.getElementById('f_height_cm');
  const wEl = document.getElementById('f_weight_kg');
  if (hEl) hEl.addEventListener('input', updateBMI);
  if (wEl) wEl.addEventListener('input', updateBMI);
  updateBMI();
}

function updateBMI() {
  const hEl = document.getElementById('f_height_cm');
  const wEl = document.getElementById('f_weight_kg');
  const valEl = document.getElementById('bmi-val');
  const catEl = document.getElementById('bmi-cat');
  if (!hEl || !wEl || !valEl) return;

  const h = parseFloat(hEl.value);
  const w = parseFloat(wEl.value);

  if (h > 0 && w > 0) {
    const bmi = w / ((h / 100) ** 2);
    valEl.textContent = bmi.toFixed(1);
    formState.data._bmi_computed = parseFloat(bmi.toFixed(2));
    formState.data.bmi = formState.data._bmi_computed;
    let cat = '', cls = '';
    if      (bmi < 18.5) { cat='Underweight';  cls='underweight'; }
    else if (bmi < 25)   { cat='Normal weight'; cls='normal'; }
    else if (bmi < 30)   { cat='Overweight';   cls='overweight'; }
    else                 { cat='Obese';         cls='obese'; }
    catEl.textContent = cat;
    catEl.className = `bmi-cat ${cls}`;
  } else {
    valEl.textContent = '—';
    catEl.textContent = 'Enter height & weight';
    catEl.className = 'bmi-cat';
    delete formState.data.bmi;
    delete formState.data._bmi_computed;
  }
}

/* ═══════════════════════════════════════════════════════════════
   FIELD COUNT DISPLAY
   ═══════════════════════════════════════════════════════════════ */

function wireUpFieldCounts() {
  const count = Object.keys(formState.data).filter(k => !k.startsWith('_') && formState.data[k] !== undefined && formState.data[k] !== false).length;
  const el = document.getElementById('fields-filled-count');
  if (el) el.textContent = count;
}

/* ═══════════════════════════════════════════════════════════════
   CSV / EXCEL UPLOAD
   ═══════════════════════════════════════════════════════════════ */

function initUploadZone() {
  const zone    = document.getElementById('upload-zone');
  const input   = document.getElementById('file-input');
  const inner   = document.getElementById('upload-inner');
  const success = document.getElementById('upload-success');
  const nameEl  = document.getElementById('upload-filename');
  const clearBtn= document.getElementById('btn-upload-clear');

  if (!zone) return;

  // Drag and drop
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  });
  input.addEventListener('change', () => { if (input.files[0]) handleFile(input.files[0]); });
  clearBtn.addEventListener('click', () => {
    input.value = '';
    inner.classList.remove('hidden');
    success.classList.add('hidden');
  });

  function handleFile(file) {
    nameEl.textContent = file.name;
    inner.classList.add('hidden');
    success.classList.remove('hidden');

    const reader = new FileReader();
    reader.onload = e => {
      try {
        const wb   = XLSX.read(e.target.result, { type:'array' });
        const ws   = wb.Sheets[wb.SheetNames[0]];
        const rows = XLSX.utils.sheet_to_json(ws, { header:1 });

        if (!rows || rows.length < 2) { showUploadError('File appears empty or invalid.'); return; }

        // Support two formats:
        // Format A (key-value): col0=field_name, col1=value
        // Format B (header row): row0=headers, row1=values
        const firstCell = String(rows[0][0] || '').toLowerCase();
        let parsed = {};

        if (firstCell === 'field_name' || firstCell === 'field' || firstCell === 'name') {
          // Format A
          for (let i = 1; i < rows.length; i++) {
            const key = String(rows[i][0] || '').trim().toLowerCase();
            const val = rows[i][1];
            if (key && val !== '' && val !== undefined) {
              parsed[key] = isNaN(val) ? val : parseFloat(val);
            }
          }
        } else {
          // Format B — header row
          const headers = rows[0].map(h => String(h || '').trim().toLowerCase());
          const values  = rows[1] || [];
          headers.forEach((h, i) => {
            const val = values[i];
            if (h && val !== '' && val !== undefined) {
              parsed[h] = isNaN(val) ? val : parseFloat(val);
            }
          });
        }

        // Map to formState.data
        Object.entries(parsed).forEach(([k, v]) => {
          const mapped = CSV_FIELD_MAP[k] || k;
          if (v === 'true' || v === true)  formState.data[mapped] = true;
          else if (v === 'false' || v === false) formState.data[mapped] = false;
          else if (typeof v === 'number')  formState.data[mapped] = v;
          else if (typeof v === 'string' && v.trim() !== '') formState.data[mapped] = v.trim();
        });

        // Re-render form with filled values
        renderForm();
        showToast(`✓ ${file.name} loaded — ${Object.keys(parsed).length} fields imported`, 'success');
      } catch (err) {
        showUploadError('Could not parse file: ' + err.message);
      }
    };
    reader.readAsArrayBuffer(file);
  }
}

function showUploadError(msg) {
  showToast('⚠ ' + msg, 'error');
}

/* ═══════════════════════════════════════════════════════════════
   TEMPLATE DOWNLOAD
   ═══════════════════════════════════════════════════════════════ */

function downloadTemplate() {
  const mode = formState.mode;
  window.location.href = `/api/detection/template/${mode}`;
}

/* ═══════════════════════════════════════════════════════════════
   TOAST NOTIFICATIONS
   ═══════════════════════════════════════════════════════════════ */

function showToast(msg, type = 'info') {
  const existing = document.getElementById('toast-el');
  if (existing) existing.remove();

  const t = document.createElement('div');
  t.id = 'toast-el';
  t.style.cssText = `
    position:fixed;bottom:24px;right:24px;z-index:999;
    padding:12px 18px;border-radius:10px;font-size:13px;font-weight:600;
    background:${type==='success'?'rgba(16,185,129,.15)':'rgba(239,68,68,.15)'};
    border:1px solid ${type==='success'?'rgba(16,185,129,.3)':'rgba(239,68,68,.3)'};
    color:${type==='success'?'#34d399':'#fca5a5'};
    font-family:Inter,sans-serif;max-width:320px;
    animation:fadeIn .2s ease;box-shadow:0 8px 24px rgba(0,0,0,.4);
  `;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

window.showToast = showToast;
