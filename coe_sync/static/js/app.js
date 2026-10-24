/**
 * COE SYNC 2026 - Global Shell & Impersonator Logic (app.js)
 * Manages sticky top bar "View As" selector, health badge, and permission toggling.
 */

window.CURRENT_ROLE = "CHAIR";

document.addEventListener("DOMContentLoaded", () => {
  initHealthCheck();
  initViewAsSelector();
  initSeedButton();
});

// -------------------------------------------------------------
// Toast Notifications
// -------------------------------------------------------------
window.showToast = function (message, isError = false) {
  let toast = document.getElementById("app-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "app-toast";
    toast.className = "toast-msg";
    document.body.appendChild(toast);
  }
  toast.innerHTML = `
    <span style="color: ${isError ? "#EF4444" : "#10B981"}; font-weight: bold;">
      ${isError ? "✕" : "✓"}
    </span>
    <span>${escapeHtml(message)}</span>
  `;
  toast.classList.add("show");
  setTimeout(() => {
    toast.classList.remove("show");
  }, 3500);
};

// -------------------------------------------------------------
// Health Check
// -------------------------------------------------------------
async function initHealthCheck() {
  const statusElem = document.getElementById("health-text");
  const badgeElem = document.getElementById("health-badge");
  if (!statusElem || !badgeElem) return;

  try {
    const res = await API.getHealth();
    if (res.status === "ok") {
      statusElem.textContent = `${res.app} | Online`;
      badgeElem.style.display = "inline-flex";
    }
  } catch (err) {
    statusElem.textContent = "Offline (Check DB)";
    badgeElem.style.borderColor = "#EF4444";
    badgeElem.style.color = "#DC2626";
    const pulse = badgeElem.querySelector(".health-pulse");
    if (pulse) pulse.style.backgroundColor = "#EF4444";
  }
}

// -------------------------------------------------------------
// Sticky "View As" Role Impersonator Selector
// -------------------------------------------------------------
async function initViewAsSelector() {
  const selector = document.getElementById("view-as-select");
  if (!selector) return;

  // Retrieve existing session role
  try {
    const sessionInfo = await API.getCurrentSession();
    if (sessionInfo) {
      window.AUTHENTIC_USER_ROLE = sessionInfo.role;
      if (sessionInfo.role !== "CHAIR" && sessionInfo.role !== "ADMIN") {
        const container = document.getElementById("view-as-container");
        if (container) container.remove();
        applyRolePermissions(sessionInfo.active_role || sessionInfo.role);
        return;
      }
      if (sessionInfo.active_role) {
        window.CURRENT_ROLE = sessionInfo.active_role;
        selector.value = sessionInfo.active_role;
        applyRolePermissions(sessionInfo.active_role);
      }
    }
  } catch (e) {
    console.warn("Could not fetch session info:", e);
  }

  selector.addEventListener("change", async (e) => {
    const chosenRole = e.target.value;
    try {
      const result = await API.impersonate(chosenRole);
      window.CURRENT_ROLE = chosenRole;
      applyRolePermissions(chosenRole);
      showToast(result.message || `Switched view to ${chosenRole}`);

      // Update Chair status visibility and reschedules for new role
      await updateChairStatusUI();
      await updateReschedulesBadge();

      // Dispatch event so individual page views (manage, dashboard, schedules) can refresh
      window.dispatchEvent(new CustomEvent("roleChanged", { detail: { role: chosenRole } }));
    } catch (err) {
      showToast(err.message || "Failed to switch role", true);
    }
  });
}

/**
 * Apply role-based UI restrictions (Hide Add/Edit/Delete buttons when not CHAIR or ADMIN)
 */
