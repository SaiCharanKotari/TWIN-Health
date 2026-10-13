/**
 * patient.js — Patient Lifestyle & Chronotherapy Companion Controller
 *
 * Connects the Patient Companion to local JSON persistence:
 *  - Email identity resolution (sessionStorage / URL params)
 *  - Date-aware chronotherapy checklist with instant toggle synchronization
 *  - Daily and weekly adherence calculation
 *  - Dynamic empty state handling if care plan is not yet assigned
 */
'use strict';

let currentPatientEmail = 'robert.chen@example.com';
let currentDate = new Date().toISOString().split('T')[0];
let currentCarePlanId = null;
let currentActiveView = 'daily';

document.addEventListener('DOMContentLoaded', async () => {
  resolvePatientIdentity();
  updateDateLabel();
  await loadPatientDashboard();
});

function resolvePatientIdentity() {
  const urlParams = new URLSearchParams(window.location.search);
  const qEmail = urlParams.get('email') || urlParams.get('patientEmail');

  if (qEmail) {
    currentPatientEmail = qEmail.trim().toLowerCase();
  } else {
    const stored = sessionStorage.getItem('twinhealth_user');
    if (stored) {
      try {
        const u = JSON.parse(stored);
        if (u.email) currentPatientEmail = u.email.trim().toLowerCase();
      } catch {}
    }
  }

  const navEmail = document.getElementById('nav-user-email');
  if (navEmail) navEmail.textContent = `Account: ${currentPatientEmail}`;
  const metaEmail = document.getElementById('patient-meta-email');
  if (metaEmail) metaEmail.textContent = currentPatientEmail;
}

function logoutPatient() {
  sessionStorage.removeItem('twinhealth_user');
  window.location.href = '/login?role=patient';
}

function switchView(view) {
  currentActiveView = view;
  document.getElementById('tab-view-daily').classList.toggle('active', view === 'daily');
  document.getElementById('tab-view-weekly').classList.toggle('active', view === 'weekly');
  document.getElementById('view-daily-content').style.display = view === 'daily' ? 'block' : 'none';
  document.getElementById('view-weekly-content').style.display = view === 'weekly' ? 'block' : 'none';

  if (view === 'weekly') {
    loadWeeklyProgress();
  }
}

function shiftDay(delta) {
  const d = new Date(currentDate);
  d.setDate(d.getDate() + delta);
  currentDate = d.toISOString().split('T')[0];
  updateDateLabel();
  loadDailyProgress();
}

function goToToday() {
  currentDate = new Date().toISOString().split('T')[0];
  updateDateLabel();
  loadDailyProgress();
}

function updateDateLabel() {
  const todayStr = new Date().toISOString().split('T')[0];
  const heading = document.getElementById('current-day-heading');
  if (!heading) return;

  if (currentDate === todayStr) {
    heading.textContent = `Today (${currentDate})`;
  } else {
    const d = new Date(currentDate);
    const dayName = d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
    heading.textContent = `${dayName} (${currentDate})`;
  }
}

async function loadPatientDashboard() {
  await Promise.all([
    loadDailyProgress(),
    loadPatientMedications()
  ]);
}

async function loadPatientMedications() {
  const actionsEl = document.getElementById('patient-medication-actions');
  if (!actionsEl) return;

  try {
    const res = await fetch(`/api/patients/${encodeURIComponent(currentPatientEmail)}/medications`);
    if (!res.ok) {
      actionsEl.innerHTML = `<span style="font-size:13px; color:#71717a; font-style:italic;">No prescription file on record</span>`;
      return;
    }

    const data = await res.json();
    if (data.has_medication && data.medication) {
      const med = data.medication;
      actionsEl.innerHTML = `
        <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
          <span style="font-size:13px; font-weight:600; color:#000000;">📄 ${escapeHtml(med.filename)}</span>
          <a href="${escapeHtml(med.download_url)}" download class="btn" style="background:#000000; color:#ffffff; padding:8px 16px; border-radius:8px; font-size:13px; font-weight:700; text-decoration:none; display:inline-flex; align-items:center; gap:6px; cursor:pointer;">
            <span>📥</span> Download Prescription File
          </a>
        </div>
      `;
    } else {
      actionsEl.innerHTML = `
        <span style="font-size:13px; color:#71717a; font-style:italic;">No medication file uploaded yet</span>
      `;
    }
  } catch (err) {
    actionsEl.innerHTML = `<span style="font-size:13px; color:#71717a;">Could not check medications.</span>`;
  }
}

