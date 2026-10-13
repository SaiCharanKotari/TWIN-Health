/**
 * app.js — TwinHealth AI Application Router & State Manager
 *
 * Manages:
 *  - Screen transitions (input → loading → results)
 *  - Tab switching (Basic / Advanced)
 *  - Input method switching (form / upload)
 *  - API call to /api/detection/analyze
 *  - Error handling with user-friendly messages
 *  - Health check → provider badge
 */
'use strict';

/* ═══════════════════════════════════════════════════════════════
   SCREEN MANAGEMENT
   ═══════════════════════════════════════════════════════════════ */

const SCREENS = ['screen-input', 'screen-loading', 'screen-results', 'screen-plan'];

window.showScreen = function(name) {
  SCREENS.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('active', id === `screen-${name}`);
  });
  window.scrollTo({ top: 0, behavior: 'smooth' });
};

/* ═══════════════════════════════════════════════════════════════
   LOADING ANIMATION
   ═══════════════════════════════════════════════════════════════ */

const DISEASE_META = [
  { key:'diabetes',      icon:'🩺', name:'Diabetes' },
  { key:'heart_disease', icon:'❤️', name:'Heart Disease' },
  { key:'ckd',           icon:'🫘', name:'CKD' },
  { key:'liver_disease', icon:'🟤', name:'Liver Disease' },
  { key:'stroke',        icon:'🧠', name:'Stroke Risk' },
];

const LOADING_MSGS = [
  'Validating patient data…',
  'Running Diabetes model…',
  'Running Heart Disease model…',
  'Running CKD assessment…',
  'Running Liver Disease model…',
  'Running Stroke Risk model…',
  'Normalising results…',
  'Preparing dashboard…',
];

function renderLoadingCards() {
  const grid = document.getElementById('loading-disease-grid');
  grid.innerHTML = DISEASE_META.map(d => `
    <div class="loading-card">
      <span class="lc-icon">${d.icon}</span>
      <span class="lc-name">${d.name}</span>
      <div class="lc-bar"><div class="lc-bar-inner"></div></div>
    </div>`).join('');
}

function cycleLoadingMessages() {
  const el  = document.getElementById('loading-sub');
  let   idx = 0;
  return setInterval(() => {
    if (el) el.textContent = LOADING_MSGS[idx % LOADING_MSGS.length];
    idx++;
  }, 900);
}

/* ═══════════════════════════════════════════════════════════════
   TABS & INPUT METHOD
   ═══════════════════════════════════════════════════════════════ */

function initTabs() {
  document.querySelectorAll('.mode-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      formState.mode = tab.dataset.mode;
      renderForm(formState.highlightFields || []);
    });
  });
}

function initMethodToggle() {
  document.querySelectorAll('.method-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.method-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      formState.inputMethod = btn.dataset.method;

      const uploadZone     = document.getElementById('upload-zone');
      const formContainer  = document.getElementById('form-container');
      const isUpload       = formState.inputMethod === 'upload';

      uploadZone.classList.toggle('hidden', !isUpload);
      formContainer.style.opacity = isUpload ? '0.4' : '1';
      formContainer.style.pointerEvents = isUpload ? 'none' : 'auto';
    });
  });
}

/* ═══════════════════════════════════════════════════════════════
   FORM SUBMIT → ANALYSIS
   ═══════════════════════════════════════════════════════════════ */

function initAnalyzeButton() {
  document.getElementById('btn-analyze').addEventListener('click', async () => {
    const payload = buildPayload();

    // Quick validation: need at least age OR some data
    const hasData = Object.keys(payload).length > 0;
    if (!hasData) {
      showToast('⚠ Please fill in at least a few fields before running detection.', 'error');
      return;
    }

    showScreen('loading');
    renderLoadingCards();
    const msgInterval = cycleLoadingMessages();

    try {
      const provider = document.getElementById('engine-select').value;
      const res = await fetch(`/api/detection/analyze?provider=${provider}`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ ...payload }),
      });

      clearInterval(msgInterval);

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail?.message || `Server error (${res.status})`);
      }

      const data = await res.json();
      saveToHistory(payload, data);
      showScreen('results');
      renderResults(data);

    } catch (err) {
      clearInterval(msgInterval);
      showScreen('input');
      showToast(`⚠ ${err.message}`, 'error');
    }
  });
}

/* ═══════════════════════════════════════════════════════════════
   NEW ASSESSMENT BUTTON
   ═══════════════════════════════════════════════════════════════ */

function initNewButton() {
  document.getElementById('btn-new').addEventListener('click', () => {
    showScreen('input');
    // Clear results but keep form data for editing
  });
}

/* ═══════════════════════════════════════════════════════════════
   DOWNLOAD TEMPLATE
   ═══════════════════════════════════════════════════════════════ */

function initDownloadTemplate() {
  document.getElementById('btn-download-template').addEventListener('click', downloadTemplate);
}

/* ═══════════════════════════════════════════════════════════════
   HEALTH CHECK → PROVIDER BADGE
   ═══════════════════════════════════════════════════════════════ */