window.applyRolePermissions = function (role) {
  const isAdminOrChair = role === "CHAIR" || role === "ADMIN";
  const isStudent = role === "STUDENT";
  const isFaculty = role === "FACULTY";

  // Admin/Chair only mutation controls
  const adminElements = document.querySelectorAll(".admin-only");
  adminElements.forEach((el) => {
    if (isAdminOrChair) {
      el.style.display = el.dataset.display || "";
    } else {
      if (!el.dataset.display) el.dataset.display = window.getComputedStyle(el).display;
      el.style.display = "none";
    }
  });

  // Strict Student View Simplification:
  // For STUDENT users, hide Dashboard, Rooms, Faculty, Sections, Subjects, Conflict Radar, and Reports.
  // The student sidebar must strictly display: Brand, Schedules, Settings, Logout.
  const nonStudentElements = document.querySelectorAll(
    ".non-student, #nav-dashboard, #nav-reports, #nav-conflict-radar, #btn-conflict-radar, #nav-rooms, #nav-faculty, #nav-sections, #nav-subjects, a[href^='/manage']"
  );
  nonStudentElements.forEach((el) => {
    el.style.display = isStudent ? "none" : "";
  });

  // Role Impersonator lockdown: If native session role is FACULTY or STUDENT, remove View As toggle
  if (window.AUTHENTIC_USER_ROLE && window.AUTHENTIC_USER_ROLE !== "CHAIR" && window.AUTHENTIC_USER_ROLE !== "ADMIN") {
    const viewAsEl = document.getElementById("view-as-container");
    if (viewAsEl) viewAsEl.remove();
  }
};

// -------------------------------------------------------------
// Program Chair Active/Inactive Availability Status
// -------------------------------------------------------------
let _chairIsActive = true;

async function initChairStatus() {
  const toggleBtn = document.getElementById("chair-status-toggle-btn");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", async () => {
      try {
        const nextState = !_chairIsActive;
        const res = await API.updateChairStatus(nextState);
        if (res.status === "success") {
          _chairIsActive = nextState;
          renderChairStatus(_chairIsActive);
          showToast(res.message);
        }
      } catch (e) {
        showToast(e.message || "Failed to update Chair status", true);
      }
    });
  }

  await updateChairStatusUI();
}

async function updateChairStatusUI() {
  const role = window.CURRENT_ROLE || "CHAIR";
  const widget = document.getElementById("chair-status-widget");
  const toggleBtn = document.getElementById("chair-status-toggle-btn");
  const facBadge = document.getElementById("faculty-chair-badge");

  if (!widget) return;

  // Strict Isolation: Hidden completely from Students
  if (role === "STUDENT") {
    widget.style.display = "none";
    return;
  }

  try {
    const res = await API.getChairStatus();
    if (res.status === "success") {
      _chairIsActive = Boolean(res.is_active);
      widget.style.display = "flex";

      if (role === "CHAIR" || role === "ADMIN") {
        if (toggleBtn) toggleBtn.style.display = "inline-flex";
        if (facBadge) facBadge.style.display = "none";
      } else if (role === "FACULTY") {
        if (toggleBtn) toggleBtn.style.display = "none";
        if (facBadge) facBadge.style.display = "inline-flex";
      }

      renderChairStatus(_chairIsActive, res.chair_name);
    }
  } catch (err) {
    // If student or unauthorized, hide widget
    widget.style.display = "none";
  }
}

function renderChairStatus(isActive, chairName = "") {
  const dot = document.getElementById("chair-status-dot");
  const label = document.getElementById("chair-status-label");
  const facDot = document.getElementById("fac-status-dot");
  const facVal = document.getElementById("fac-status-val");

  const statusText = isActive ? "Active" : "Out of Office";

  if (dot) {
    dot.className = `status-dot ${isActive ? "active" : "inactive"}`;
  }
  if (label) {
    label.textContent = `Chair: ${statusText}`;
  }
  if (facDot) {
    facDot.className = `status-dot ${isActive ? "active" : "inactive"}`;
  }
  if (facVal) {
    facVal.textContent = statusText;
    facVal.style.color = isActive ? "#059669" : "#6B7280";
  }
}

// -------------------------------------------------------------
// 2-Tier Student Reschedule Pipeline Controller
// -------------------------------------------------------------
let _activeRescheduleTab = "pending";
let _allRescheduleRequests = [];