async function loadDailyProgress() {
  const root = document.getElementById('checklist-tasks-root');
  const emptyView = document.getElementById('empty-plan-view');
  const dailyView = document.getElementById('view-daily-content');

  try {
    const res = await fetch(`/api/activity/patient/${encodeURIComponent(currentPatientEmail)}?date=${encodeURIComponent(currentDate)}`);
    if (!res.ok) throw new Error(`API error ${res.status}`);
    const data = await res.json();

    currentCarePlanId = data.care_plan_id;

    // Check if care plan exists
    if (!data.care_plan_id || data.care_plan_status === 'none') {
      if (emptyView) emptyView.style.display = 'block';
      if (dailyView) dailyView.style.display = 'none';
      return;
    } else {
      if (emptyView) emptyView.style.display = 'none';
      if (dailyView) dailyView.style.display = currentActiveView === 'daily' ? 'block' : 'none';
    }

    // Populate Hero Metadata
    const nameEl = document.getElementById('patient-display-name');
    if (nameEl) nameEl.textContent = `Welcome back, ${data.patient_name || currentPatientEmail.split('@')[0].toUpperCase()}`;

    const planStatusEl = document.getElementById('patient-plan-status');
    if (planStatusEl) {
      if (data.care_plan_status === 'approved') {
        planStatusEl.textContent = 'Doctor Approved ✓';
        planStatusEl.style.color = '#0d9488';
      } else {
        planStatusEl.textContent = 'Clinical Draft (Pending Final Review)';
        planStatusEl.style.color = '#b45309';
      }
    }

    const docEl = document.getElementById('doctor-attending-name');
    if (docEl && data.approved_by) {
      docEl.textContent = data.approved_by;
    }

    // Doctor Comments
    const docCard = document.getElementById('doctor-notes-card');
    const docText = document.getElementById('doctor-notes-text');
    if (data.doctor_comments) {
      if (docCard) docCard.style.display = 'block';
      if (docText) docText.textContent = `"${data.doctor_comments}"`;
    } else if (docCard) {
      docCard.style.display = 'none';
    }

    // Update Adherence Progress Bar
    const pct = data.completion_percentage || 0;
    const pctBadge = document.getElementById('adherence-pct-val');
    const fillBar = document.getElementById('adherence-fill-bar');
    const countText = document.getElementById('adherence-count-text');

    if (pctBadge) pctBadge.textContent = `${pct}%`;
    if (fillBar) fillBar.style.width = `${pct}%`;
    if (countText) countText.textContent = `${data.completed_tasks || 0} of ${data.total_tasks || 0} activities completed`;

    // Render Chronotherapy Tasks Grouped by Period
    const tasks = data.tasks || [];
    if (tasks.length === 0) {
      root.innerHTML = `<div style="text-align:center; padding:24px; color:#64748b;">No activities scheduled for this date.</div>`;
      return;
    }

    const groups = {};
    tasks.forEach(t => {
      const p = t.period || 'General';
      if (!groups[p]) groups[p] = [];
      groups[p].push(t);
    });

    const periodsOrder = ['Early Morning', 'Morning', 'Mid-Morning', 'Afternoon', 'Evening', 'Dinner', 'Night', 'Bedtime'];
    const sortedKeys = Object.keys(groups).sort((a, b) => {
      let ia = periodsOrder.indexOf(a);
      let ib = periodsOrder.indexOf(b);
      if (ia === -1) ia = 99;
      if (ib === -1) ib = 99;
      return ia - ib;
    });

    let html = '';
    sortedKeys.forEach(period => {
      const pTasks = groups[period];
      html += `
        <div class="period-section">
          <div class="period-title">
            <span>⏰</span>
            <span>${escapeHtml(period)}</span>
          </div>
          ${pTasks.map(task => `
            <div class="task-item ${task.completed ? 'completed' : ''}" id="task-box-${escapeHtml(task.task_id)}">
              <input 
                type="checkbox" 
                class="task-checkbox-input" 
                id="check-${escapeHtml(task.task_id)}" 
                ${task.completed ? 'checked' : ''} 
                onchange="toggleTask('${escapeHtml(task.task_id)}', '${escapeHtml(task.category)}', '${escapeHtml(task.title)}', this.checked)"
              />
              <div class="task-details">
                <div>
                  <span class="task-time-badge">${escapeHtml(task.time || 'Daily')}</span>
                  <span class="task-cat-badge">${escapeHtml(task.category || 'General')}</span>
                </div>
                <div class="task-label-text">${escapeHtml(task.title)}</div>
                <p class="task-sub-text">${escapeHtml(task.description)}</p>
              </div>
            </div>
          `).join('')}
        </div>
      `;
    });

    root.innerHTML = html;

  } catch (err) {
    console.error('Error fetching patient progress:', err);
    if (root) {
      root.innerHTML = `<div style="color:#b91c1c; text-align:center; padding:24px;">Failed to load daily routine: ${escapeHtml(err.message)}</div>`;
    }
  }
}

