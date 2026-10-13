/**
 * doctor.js — Physician Clinical Workspace Logic
 *
 * Connects the Doctor Dashboard directly to backend persistence:
 *  - Live KPI metrics and searchable review queue
 *  - In-depth patient inspection with 5 disease model breakdowns
 *  - Clinician notes, lab test orders, and care plan drafting/approval
 */
'use strict';

let currentQueue = [];
let currentAssessment = null;
let currentCarePlan = null;
let activeFilter = 'all';

// ── DOM Elements ──────────────────────────────────────────────────────────────
const queueTbody = document.getElementById('queue-tbody');
const queueSearch = document.getElementById('queue-search');
const filterTabs = document.getElementById('filter-tabs');
const inspectorEmpty = document.getElementById('inspector-empty');
const inspectorContent = document.getElementById('inspector-content');
const btnRefresh = document.getElementById('btn-refresh-queue');

// Modal Elements
const modalPlan = document.getElementById('modal-care-plan');
const btnClosePlan = document.getElementById('btn-close-plan-modal');
const btnCancelPlan = document.getElementById('btn-cancel-plan');
const btnPublishPlan = document.getElementById('btn-publish-plan');
const modalPlanBody = document.getElementById('modal-plan-body');

// ── Init & Lifecycle ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  initEventListeners();
  await loadQueue();

  // Check URL parameters for direct deep-linking
  const params = new URLSearchParams(window.location.search);
  const targetAssessmentId = params.get('assessmentId');
  if (targetAssessmentId) {
    await selectAssessment(targetAssessmentId);
  }
});

function initEventListeners() {
  if (btnRefresh) {
    btnRefresh.addEventListener('click', loadQueue);
  }

  if (queueSearch) {
    let debounce;
    queueSearch.addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(loadQueue, 300);
    });
  }

  if (filterTabs) {
    filterTabs.querySelectorAll('.filter-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        filterTabs.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        activeFilter = tab.dataset.filter;
        loadQueue();
      });
    });
  }

  if (btnClosePlan) btnClosePlan.addEventListener('click', closePlanModal);
  if (btnCancelPlan) btnCancelPlan.addEventListener('click', closePlanModal);
  if (btnPublishPlan) btnPublishPlan.addEventListener('click', publishCurrentCarePlan);
}

// ── Load Queue & KPIs ─────────────────────────────────────────────────────────
async function loadQueue() {
  try {
    const searchVal = queueSearch ? queueSearch.value.trim() : '';
    const res = await fetch(`/api/reviews/queue?status=${activeFilter}&search=${encodeURIComponent(searchVal)}`);
    if (!res.ok) throw new Error(`Queue API returned ${res.status}`);

    const data = await res.json();
    currentQueue = data.cases || [];
    updateKPIs(data.kpis || {});
    renderQueueTable(currentQueue);
  } catch (err) {
    console.error('Failed to load queue:', err);
    if (queueTbody) {
      queueTbody.innerHTML = `<tr><td colspan="5" class="error-td">⚠ Failed to load queue: ${escapeHtml(err.message)}</td></tr>`;
    }
  }
}

function updateKPIs(kpis) {
  const elPending = document.getElementById('kpi-pending');
  const elReviewed = document.getElementById('kpi-reviewed');
  const elPlans = document.getElementById('kpi-plans');
  const elPatients = document.getElementById('kpi-patients');
  const elCounter = document.getElementById('case-counter');

  if (elPending) elPending.textContent = kpis.pending_reviews ?? 0;
  if (elReviewed) elReviewed.textContent = kpis.reviewed_cases ?? 0;
  if (elPlans) elPlans.textContent = kpis.approved_care_plans ?? 0;
  if (elPatients) elPatients.textContent = kpis.total_patients ?? 0;
  if (elCounter) elCounter.textContent = `${currentQueue.length} Cases`;
}