function initReschedulePipeline() {
  const headerBtn = document.getElementById("btn-header-reschedules");
  const modal = document.getElementById("reschedule-modal-backdrop");
  const closeBtn = document.getElementById("reschedule-modal-close-btn");

  if (headerBtn) {
    headerBtn.addEventListener("click", () => openRescheduleModal("pending"));
  }

  if (closeBtn && modal) {
    closeBtn.addEventListener("click", () => modal.classList.remove("active"));
    modal.addEventListener("click", (e) => {
      if (e.target === modal) modal.classList.remove("active");
    });
  }

  // Tabs navigation
  const tabPending = document.getElementById("reschedule-tab-pending");
  const tabAll = document.getElementById("reschedule-tab-all");
  const tabNew = document.getElementById("reschedule-tab-new");

  if (tabPending) {
    tabPending.addEventListener("click", () => switchRescheduleTab("pending"));
  }
  if (tabAll) {
    tabAll.addEventListener("click", () => switchRescheduleTab("all"));
  }
  if (tabNew) {
    tabNew.addEventListener("click", () => switchRescheduleTab("new"));
  }

  // Cancel form
  const cancelFormBtn = document.getElementById("btn-cancel-resched-form");
  if (cancelFormBtn) {
    cancelFormBtn.addEventListener("click", () => switchRescheduleTab("pending"));
  }

  // New Request Form Submit
  const newForm = document.getElementById("reschedule-new-form");
  if (newForm) {
    newForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      await submitNewRescheduleForm();
    });
  }

  updateReschedulesBadge();
}

async function updateReschedulesBadge() {
  const badge = document.getElementById("reschedule-count-badge");
  const facBadge = document.getElementById("fac-resched-badge");
  const studentBadge = document.getElementById("student-resched-badge");

  try {
    const res = await API.getRescheduleRequests();
    if (res.status === "success" && Array.isArray(res.data)) {
      _allRescheduleRequests = res.data;
      const role = window.CURRENT_ROLE || "CHAIR";

      let pendingCount = 0;
      if (role === "STUDENT") {
        pendingCount = res.data.length;
      } else if (role === "FACULTY") {
        pendingCount = res.data.filter((r) => r.status === "PENDING_FACULTY").length;
      } else {
        pendingCount = res.data.filter((r) => r.status === "PENDING_CHAIR" || r.status === "PENDING_FACULTY").length;
      }

      if (badge) {
        badge.textContent = pendingCount;
        badge.style.display = pendingCount > 0 ? "inline-block" : "none";
      }
      if (facBadge) {
        facBadge.textContent = pendingCount;
        facBadge.style.display = pendingCount > 0 ? "inline-block" : "none";
      }
      if (studentBadge) {
        studentBadge.textContent = pendingCount;
        studentBadge.style.display = pendingCount > 0 ? "inline-block" : "none";
      }
    }
  } catch (e) {
    // silently catch if not logged in
  }
}

window.openRescheduleModal = async function (defaultTab = "pending", preselectedScheduleId = null) {
  const modal = document.getElementById("reschedule-modal-backdrop");
  if (!modal) return;

  modal.classList.add("active");
  await updateReschedulesBadge();

  const tabNew = document.getElementById("reschedule-tab-new");
  if (tabNew) {
    // Only students can propose new reschedules
    tabNew.style.display = window.CURRENT_ROLE === "STUDENT" ? "inline-block" : "none";
  }

  if (defaultTab === "new") {
    await populateRescheduleScheduleSelect(preselectedScheduleId);
    switchRescheduleTab("new");
  } else {
    switchRescheduleTab(defaultTab);
  }
};

function switchRescheduleTab(tab) {
  _activeRescheduleTab = tab;

  const tabPending = document.getElementById("reschedule-tab-pending");
  const tabAll = document.getElementById("reschedule-tab-all");
  const tabNew = document.getElementById("reschedule-tab-new");
  const listContainer = document.getElementById("reschedule-list-container");
  const formContainer = document.getElementById("reschedule-new-form");

  if (tabPending) tabPending.className = `btn btn-sm ${tab === "pending" ? "btn-primary active" : "btn-secondary"}`;
  if (tabAll) tabAll.className = `btn btn-sm ${tab === "all" ? "btn-primary active" : "btn-secondary"}`;
  if (tabNew) tabNew.className = `btn btn-sm ${tab === "new" ? "btn-primary active" : "btn-secondary"}`;

  if (tab === "new") {
    if (listContainer) listContainer.style.display = "none";
    if (formContainer) formContainer.style.display = "flex";
  } else {
    if (formContainer) formContainer.style.display = "none";
    if (listContainer) listContainer.style.display = "flex";
    renderRescheduleCards(tab);
  }
}