window.toggleTask = async function(taskId, category, title, isChecked) {
  if (!currentCarePlanId) {
    alert('No active care plan to record progress against.');
    return;
  }

  // Optimistic UI toggle
  const box = document.getElementById(`task-box-${taskId}`);
  if (box) box.classList.toggle('completed', isChecked);

  try {
    const res = await fetch('/api/activity/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        patient_email: currentPatientEmail,
        care_plan_id: currentCarePlanId,
        task_id: taskId,
        calendar_date: currentDate,
        completed: isChecked,
        category: category,
        title: title
      })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error (${res.status})`);
    }

    const data = await res.json();
    const dailyProg = data.daily_progress || {};

    // Update adherence progress bar accurately
    const pct = dailyProg.completion_percentage || 0;
    const pctBadge = document.getElementById('adherence-pct-val');
    const fillBar = document.getElementById('adherence-fill-bar');
    const countText = document.getElementById('adherence-count-text');

    if (pctBadge) pctBadge.textContent = `${pct}%`;
    if (fillBar) fillBar.style.width = `${pct}%`;
    if (countText) countText.textContent = `${dailyProg.completed_tasks || 0} of ${dailyProg.total_tasks || 0} activities completed`;

  } catch (err) {
    alert(`Failed to save task status: ${err.message}`);
    // Rollback checkbox on error
    if (box) box.classList.toggle('completed', !isChecked);
    const cb = document.getElementById(`check-${taskId}`);
    if (cb) cb.checked = !isChecked;
  }
};

async function loadWeeklyProgress() {
  const root = document.getElementById('weekly-matrix-root');
  if (!root) return;

  try {
    const res = await fetch(`/api/activity/patient/${encodeURIComponent(currentPatientEmail)}/weekly?reference_date=${encodeURIComponent(currentDate)}`);
    if (!res.ok) throw new Error(`Weekly API error ${res.status}`);
    const data = await res.json();

    const days = data.days || [];
    if (days.length === 0) {
      root.innerHTML = `<div style="text-align:center; padding:24px; color:#64748b;">No weekly adherence records found.</div>`;
      return;
    }

    let html = `
      <div style="margin-bottom:16px; font-size:13px; color:#64748b;">
        Tracking week of <strong>${escapeHtml(data.week_start)}</strong> to <strong>${escapeHtml(data.week_end)}</strong> · Weekly Adherence: <strong style="color:#0d9488;">${data.weekly_completion_percentage}%</strong>
      </div>
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); gap:12px; margin-bottom:24px;">
        ${days.map(d => `
          <div style="background:${d.is_today ? '#f0fdfa' : '#f8fafc'}; border:1px solid ${d.is_today ? '#99f6e4' : '#e2e8f0'}; border-radius:10px; padding:14px; text-align:center;">
            <div style="font-size:12px; font-weight:700; color:${d.is_today ? '#0d9488' : '#475569'}; text-transform:uppercase;">${escapeHtml(d.day_name.slice(0, 3))}</div>
            <div style="font-size:11px; color:#94a3b8; margin-bottom:8px;">${escapeHtml(d.date.slice(5))}</div>
            <div style="font-size:18px; font-weight:800; color:#0f172a;">${d.percentage}%</div>
            <div style="font-size:11px; color:#64748b;">${d.completed_tasks}/${d.total_tasks} tasks</div>
          </div>
        `).join('')}
      </div>
    `;

    root.innerHTML = html;
  } catch (err) {
    root.innerHTML = `<div style="color:#b91c1c; padding:16px;">Failed to load weekly progress: ${escapeHtml(err.message)}</div>`;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>"']/g, m => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[m]);
}