function renderQueueTable(cases) {
  if (!queueTbody) return;

  if (cases.length === 0) {
    queueTbody.innerHTML = `<tr><td colspan="5" class="empty-td">No clinical cases found for current filter.</td></tr>`;
    return;
  }

  queueTbody.innerHTML = cases.map(c => {
    const isSelected = currentAssessment && currentAssessment.id === c.assessment_id;
    const dateStr = formatDate(c.assessment_date);
    const statusBadge = getStatusBadge(c.review_status, c.assessment_status);

    // Format risk badges
    const riskBadges = (c.high_risks || []).map(r => `<span class="tag-risk high">${escapeHtml(r.title)} (${r.pct}%)</span>`).concat(
      (c.mod_risks || []).map(r => `<span class="tag-risk mod">${escapeHtml(r.title)} (${r.pct}%)</span>`)
    ).join(' ') || '<span class="tag-risk low">Low Baseline</span>';

    return `
      <tr class="queue-row ${isSelected ? 'selected' : ''}" data-id="${escapeHtml(c.assessment_id)}" onclick="selectAssessment('${escapeHtml(c.assessment_id)}')">
        <td>
          <div class="patient-cell">
            <span class="patient-name">${escapeHtml(c.patient_name || 'Anonymous')}</span>
            <span class="patient-sub">${c.patient_age ? c.patient_age + ' yrs' : ''} ${c.patient_sex ? '· ' + capitalize(c.patient_sex) : ''} · <span class="patient-id">${escapeHtml(c.assessment_id)}</span></span>
          </div>
        </td>
        <td class="date-cell">${dateStr}</td>
        <td><div class="risk-tags-cell">${riskBadges}</div></td>
        <td>${statusBadge}</td>
        <td>
          <button class="btn btn-xs btn-outline" onclick="event.stopPropagation(); selectAssessment('${escapeHtml(c.assessment_id)}')">
            Inspect →
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

// ── Select and Inspect an Assessment ──────────────────────────────────────────
window.selectAssessment = async function(assessmentId) {
  try {
    // Highlight table row
    document.querySelectorAll('.queue-row').forEach(r => {
      r.classList.toggle('selected', r.dataset.id === assessmentId);
    });

    const res = await fetch(`/api/assessments/${assessmentId}`);
    if (!res.ok) throw new Error(`Could not load assessment ${assessmentId}`);

    currentAssessment = await res.json();
    renderInspector(currentAssessment);

    // Update browser URL query without reload
    const newUrl = `${window.location.pathname}?assessmentId=${encodeURIComponent(assessmentId)}`;
    window.history.replaceState({ path: newUrl }, '', newUrl);

  } catch (err) {
    alert(`Failed to load assessment details: ${err.message}`);
  }
};

function renderInspector(asm) {
  if (!inspectorEmpty || !inspectorContent) return;

  inspectorEmpty.classList.add('hidden');
  inspectorContent.classList.remove('hidden');

  const inputs = asm.inputs || {};
  const normalized = asm.normalized_inputs || inputs;
  const results = asm.disease_results || {};
  const review = asm.review || {};

  const reviewStatus = review.status || (asm.status === 'pending_review' ? 'pending' : asm.status);
  const statusBadge = getStatusBadge(reviewStatus);

  const diseaseKeys = ['diabetes', 'heart_disease', 'ckd', 'liver_disease', 'stroke'];

  inspectorContent.innerHTML = `
    <!-- Top Patient Header -->
    <div class="inspector-header">
      <div class="patient-hero">
        <div class="patient-avatar">👤</div>
        <div>
          <h2 class="patient-title">${escapeHtml(asm.patient_name || 'Patient')}</h2>
          <div class="patient-meta-row">
            <span>Age: <strong>${inputs.age ?? '—'}</strong></span>
            <span>Sex: <strong>${capitalize(inputs.sex ?? '—')}</strong></span>
            <span>BMI: <strong>${inputs.bmi ?? '—'} kg/m²</strong></span>
            <span>Assessment ID: <code>${escapeHtml(asm.id)}</code></span>
            <span>Data Completeness: <strong>${Math.round((asm.data_completeness || 0) * 100)}%</strong></span>
          </div>
        </div>
      </div>
      <div class="inspector-header-actions">
        ${statusBadge}
        <a href="/patient?patientId=${encodeURIComponent(asm.patient_id)}" target="_blank" class="btn btn-sm btn-outline">
          View Patient Dashboard ↗
        </a>
      </div>
    </div>

    <!-- ── Submitted Measurements Grid ──────────────────────────────── -->
    <div class="card-section">
      <h3 class="section-title">Submitted Patient Vitals &amp; Laboratory Biomarkers</h3>
      <div class="vitals-matrix">
        <div class="vital-item">
          <span class="vital-lbl">Blood Pressure</span>
          <span class="vital-val">${inputs.systolic_bp ? inputs.systolic_bp + '/' + (inputs.diastolic_bp || '—') + ' mmHg' : '—'}</span>
        </div>
        <div class="vital-item">
          <span class="vital-lbl">Fasting Glucose</span>
          <span class="vital-val">${inputs.fasting_glucose ? inputs.fasting_glucose + ' mg/dL' : (inputs.hba1c ? inputs.hba1c + '% (HbA1c)' : '—')}</span>
        </div>
        <div class="vital-item">
          <span class="vital-lbl">Total Cholesterol</span>
          <span class="vital-val">${inputs.total_cholesterol ? inputs.total_cholesterol + ' mg/dL' : '—'}</span>
        </div>
        <div class="vital-item">
          <span class="vital-lbl">Serum Creatinine</span>
          <span class="vital-val">${inputs.creatinine ? inputs.creatinine + ' mg/dL' : (inputs.egfr ? inputs.egfr + ' (eGFR)' : '—')}</span>
        </div>
        <div class="vital-item">
          <span class="vital-lbl">Liver Transaminases</span>
          <span class="vital-val">${inputs.alt ? 'ALT: ' + inputs.alt + ' U/L' : '—'} ${inputs.ast ? 'AST: ' + inputs.ast + ' U/L' : ''}</span>
        </div>
        <div class="vital-item">
          <span class="vital-lbl">Heart Rate</span>
          <span class="vital-val">${inputs.heart_rate ? inputs.heart_rate + ' bpm' : '—'}</span>
        </div>
      </div>
    </div>

    <!-- ── Five Disease ML Model Assessment Grid ────────────────────── -->
    <div class="card-section">
      <h3 class="section-title">Local Machine Learning Disease Risk Assessments</h3>
      <div class="disease-models-grid">
        ${diseaseKeys.map(k => renderDiseaseModelCard(k, results[k])).join('')}
      </div>
    </div>

    <!-- ── Clinician Actions & Notes ─────────────────────────────────── -->
    <div class="card-section decision-box">
      <h3 class="section-title">Physician Evaluation &amp; Orders</h3>

      <div class="form-group">
        <label for="doctor-notes-input">Clinician Assessment Notes &amp; Observations</label>
        <textarea id="doctor-notes-input" class="clinical-textarea" rows="3" placeholder="Enter clinical assessment notes, dietary cautions, or medication recommendations…">${escapeHtml(review.doctor_notes || '')}</textarea>
      </div>

      <div class="form-group">
        <label>Requested Diagnostic Follow-ups &amp; Laboratory Tests</label>
        <div class="test-chips" id="test-chips">
          ${renderTestChips(review.requested_tests || [])}
        </div>
      </div>

      <div class="decision-actions">
        <button class="btn btn-secondary" id="btn-save-notes" onclick="saveDoctorNotes()">
          💾 Save Notes &amp; Tests
        </button>
        <button class="btn btn-secondary" id="btn-request-followup" onclick="setFollowUpStatus()">
          🚩 Flag Follow-up Required
        </button>
        <button class="btn btn-primary" id="btn-open-plan-modal" onclick="openCarePlanModal()">
          📝 Draft / Approve Care Plan →
        </button>
      </div>
    </div>
  `;
}

function renderDiseaseModelCard(key, data) {
  if (!data) {
    return `<div class="model-eval-card empty"><h4>${capitalize(key)}</h4><p>Not evaluated</p></div>`;
  }

  const name = data.display_name || capitalize(key);
  const status = data.status || 'unknown';
  const icon = data.icon || '🩺';
  const pred = data.prediction || {};
  const prob = pred.probability;
  const pct = pred.percentage ?? (prob !== null && prob !== undefined ? Math.round(prob * 100) : null);
  const label = pred.label || 'unknown';
  const modelInfo = data.model || {};

  let statusClass = 'low';
  let badgeText = 'LOW RISK';
  if (status === 'insufficient_data') {
    statusClass = 'insufficient';
    badgeText = 'INSUFFICIENT DATA';
  } else if (label === 'high_risk' || (pct && pct >= 65)) {
    statusClass = 'high';
    badgeText = `HIGH RISK (${pct}%)`;
  } else if (label === 'moderate_risk' || (pct && pct >= 35)) {
    statusClass = 'mod';
    badgeText = `MODERATE (${pct}%)`;
  } else if (pct !== null) {
    badgeText = `LOW RISK (${pct}%)`;
  }

  const factors = data.explanation?.factors || [];
  const missing = data.missing_features || [];

  return `
    <div class="model-eval-card ${statusClass}">
      <div class="mec-head">
        <div class="mec-title">
          <span class="mec-icon">${icon}</span>
          <span class="mec-name">${escapeHtml(name)}</span>
        </div>
        <span class="mec-badge ${statusClass}">${badgeText}</span>
      </div>

      ${status === 'insufficient_data' ? `
        <div class="mec-insufficient-msg">
          <p>Assessment requires mandatory clinical markers: <strong>${escapeHtml(missing.join(', '))}</strong></p>
        </div>
      ` : `
        <div class="mec-meter">
          <div class="mec-meter-fill ${statusClass}" style="width: ${pct || 0}%"></div>
        </div>
        <div class="mec-model-meta">
          <span>Algo: <code>${escapeHtml(modelInfo.model_id || 'Pipeline')}</code></span>
          <span>AUC: <strong>${escapeHtml(modelInfo.version ? modelInfo.version.split('ROC-AUC: ')[1]?.replace(')', '') || 'Validated' : 'Validated')}</strong></span>
        </div>
        <div class="mec-factors">
          <span class="factors-lbl">Drivers:</span>
          ${factors.slice(0, 3).map(f => `<span class="factor-tag">${escapeHtml(f)}</span>`).join('') || '<span class="factor-tag">Normal baseline</span>'}
        </div>
      `}
    </div>
  `;
}

function renderTestChips(selectedTests) {
  const commonTests = [
    'Fasting Blood Glucose', 'HbA1c (Glycated Hb)', 'Lipid Profile (HDL/LDL)',
    'Serum Creatinine & eGFR', 'Urine Albumin (UACR)', 'Liver Panel (ALT/AST)',
    'Resting ECG', 'Echocardiogram'
  ];

  return commonTests.map(t => {
    const active = selectedTests.includes(t);
    return `
      <label class="test-chip ${active ? 'active' : ''}">
        <input type="checkbox" name="req_tests" value="${escapeHtml(t)}" ${active ? 'checked' : ''} onchange="this.parentElement.classList.toggle('active', this.checked)" />
        ${escapeHtml(t)}
      </label>
    `;
  }).join('');
}

// ── Save Doctor Notes & Tests ─────────────────────────────────────────────────
window.saveDoctorNotes = async function(statusOverride) {
  if (!currentAssessment) return;
  const notesInput = document.getElementById('doctor-notes-input');
  const notesText = notesInput ? notesInput.value.trim() : '';

  const checkedTests = Array.from(document.querySelectorAll('input[name="req_tests"]:checked')).map(el => el.value);
  const status = statusOverride || 'reviewed';

  try {
    const res = await fetch(`/api/reviews/${currentAssessment.id}/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        status: status,
        doctor_notes: notesText,
        requested_tests: checkedTests,
        doctor_name: 'Dr. Sarah Mitchell, MD'
      })
    });

    if (!res.ok) throw new Error(`Save failed (${res.status})`);
    const updated = await res.json();
    alert('✓ Clinical notes & orders successfully saved.');
    await loadQueue();
    await selectAssessment(currentAssessment.id);
  } catch (err) {
    alert(`Failed to save doctor review: ${err.message}`);
  }
};