function renderRescheduleCards(tab) {
  const container = document.getElementById("reschedule-list-container");
  if (!container) return;

  const role = window.CURRENT_ROLE || "CHAIR";
  let items = [..._allRescheduleRequests];

  if (tab === "pending") {
    if (role === "FACULTY") {
      items = items.filter((r) => r.status === "PENDING_FACULTY");
    } else if (role === "CHAIR" || role === "ADMIN") {
      items = items.filter((r) => r.status === "PENDING_CHAIR");
    } else if (role === "STUDENT") {
      items = items.filter((r) => r.status === "PENDING_FACULTY" || r.status === "PENDING_CHAIR");
    }
  }

  if (items.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 36px 20px;">
      <div style="font-size: 28px; margin-bottom: 8px;">✓</div>
      <div>No ${tab === "pending" ? "pending" : ""} reschedule requests found.</div>
    </div>`;
    return;
  }

  container.innerHTML = items.map((r) => {
    let statusPill = "";
    if (r.status === "PENDING_FACULTY") {
      statusPill = '<span class="step-pill pending">⏳ Step 1: Pending Faculty Review</span>';
    } else if (r.status === "PENDING_CHAIR") {
      statusPill = '<span class="step-pill pending">⏳ Step 2: Pending Program Chair Approval</span>';
    } else if (r.status === "APPROVED") {
      statusPill = '<span class="step-pill approved">✓ Approved &amp; Timetable Updated</span>';
    } else if (r.status === "REJECTED") {
      statusPill = '<span class="step-pill rejected">✕ Rejected</span>';
    }

    const isPendingFaculty = r.status === "PENDING_FACULTY";
    const isPendingChair = r.status === "PENDING_CHAIR";

    const canFacultyReview = role === "FACULTY" && isPendingFaculty;
    const canChairDecide = (role === "CHAIR" || role === "ADMIN") && (isPendingChair || isPendingFaculty);

    return `
      <div class="reschedule-card" data-id="${r.id}">
        <div class="reschedule-card-header">
          <div>
            <div class="reschedule-card-title">${escapeHtml(r.subject_code || "Class")} &bull; ${escapeHtml(r.section_name || "Section")}</div>
            <div style="font-size: 12px; color: var(--text-muted);">${escapeHtml(r.subject_title || "")} (${escapeHtml(r.faculty_name || "Instructor")})</div>
          </div>
          <div>${statusPill}</div>
        </div>

        <div class="reschedule-details-row">
          <div><strong>Current:</strong> ${r.current_day || "—"} ${r.current_start_time || ""}&ndash;${r.current_end_time || ""}</div>
          <div style="color: var(--sidebar-bg);">&rarr;</div>
          <div><strong>Proposed:</strong> <span style="color: #065F46; font-weight: 700;">${r.proposed_day} ${r.proposed_start_time ? r.proposed_start_time.slice(0, 5) : ""}&ndash;${r.proposed_end_time ? r.proposed_end_time.slice(0, 5) : ""}</span></div>
          <div><strong>Room:</strong> ${escapeHtml(r.room_code || "—")}</div>
        </div>

        <div style="font-size: 12px; background: var(--bg-page); padding: 8px 12px; border-radius: var(--radius-xs);">
          <strong>Reason:</strong> ${escapeHtml(r.reason)}
        </div>

        ${r.faculty_feedback ? `
          <div style="font-size: 12px; color: #065F46; background: #D1FAE5; padding: 6px 10px; border-radius: var(--radius-xs);">
            <strong>Faculty Feedback:</strong> ${escapeHtml(r.faculty_feedback)}
          </div>
        ` : ""}

        ${r.chair_feedback ? `
          <div style="font-size: 12px; color: #1E40AF; background: #DBEAFE; padding: 6px 10px; border-radius: var(--radius-xs);">
            <strong>Chair Feedback:</strong> ${escapeHtml(r.chair_feedback)}
          </div>
        ` : ""}

        ${canFacultyReview ? `
          <div class="reschedule-actions-row">
            <input type="text" class="reschedule-feedback-input" id="fac-feedback-${r.id}" placeholder="Optional faculty review feedback...">
            <button class="btn btn-sm btn-primary" onclick="handleFacultyReview(${r.id}, true)">
              ✓ Endorse Proposal
            </button>
            <button class="btn btn-sm btn-secondary" style="color: #DC2626;" onclick="handleFacultyReview(${r.id}, false)">
              ✕ Reject
            </button>
          </div>
        ` : ""}

        ${canChairDecide ? `
          <div class="reschedule-actions-row">
            <input type="text" class="reschedule-feedback-input" id="chair-feedback-${r.id}" placeholder="Chair authorization remarks...">
            <button class="btn btn-sm btn-primary" onclick="handleChairDecision(${r.id}, true)">
              ✓ 1-Click Approve &amp; Update Timetable
            </button>
            <button class="btn btn-sm btn-secondary" style="color: #DC2626;" onclick="handleChairDecision(${r.id}, false)">
              ✕ Reject
            </button>
          </div>
        ` : ""}
      </div>
    `;
  }).join("");
}

window.handleFacultyReview = async function (id, approved) {
  const input = document.getElementById(`fac-feedback-${id}`);
  const feedback = input ? input.value : "";
  try {
    const res = await API.reviewRescheduleByFaculty(id, approved, feedback);
    showToast(res.message);
    await updateReschedulesBadge();
    renderRescheduleCards(_activeRescheduleTab);
  } catch (err) {
    showToast(err.message || "Failed to submit review", true);
  }
};

window.handleChairDecision = async function (id, approved) {
  const input = document.getElementById(`chair-feedback-${id}`);
  const feedback = input ? input.value : "";
  try {
    const res = await API.decideRescheduleByChair(id, approved, feedback);
    showToast(res.message);
    await updateReschedulesBadge();
    renderRescheduleCards(_activeRescheduleTab);

    // Refresh timetable grid if on schedules view
    if (window.fetchAndRender) {
      window.fetchAndRender();
    }
  } catch (err) {
    showToast(err.message || "Failed to finalize decision", true);
  }
};

async function populateRescheduleScheduleSelect(preselectedId = null) {
  const select = document.getElementById("resched-select-schedule");
  if (!select) return;

  select.innerHTML = '<option value="">Loading classes...</option>';
  try {
    const res = await API.getSchedules();
    if (res.status === "success" && Array.isArray(res.data)) {
      select.innerHTML = '<option value="">-- Choose scheduled class --</option>' +
        res.data.map((s) => `
          <option value="${s.id}" ${preselectedId && String(preselectedId) === String(s.id) ? "selected" : ""}>
            ${escapeHtml(s.subject_code)} &bull; ${escapeHtml(s.section_name)} (${s.day_of_week} ${s.start_time.slice(0, 5)}-${s.end_time.slice(0, 5)} in ${escapeHtml(s.room_code)})
          </option>
        `).join("");
    }
  } catch (e) {
    select.innerHTML = '<option value="">Failed to load classes</option>';
  }
}

async function submitNewRescheduleForm() {
  const scheduleId = document.getElementById("resched-select-schedule")?.value;
  const day = document.getElementById("resched-day")?.value;
  const start = document.getElementById("resched-start")?.value;
  const end = document.getElementById("resched-end")?.value;
  const reason = document.getElementById("resched-reason")?.value;

  const banner = document.getElementById("resched-feedback-banner");
  if (banner) banner.style.display = "none";

  if (!scheduleId || !day || !start || !end || !reason) {
    showToast("Please fill all fields.", true);
    return;
  }

  try {
    const payload = {
      schedule_id: parseInt(scheduleId),
      proposed_day: day,
      proposed_start_time: start,
      proposed_end_time: end,
      reason: reason.trim(),
    };

    const res = await API.submitRescheduleRequest(payload);
    showToast(res.message);

    // Clear form
    document.getElementById("resched-reason").value = "";

    await updateReschedulesBadge();
    switchRescheduleTab("pending");
  } catch (err) {
    if (banner) {
      banner.style.display = "block";
      banner.style.background = "#FEE2E2";
      banner.style.color = "#991B1B";
      banner.textContent = err.message || "Conflict detected on proposed slot.";
    }
    showToast(err.message || "Failed to submit request", true);
  }
}

// -------------------------------------------------------------
// Seed Database Trigger Button
// -------------------------------------------------------------
function initSeedButton() {
  const btn = document.getElementById("global-seed-btn");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    if (!confirm("Reset database and seed Section 8 mock data?")) return;

    btn.disabled = true;
    btn.textContent = "Seeding...";
    try {
      await API.seedDatabase();
      showToast("Database reset & baseline data seeded!");
      setTimeout(() => window.location.reload(), 1000);
    } catch (err) {
      showToast(err.message, true);
    } finally {
      btn.disabled = false;
      btn.textContent = "Reset DB";
    }
  });
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
window.escapeHtml = escapeHtml;

// -------------------------------------------------------------
// Credentials Management Modal & Gateway
// -------------------------------------------------------------
function initCredentialsManagement() {
  const btnTrigger = document.getElementById("btn-user-credentials");
  const modal = document.getElementById("credentials-modal-backdrop");
  const btnClose = document.getElementById("credentials-modal-close-btn");
  const btnCancel = document.getElementById("btn-cancel-credentials");
  const form = document.getElementById("form-manage-credentials");
  const feedback = document.getElementById("credentials-feedback-banner");

  if (!modal || !form) return;

  function openCredentialsModal(enforceMandatory = false) {
    modal.classList.add("open");
    if (feedback) feedback.style.display = "none";

    if (enforceMandatory) {
      if (btnClose) btnClose.style.display = "none";
      if (btnCancel) btnCancel.style.display = "none";
      if (feedback) {
        feedback.style.display = "block";
        feedback.style.background = "#FEF3C7";
        feedback.style.color = "#92400E";
        feedback.textContent = "Security Notice: Please update your default Program Chair credentials before continuing.";
      }
    } else {
      if (btnClose) btnClose.style.display = "block";
      if (btnCancel) btnCancel.style.display = "inline-block";
    }
  }

  function closeCredentialsModal() {
    modal.classList.remove("open");
  }

  window.openCredentialsModal = openCredentialsModal;
  window.closeCredentialsModal = closeCredentialsModal;

  if (btnTrigger) {
    btnTrigger.addEventListener("click", () => openCredentialsModal(false));
  }

  if (btnClose) {
    btnClose.addEventListener("click", closeCredentialsModal);
  }

  if (btnCancel) {
    btnCancel.addEventListener("click", closeCredentialsModal);
  }

  // Check on load if credentials update is enforced
  API.get("/api/auth/me").then((res) => {
    if (res && res.must_change_credentials) {
      openCredentialsModal(true);
    }
  }).catch(() => {});

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (feedback) feedback.style.display = "none";

    const currentPassword = document.getElementById("inp-modal-current-pw").value;
    const newUsername = document.getElementById("inp-modal-new-username").value.trim();
    const newPassword = document.getElementById("inp-modal-new-pw").value;
    const confirmPassword = document.getElementById("inp-modal-confirm-pw").value;

    if (newPassword !== confirmPassword) {
      if (feedback) {
        feedback.style.display = "block";
        feedback.style.background = "#FEE2E2";
        feedback.style.color = "#991B1B";
        feedback.textContent = "New passwords do not match.";
      }
      return;
    }

    try {
      const res = await API.changeCredentials({
        current_password: currentPassword,
        new_username: newUsername,
        new_password: newPassword,
      });

      if (feedback) {
        feedback.style.display = "block";
        feedback.style.background = "#DCFCE7";
        feedback.style.color = "#15803D";
        feedback.textContent = "Credentials updated successfully!";
      }

      showToast("Credentials updated successfully!");

      const userElem = document.getElementById("header-username");
      if (userElem && res.user && res.user.username) {
        userElem.textContent = res.user.username;
      }

      setTimeout(() => {
        closeCredentialsModal();
        if (btnClose) btnClose.style.display = "block";
        if (btnCancel) btnCancel.style.display = "inline-block";
      }, 1200);
    } catch (err) {
      if (feedback) {
        feedback.style.display = "block";
        feedback.style.background = "#FEE2E2";
        feedback.style.color = "#991B1B";
        feedback.textContent = err.message || "Failed to update credentials.";
      }
      showToast(err.message || "Failed to update credentials", true);
    }
  });
}

// Initial bootstrap
document.addEventListener("DOMContentLoaded", () => {
  initHealthCheck();
  initViewAsSelector();
  initChairStatus();
  initReschedulePipeline();
  initCredentialsManagement();
  initSeedButton();
});