async function initHealthBadge() {
  const badge = document.getElementById('provider-badge');
  if (!badge) return;
  try {
    const res  = await fetch('/health');
    const data = await res.json();
    const prov = data.default_provider || 'unknown';
    const key  = data.gemini_key_set;
    if (prov === 'gemini' && key) {
      badge.textContent = '✓ Gemini AI';
      badge.style.borderColor = 'rgba(16,185,129,.35)';
      badge.style.color = '#10b981';
      badge.style.background = 'rgba(16,185,129,.08)';
    } else if (prov === 'mock') {
      badge.textContent = '⚙ Demo Mode (mock)';
      badge.style.borderColor = 'rgba(245,158,11,.35)';
      badge.style.color = '#d97706';
      badge.style.background = 'rgba(245,158,11,.08)';
    } else {
      badge.textContent = `✦ ${prov}`;
      badge.style.color = '#0d9488';
      badge.style.background = 'rgba(13,148,136,.08)';
      badge.style.borderColor = 'rgba(13,148,136,.3)';
    }
    badge.style.display = 'inline-flex';
  } catch {
    /* silently hide badge if API health check fails */
  }
}

/* ═══════════════════════════════════════════════════════════════
   INIT
   ═══════════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {
  // Render initial form (basic mode)
  renderForm([]);

  // Wire up interactivity
  initTabs();
  initMethodToggle();
  initUploadZone();
  initAnalyzeButton();
  initNewButton();
  initDownloadTemplate();
  initHealthBadge();

  // Initialize history sidebar
  renderHistorySidebar();
  const clearBtn = document.getElementById('btn-clear-history');
  if (clearBtn) {
    clearBtn.addEventListener('click', clearHistory);
  }
  const toggleBtn = document.getElementById('btn-toggle-history');
  const sidebar = document.getElementById('history-sidebar');
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('open');
    });
  }

  // Default: show input screen
  showScreen('input');
});

/* ═══════════════════════════════════════════════════════════════
   LOCAL ASSESSMENT HISTORY
   ═══════════════════════════════════════════════════════════════ */

function getHistory() {
  try {
    return JSON.parse(localStorage.getItem('twinhealth_history') || '[]');
  } catch {
    return [];
  }
}

function saveToHistory(payload, data) {
  const history = getHistory();
  const newItem = {
    id: Date.now().toString(),
    timestamp: new Date().toISOString(),
    input_payload: payload,
    results: data
  };
  history.unshift(newItem);
  if (history.length > 50) history.pop();
  localStorage.setItem('twinhealth_history', JSON.stringify(history));
  renderHistorySidebar();
}

function clearHistory() {
  if (confirm("Are you sure you want to clear your assessment history?")) {
    localStorage.removeItem('twinhealth_history');
    renderHistorySidebar();
    showScreen('input');
  }
}

function renderHistorySidebar() {
  const container = document.getElementById('history-list');
  if (!container) return;

  const history = getHistory();
  if (history.length === 0) {
    container.innerHTML = '<div class="history-empty">No previous assessments</div>';
    return;
  }

  container.innerHTML = history.map(item => {
    const date = new Date(item.timestamp);
    const dateStr = date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ', ' + date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    
    const age = item.input_payload.age || '—';
    const sex = item.input_payload.sex || '—';
    const patientStr = `${age} yrs, ${sex.charAt(0).toUpperCase() + sex.slice(1)}`;
    
    let worstRisk = 'low';
    let worstRiskLabel = 'Low Risk';
    
    if (item.results && item.results.results) {
      Object.values(item.results.results).forEach(r => {
        if (r.status === 'success' || r.status === 'preliminary') {
          const lbl = r.prediction?.label;
          if (lbl === 'high_risk') {
            worstRisk = 'high';
            worstRiskLabel = 'High Risk';
          } else if (lbl === 'moderate_risk' && worstRisk !== 'high') {
            worstRisk = 'moderate';
            worstRiskLabel = 'Mod Risk';
          }
        }
      });
    }

    const providerName = getHistoryProviderName(item.results?.results || {});

    return `
      <div class="history-item" data-id="${item.id}">
        <div class="hi-top">
          <span class="hi-date">${dateStr}</span>
          <span class="hi-provider">${providerName}</span>
        </div>
        <div class="hi-patient">${patientStr}</div>
        <div class="hi-summary-row">
          <span class="hi-disease-badge ${worstRisk}">${worstRiskLabel}</span>
        </div>
      </div>
    `;
  }).join('');

  container.querySelectorAll('.history-item').forEach(el => {
    el.addEventListener('click', () => {
      const id = el.dataset.id;
      loadHistoryItem(id);
    });
  });
}

function getHistoryProviderName(results) {
  for (const r of Object.values(results)) {
    const p = r.model?.provider;
    if (p && p !== 'mock') return p.charAt(0).toUpperCase() + p.slice(1);
    if (p === 'mock') return 'Demo';
  }
  return 'AI';
}

function loadHistoryItem(id) {
  const history = getHistory();
  const item = history.find(x => x.id === id);
  if (!item) return;

  document.querySelectorAll('.history-item').forEach(el => {
    el.classList.toggle('active', el.dataset.id === id);
  });

  window.formState.data = { ...item.input_payload };
  if (window.renderForm) {
    window.renderForm([]);
  }

  if (window.renderResults) {
    window.renderResults(item.results);
  }

  window.showScreen('results');
}