window.setFollowUpStatus = function() {
  saveDoctorNotes('follow_up_required');
};

// ── Care Plan Drafting & Approval ─────────────────────────────────────────────
window.openCarePlanModal = async function() {
  if (!currentAssessment) return;
  if (!modalPlan || !modalPlanBody) return;

  modalPlan.classList.remove('hidden');
  modalPlanBody.innerHTML = `
    <div class="plan-loading">
      <div class="loading-spinner-ring"></div>
      <p style="margin-top:12px; color:#64748b;">Generating evidence-based Clinical Decision Support plan…</p>
    </div>
  `;

  try {
    const notesInput = document.getElementById('doctor-notes-input');
    const notesText = notesInput ? notesInput.value.trim() : '';

    const res = await fetch('/api/care-plans/draft', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        assessment_id: currentAssessment.id,
        doctor_comments: notesText,
        provider: 'local'
      })
    });

    if (!res.ok) throw new Error(`Plan draft API error (${res.status})`);
    currentCarePlan = await res.json();
    renderCarePlanModalBody(currentCarePlan);

  } catch (err) {
    modalPlanBody.innerHTML = `<div class="error-box">⚠ Failed to generate care plan draft: ${escapeHtml(err.message)}</div>`;
  }
};

function renderCarePlanModalBody(plan) {
  if (!modalPlanBody) return;

  const diet = plan.diet || {};
  const exercise = plan.exercise || {};
  const schedule = plan.schedule || [];

  modalPlanBody.innerHTML = `
    <div class="cplan-editor">
      <div class="cplan-status-alert">
        <span>⚠ Status: <strong>DRAFT (Unpublished)</strong></span>
        <span>Review recommendations below. Clicking Approve will immediately publish this plan to the patient dashboard.</span>
      </div>

      <!-- Diet Guidelines -->
      <div class="plan-section">
        <h4>1. Nutritional &amp; Dietary Guidelines</h4>
        <div class="diet-editor-grid">
          <div>
            <label class="lbl-sm">Recommended Foods</label>
            <textarea id="edit-diet-eat" class="cplan-field" rows="3">${escapeHtml((diet.foods_to_eat || []).map(f => typeof f === 'object' ? f.name : f).join('\n'))}</textarea>
          </div>
          <div>
            <label class="lbl-sm">Foods to Avoid</label>
            <textarea id="edit-diet-avoid" class="cplan-field" rows="3">${escapeHtml((diet.foods_to_avoid || []).map(f => typeof f === 'object' ? f.name : f).join('\n'))}</textarea>
          </div>
        </div>
      </div>

      <!-- Exercise Protocol -->
      <div class="plan-section">
        <h4>2. Physical Activity &amp; Exercise Regimen</h4>
        <input type="text" id="edit-exercise-proto" class="cplan-field" value="${escapeHtml(exercise.regimen_name || exercise.protocol || '30-minute daily moderate aerobic walking')}" />
      </div>

      <!-- 24-Hour Schedule -->
      <div class="plan-section">
        <h4>3. Daily Chronotherapy &amp; Routine Schedule</h4>
        <div class="schedule-editor-list" id="schedule-editor-list">
          ${schedule.map((s, idx) => `
            <div class="schedule-edit-row">
              <span class="sched-time">${escapeHtml(s.time || 'Routine')}</span>
              <span class="sched-period">[${escapeHtml(s.period || 'Day')}]</span>
              <input type="text" class="cplan-field sched-input" data-idx="${idx}" value="${escapeHtml(s.task || '')}" />
            </div>
          `).join('')}
        </div>
      </div>

      <!-- Doctor Signed Instructions -->
      <div class="plan-section">
        <h4>4. Physician Instructions for Patient</h4>
        <textarea id="edit-doctor-comments" class="cplan-field" rows="2" placeholder="Signed physician instructions…">${escapeHtml(plan.doctor_comments || '')}</textarea>
      </div>
    </div>
  `;
}

function closePlanModal() {
  if (modalPlan) modalPlan.classList.add('hidden');
}

async function publishCurrentCarePlan() {
  if (!currentCarePlan) return;

  // Gather edits
  const eatLines = (document.getElementById('edit-diet-eat')?.value || '').split('\n').filter(Boolean);
  const avoidLines = (document.getElementById('edit-diet-avoid')?.value || '').split('\n').filter(Boolean);
  const proto = document.getElementById('edit-exercise-proto')?.value || '';
  const doctorComments = document.getElementById('edit-doctor-comments')?.value || '';

  const scheduleInputs = document.querySelectorAll('.sched-input');
  const updatedSchedule = [...(currentCarePlan.schedule || [])];
  scheduleInputs.forEach(input => {
    const idx = parseInt(input.dataset.idx, 10);
    if (updatedSchedule[idx]) {
      updatedSchedule[idx].task = input.value;
    }
  });

  try {
    // 1. Update draft
    await fetch(`/api/care-plans/${currentCarePlan.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        diet: { foods_to_eat: eatLines, foods_to_avoid: avoidLines },
        exercise: { protocol: proto },
        schedule: updatedSchedule,
        doctor_comments: doctorComments
      })
    });

    // 2. Approve and Publish
    const approveRes = await fetch(`/api/care-plans/${currentCarePlan.id}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved_by: 'Dr. Sarah Mitchell, MD' })
    });

    if (!approveRes.ok) throw new Error(`Approval failed (${approveRes.status})`);

    alert('✓ Care plan approved and published! The patient can now view their daily action plan on /patient.');
    closePlanModal();
    await loadQueue();
    if (currentAssessment) await selectAssessment(currentAssessment.id);

  } catch (err) {
    alert(`Failed to approve care plan: ${err.message}`);
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function getStatusBadge(reviewStatus, asmStatus) {
  const s = (reviewStatus || asmStatus || 'pending').toLowerCase();
  if (s === 'reviewed' || s === 'care_plan_approved') {
    return `<span class="badge badge-reviewed">✓ Reviewed</span>`;
  }
  if (s === 'follow_up_required') {
    return `<span class="badge badge-followup">🚩 Follow-up Req</span>`;
  }
  return `<span class="badge badge-pending">⏳ Pending Review</span>`;
}

function formatDate(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return iso;
  }
}

function capitalize(s) {
  if (!s) return '';
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
