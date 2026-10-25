/**
 * COE SYNC 2026 - Global Shell & Impersonator Logic (app.js)
 * Manages sticky top bar "View As" selector, health badge, and permission toggling.
 */

window.normalizeRole = function (role) {
  const up = String(role || "").trim().toUpperCase();
  if (up === "PROG_CHA" || up === "CHAIR") return "CHAIR";
  if (up === "FCLTY_DEPT" || up === "FACULTY") return "FACULTY";
  if (up === "STDN_MYR" || up === "STUDENT") return "STUDENT";
  return up;
};

window.CURRENT_ROLE = window.CURRENT_ROLE ? window.normalizeRole(window.CURRENT_ROLE) : "CHAIR";

document.addEventListener("DOMContentLoaded", () => {
  initHealthCheck();
  initViewAsSelector();
  initProfileSwitcher();
  initConflictAlertPill();
  updateGlobalAlertPill();
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
// Conflict Alert Pill (#conflict-alert-pill)
// -------------------------------------------------------------
function initConflictAlertPill() {
  const pill = document.getElementById("conflict-alert-pill");
  if (!pill) return;

  pill.addEventListener("click", () => {
    if (typeof openRadar === "function") {
      openRadar();
    } else {
      window.location.href = "/schedules?radar=open";
    }
  });
}

window.updateGlobalAlertPill = async function () {
  const pillText = document.getElementById("conflict-alert-text");
  if (!pillText) return;

  try {
    const res = await API.getAnalyticsSummary();
    if (res && res.status === "success") {
      const count = res.data?.unresolved_conflicts || 0;
      pillText.textContent = `${count} Alert${count === 1 ? "" : "s"}`;
    }
  } catch (e) {
    // Soft ignore
  }
};

// -------------------------------------------------------------
// Interactive Role Switcher Profile Pill & Dropdown
// -------------------------------------------------------------
function initProfileSwitcher() {
  const pill = document.getElementById("user-profile-pill");
  const menu = document.getElementById("role-dropdown-menu");
  if (!pill || !menu) return;

  pill.addEventListener("click", (e) => {
    if (e.target.closest(".role-dropdown-menu")) return;
    menu.classList.toggle("show");
  });

  document.addEventListener("click", (e) => {
    if (!pill.contains(e.target)) {
      menu.classList.remove("show");
    }
  });

}

function updateProfilePillUI(role) {
  const avatarEl = document.getElementById("profile-avatar-circle");
  if (!avatarEl) return;

  avatarEl.classList.remove("avatar-dean", "avatar-admin", "avatar-chair", "avatar-faculty", "avatar-student");

  const norm = window.normalizeRole ? window.normalizeRole(role) : role;
  if (norm === "DEAN") {
    avatarEl.textContent = "DN";
    avatarEl.classList.add("avatar-dean");
  } else if (norm === "ADMIN") {
    avatarEl.textContent = "AD";
    avatarEl.classList.add("avatar-admin");
  } else if (norm === "FACULTY") {
    avatarEl.textContent = "FC";
    avatarEl.classList.add("avatar-faculty");
  } else if (norm === "STUDENT") {
    avatarEl.textContent = "ST";
    avatarEl.classList.add("avatar-student");
  } else {
    avatarEl.textContent = "CH";
    avatarEl.classList.add("avatar-chair");
  }
}

async function executeRoleSwitch(chosenRole) {
  try {
    const result = await API.impersonate(chosenRole);
    window.CURRENT_ROLE = chosenRole;
    if (result && result.active_reference_id) {
      window.CURRENT_REF_ID = result.active_reference_id;
    }
    updateProfilePillUI(chosenRole);
    applyRolePermissions(chosenRole);

    const selector = document.getElementById("view-as-select");
    if (selector) selector.value = chosenRole;

    showToast(result.message || `Switched view to ${chosenRole}`);

    await updateChairStatusUI();
    await updateReschedulesBadge();
    await updateRequestsInbox();
    await updateGlobalAlertPill();

    window.dispatchEvent(new CustomEvent("roleChanged", { detail: { role: chosenRole, reference_id: result?.active_reference_id } }));
  } catch (err) {
    showToast(err.message || "Failed to switch role", true);
  }
}

// -------------------------------------------------------------
// Sticky "View As" Role Impersonator Selector (Backwards Compatibility)
// -------------------------------------------------------------
async function initViewAsSelector() {
  const selector = document.getElementById("view-as-select");

  try {
    const sessionInfo = await API.getCurrentSession();
    if (sessionInfo) {
      window.AUTHENTIC_USER_ROLE = sessionInfo.role;
      const effectiveRole = sessionInfo.active_role || sessionInfo.role;
      window.CURRENT_ROLE = window.normalizeRole(effectiveRole);
      window.CURRENT_PROGRAM = sessionInfo.active_program || sessionInfo.user_program || sessionInfo.program || null;
      window.USER_PROGRAM = sessionInfo.program || sessionInfo.user_program || null;
      if (sessionInfo.active_reference_id) {
        window.CURRENT_REF_ID = sessionInfo.active_reference_id;
      }
      updateProfilePillUI(effectiveRole);

      const normUserRole = window.normalizeRole(sessionInfo.role);
      if (normUserRole !== "CHAIR" && normUserRole !== "ADMIN" && normUserRole !== "DEAN") {
        const container = document.getElementById("view-as-container");
        if (container) container.remove();
        applyRolePermissions(window.CURRENT_ROLE);
        return;
      }

      if (selector) {
        selector.value = effectiveRole;
      }
      applyRolePermissions(window.CURRENT_ROLE);
    }
  } catch (e) {
    console.warn("Could not fetch session info:", e);
  }

  if (selector) {
    selector.addEventListener("change", async (e) => {
      await executeRoleSwitch(e.target.value);
    });
  }
}

/**
 * Apply role-based UI restrictions according to NEXUS 2.0 access matrix
 */
window.applyRolePermissions = function (role) {
  let normalizedRole = role || "CHAIR";
  if (role === "PROG_CHA") normalizedRole = "CHAIR";
  if (role === "FCLTY_DEPT") normalizedRole = "FACULTY";
  if (role === "STDN_MYR") normalizedRole = "STUDENT";

  const isDean = normalizedRole === "DEAN";
  const isAdmin = normalizedRole === "ADMIN";
  const isChair = normalizedRole === "CHAIR";
  const isFaculty = normalizedRole === "FACULTY";
  const isStudent = normalizedRole === "STUDENT";
  const isAdminOrChair = isChair || isAdmin;

  updateProfilePillUI(normalizedRole);

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

  // Navigation tabs visibility
  const navDashboard = document.getElementById("nav-dashboard");
  const navSchedules = document.getElementById("nav-schedules");
  const navCreateSchedule = document.getElementById("nav-create-schedule");
  const navRooms = document.getElementById("nav-rooms");
  const navMyProfile = document.getElementById("nav-my-profile");
  const navFaculty = document.getElementById("nav-faculty");
  const navSections = document.getElementById("nav-sections");
  const navSubjects = document.getElementById("nav-subjects");
  const navConflictRadar = document.getElementById("nav-conflict-radar");
  const navReports = document.getElementById("nav-reports");

  if (navDashboard) navDashboard.style.display = ""; // All see dashboard
  if (navSchedules) navSchedules.style.display = ""; // All see schedules
  if (navRooms) navRooms.style.display = ""; // All see rooms

  if (navCreateSchedule) navCreateSchedule.style.display = isAdminOrChair ? "" : "none";
  if (navMyProfile) navMyProfile.style.display = isFaculty ? "" : "none";
  if (navFaculty) navFaculty.style.display = (isAdminOrChair || isDean) ? "" : "none";
  if (navSections) navSections.style.display = isStudent ? "none" : "";
  // Dean CANNOT see subjects per NEXUS 2.0 Part 2 spec:
  if (navSubjects) navSubjects.style.display = (isAdminOrChair || isFaculty) ? "" : "none";
  if (navConflictRadar) navConflictRadar.style.display = isAdminOrChair ? "" : "none";
  if (navReports) navReports.style.display = (isAdminOrChair || isDean) ? "" : "none";

  // Role Impersonator lockdown: If native session role is FACULTY or STUDENT, remove View As toggle
  const normAuth = window.normalizeRole(window.AUTHENTIC_USER_ROLE || "");
  if (normAuth && normAuth !== "CHAIR" && normAuth !== "ADMIN" && normAuth !== "DEAN") {
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
let _activeInboxTab = "interdept";
let _activeRescheduleTab = "pending";
let _allRescheduleRequests = [];
let _allInterdeptRequests = [];

function initReschedulePipeline() {
  const headerBtn = document.getElementById("btn-header-reschedules");
  const inboxPill = document.getElementById("requests-inbox-pill");
  const modal = document.getElementById("reschedule-modal-backdrop");
  const closeBtn = document.getElementById("reschedule-modal-close-btn");

  if (headerBtn) {
    headerBtn.addEventListener("click", () => openUnifiedInboxModal("reschedules"));
  }

  if (inboxPill) {
    inboxPill.addEventListener("click", () => openUnifiedInboxModal());
  }

  if (closeBtn && modal) {
    closeBtn.addEventListener("click", () => modal.classList.remove("active"));
    modal.addEventListener("click", (e) => {
      if (e.target === modal) modal.classList.remove("active");
    });
  }

  // Top Inbox Tabs navigation
  const tabInterdept = document.getElementById("inbox-tab-interdept");
  const tabResched = document.getElementById("inbox-tab-reschedules");
  if (tabInterdept) {
    tabInterdept.addEventListener("click", () => switchInboxTab("interdept"));
  }
  if (tabResched) {
    tabResched.addEventListener("click", () => switchInboxTab("reschedules"));
  }

  // Reschedule Sub-Tabs navigation
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
  updateRequestsInbox();
}

window.openUnifiedInboxModal = async function (preferredTab = null, defaultSubTab = "pending") {
  const modal = document.getElementById("reschedule-modal-backdrop");
  if (!modal) return;

  const role = window.normalizeRole ? window.normalizeRole(window.CURRENT_ROLE) : (window.CURRENT_ROLE || "CHAIR");
  const tabInterdept = document.getElementById("inbox-tab-interdept");
  const tabNew = document.getElementById("reschedule-tab-new");

  if (tabInterdept) {
    tabInterdept.style.display = (role === "STUDENT" || role === "FACULTY") ? "none" : "inline-block";
  }
  if (tabNew) {
    tabNew.style.display = role === "STUDENT" ? "inline-block" : "none";
  }

  modal.classList.add("active");
  await updateRequestsInbox();
  await updateReschedulesBadge();

  if (preferredTab) {
    switchInboxTab(preferredTab, defaultSubTab);
  } else {
    const reschedCount = parseInt(document.getElementById("reschedule-count-badge")?.textContent || "0", 10);
    const interCount = parseInt(document.getElementById("count-badge-interdept")?.textContent || "0", 10);
    if (reschedCount > 0) {
      switchInboxTab("reschedules", defaultSubTab);
    } else if (interCount > 0 && role !== "STUDENT" && role !== "FACULTY") {
      switchInboxTab("interdept", defaultSubTab);
    } else {
      switchInboxTab("reschedules", defaultSubTab);
    }
  }
};

window.switchInboxTab = function (tab, subTab = "pending") {
  _activeInboxTab = tab;
  const tabInterdept = document.getElementById("inbox-tab-interdept");
  const tabResched = document.getElementById("inbox-tab-reschedules");
  const interContainer = document.getElementById("interdept-list-container");
  const reschedContainer = document.getElementById("reschedule-list-container");
  const subfilterBar = document.getElementById("reschedule-subfilter-bar");
  const formContainer = document.getElementById("reschedule-new-form");
  const tabNew = document.getElementById("reschedule-tab-new");
  const role = window.normalizeRole ? window.normalizeRole(window.CURRENT_ROLE) : (window.CURRENT_ROLE || "CHAIR");

  if (tab === "interdept") {
    if (tabInterdept) tabInterdept.className = "btn btn-sm btn-primary active";
    if (tabResched) tabResched.className = "btn btn-sm btn-secondary";
    if (interContainer) interContainer.style.display = "flex";
    if (reschedContainer) reschedContainer.style.display = "none";
    if (subfilterBar) subfilterBar.style.display = "none";
    if (formContainer) formContainer.style.display = "none";
    if (tabNew) tabNew.style.display = "none";
    renderInterdeptCards();
  } else {
    if (tabResched) tabResched.className = "btn btn-sm btn-primary active";
    if (tabInterdept) tabInterdept.className = "btn btn-sm btn-secondary";
    if (interContainer) interContainer.style.display = "none";
    if (reschedContainer) reschedContainer.style.display = "flex";
    if (subfilterBar) subfilterBar.style.display = "flex";
    if (tabNew) {
      tabNew.style.display = role === "STUDENT" ? "inline-block" : "none";
    }
    switchRescheduleTab(subTab);
  }
};

window.updateRequestsInbox = async function () {
  try {
    const res = await API.get("/api/requests/pending-summary");
    if (res.status === "success" && res.data) {
      const d = res.data;
      const totalPending = d.total_pending || 0;
      const interCount = d.interdept_count || 0;
      const reschedCount = d.reschedule_count || 0;

      const inboxText = document.getElementById("requests-inbox-text");
      const inboxDot = document.getElementById("requests-dot");
      const badgeInter = document.getElementById("count-badge-interdept");
      const badgeResched = document.getElementById("count-badge-resched");

      if (inboxText) {
        inboxText.textContent = `🔔 ${totalPending} Request${totalPending === 1 ? '' : 's'}`;
      }
      if (inboxDot) {
        inboxDot.style.background = totalPending > 0 ? "#EF4444" : "#10B981";
      }
      if (badgeInter) badgeInter.textContent = interCount;
      if (badgeResched) badgeResched.textContent = reschedCount;
    }
  } catch (err) {
    // soft catch
  }
};

window.renderInterdeptCards = async function () {
  const container = document.getElementById("interdept-list-container");
  if (!container) return;

  container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 24px;">Loading inter-department requests...</div>`;

  try {
    const res = await API.get("/api/interdept/requests");
    if (res.status === "success" && Array.isArray(res.data)) {
      _allInterdeptRequests = res.data;
      const items = res.data;

      if (items.length === 0) {
        container.innerHTML = `
          <div style="text-align: center; color: var(--text-muted); padding: 36px 20px;">
            <div style="font-size: 28px; margin-bottom: 8px;">✓</div>
            <div>No pending inter-department room / conflict requests found.</div>
          </div>
        `;
        return;
      }

      const role = window.CURRENT_ROLE || "CHAIR";
      const canAct = role === "CHAIR" || role === "ADMIN" || role === "DEAN";

      container.innerHTML = items.map(r => {
        let statusPill = "";
        if (r.status === "PENDING_APPROVAL") {
          statusPill = `<span class="step-pill pending">⏳ Pending Approval</span>`;
        } else if (r.status === "APPROVED") {
          statusPill = `<span class="step-pill approved">✓ Approved &amp; Allocated</span>`;
        } else {
          statusPill = `<span class="step-pill rejected">✕ Declined</span>`;
        }

        return `
          <div class="reschedule-card" data-id="${r.id}" style="border-left: 4px solid #3B82F6;">
            <div class="reschedule-card-header">
              <div>
                <div class="reschedule-card-title">
                  <span style="background: #DBEAFE; color: #1D4ED8; font-size: 11px; font-weight: 800; padding: 2px 6px; border-radius: 4px; margin-right: 4px;">
                    ${escapeHtml(r.requesting_dept)} &rarr; ${escapeHtml(r.target_dept || 'GEN')}
                  </span>
                  ${escapeHtml(r.subject_code || 'Subject')} &bull; ${escapeHtml(r.section_name || 'Section')}
                </div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">
                  Room Requested: <strong>${escapeHtml(r.target_room_code || 'Any')}</strong> (${escapeHtml(r.target_dept || 'General COE')})
                  &bull; Requested by Chair (${escapeHtml(r.requesting_dept)})
                </div>
              </div>
              <div>${statusPill}</div>
            </div>

            <div class="reschedule-details-row" style="margin-top: 6px;">
              <div><strong>Requested Slot:</strong> ${r.day_of_week || 'MON'} ${r.start_time ? r.start_time.slice(0,5) : ''}&ndash;${r.end_time ? r.end_time.slice(0,5) : ''}</div>
            </div>

            <div style="font-size: 12px; background: #F1F5F9; padding: 8px 12px; border-radius: var(--radius-xs); margin-top: 6px;">
              <strong>Justification:</strong> ${escapeHtml(r.reason || 'Department room allocation overflow')}
            </div>

            <!-- AI / Algorithmic Alternative Recommendations -->
            <div style="margin-top: 6px; padding: 10px 12px; background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: var(--radius-xs);">
              <div style="font-size: 11.5px; font-weight: 700; color: #065F46; display: flex; align-items: center; gap: 4px; margin-bottom: 2px;">
                <span>💡 Algorithmic Alternative Recommendation:</span>
              </div>
              <div style="font-size: 12px; color: #047857;">
                Assign to <strong>${escapeHtml(r.recommended_alt_room || 'COE 102')}</strong> &bull; Recommended Slot: <strong>${escapeHtml(r.recommended_alt_time || 'Alternate Free Window')}</strong>
              </div>
            </div>

            ${r.status === "PENDING_APPROVAL" && canAct ? `
              <div class="reschedule-actions-row" style="margin-top: 10px; display:flex; gap: 8px;">
                <button class="btn btn-sm btn-primary" onclick="handleInterdeptAction(${r.id}, 'APPROVE')">
                  ✓ Approve &amp; Apply Alternative
                </button>
                <button class="btn btn-sm btn-secondary" style="color: #DC2626;" onclick="handleInterdeptAction(${r.id}, 'DECLINE')">
                  ✕ Decline
                </button>
              </div>
            ` : ""}
          </div>
        `;
      }).join("");
    }
  } catch (err) {
    container.innerHTML = `<div style="text-align: center; color: #DC2626; padding: 24px;">Failed to load inter-department requests: ${escapeHtml(err.message)}</div>`;
  }
};

window.handleInterdeptAction = async function (id, action) {
  try {
    const res = await API.post(`/api/interdept/${id}/action`, { action });
    showToast(res.message || `Request ${action.toLowerCase()}d successfully`);
    await updateRequestsInbox();
    renderInterdeptCards();
    if (window.fetchAndRender) window.fetchAndRender();
  } catch (err) {
    showToast(err.message || "Failed to process inter-department action", true);
  }
};

async function updateReschedulesBadge() {
  const badge = document.getElementById("reschedule-count-badge");
  const facBadge = document.getElementById("fac-resched-badge");
  const studentBadge = document.getElementById("student-resched-badge");
  const chairBadge = document.getElementById("chair-resched-badge");

  try {
    const res = await API.getRescheduleRequests();
    if (res.status === "success" && Array.isArray(res.data)) {
      _allRescheduleRequests = res.data;
      const role = window.normalizeRole ? window.normalizeRole(window.CURRENT_ROLE) : (window.CURRENT_ROLE || "CHAIR");

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
      if (chairBadge) {
        chairBadge.textContent = pendingCount;
        chairBadge.style.display = pendingCount > 0 ? "inline-block" : "none";
      }
    }
  } catch (e) {
    // silently catch if not logged in
  }
}

window.openRescheduleModal = async function (defaultTab = "pending", preselectedScheduleId = null) {
  await openUnifiedInboxModal("reschedules", defaultTab);
  if (defaultTab === "new") {
    await populateRescheduleScheduleSelect(preselectedScheduleId);
    switchRescheduleTab("new");
  } else if (defaultTab === "all") {
    switchRescheduleTab("all");
  } else {
    switchRescheduleTab("pending");
  }
};

function switchRescheduleTab(tab) {
  _activeRescheduleTab = tab;

  const tabPending = document.getElementById("reschedule-tab-pending");
  const tabAll = document.getElementById("reschedule-tab-all");
  const tabNew = document.getElementById("reschedule-tab-new");
  const listContainer = document.getElementById("reschedule-list-container");
  const formContainer = document.getElementById("reschedule-new-form");

  if (tabPending) tabPending.className = `btn btn-xs ${tab === "pending" ? "btn-primary active" : "btn-secondary"}`;
  if (tabAll) tabAll.className = `btn btn-xs ${tab === "all" ? "btn-primary active" : "btn-secondary"}`;
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

async function renderRescheduleCards(tab) {
  const container = document.getElementById("reschedule-list-container");
  if (!container) return;

  container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 24px;">Loading requests...</div>`;

  try {
    const res = await API.getRescheduleRequests();
    if (res.status === "success" && Array.isArray(res.data)) {
      _allRescheduleRequests = res.data;
    }
  } catch (err) {
    console.error("Failed loading reschedule requests:", err);
  }

  const role = window.normalizeRole ? window.normalizeRole(window.CURRENT_ROLE) : (window.CURRENT_ROLE || "CHAIR");
  let items = [..._allRescheduleRequests];

  if (tab === "pending") {
    if (role === "FACULTY") {
      items = items.filter((r) => r.status === "PENDING_FACULTY" || r.status === "PENDING");
    } else if (role === "CHAIR" || role === "ADMIN") {
      items = items.filter((r) => r.status === "PENDING_CHAIR" || r.status === "PENDING_FACULTY" || r.status === "PENDING");
    } else if (role === "STUDENT") {
      items = items.filter((r) => r.status === "PENDING_FACULTY" || r.status === "PENDING_CHAIR" || r.status === "PENDING");
    }
  }

  if (items.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 36px 20px;">
      <div style="font-size: 28px; margin-bottom: 8px;">📋</div>
      <div style="font-weight: 600; font-size: 14px; color: var(--text-dark);">No ${tab === "pending" ? "pending " : ""}reschedule requests found.</div>
      <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
        ${role === "STUDENT" ? "You currently have no class reschedule proposals in this view." : "There are no pending requests requiring action."}
      </div>
      ${role === "STUDENT" ? `
        <div style="margin-top: 14px;">
          <button type="button" class="btn btn-sm btn-primary" onclick="window.openRescheduleModal('new')">
            + Request Class Reschedule
          </button>
        </div>` : ""}
    </div>`;
    return;
  }

  container.innerHTML = items.map((r) => {
    const isRoomBooking = !r.schedule_id || (r.reason && r.reason.startsWith("[Room Booking Request]"));
    let statusPill = "";
    if (r.status === "PENDING_FACULTY" || r.status === "PENDING") {
      statusPill = '<span class="step-pill pending" style="background:#FEF3C7; color:#92400E; font-weight:700;">⏳ Step 1: Pending Faculty Review</span>';
    } else if (r.status === "PENDING_CHAIR") {
      statusPill = '<span class="step-pill pending" style="background:#DBEAFE; color:#1E40AF; font-weight:700;">⏳ Step 2: Pending Chair Approval</span>';
    } else if (r.status === "APPROVED") {
      statusPill = isRoomBooking ? '<span class="step-pill approved">✓ Approved &amp; Room Reserved</span>' : '<span class="step-pill approved">✓ Approved &amp; Timetable Updated</span>';
    } else if (r.status === "REJECTED") {
      statusPill = '<span class="step-pill rejected">✕ Rejected</span>';
    }

    const isPending = r.status === "PENDING" || r.status === "PENDING_FACULTY" || r.status === "PENDING_CHAIR";
    const canReview = isPending && (role === "FACULTY" || role === "CHAIR" || role === "ADMIN");
    const expDays = r.expires_in_days !== undefined ? r.expires_in_days : 7;

    const titleText = isRoomBooking
      ? `🏢 Room Reservation &bull; ${escapeHtml(r.proposed_room_code || "Room")}`
      : `${escapeHtml(r.subject_code || "Class")} &bull; ${escapeHtml(r.section_name || "Section")}`;
    const subtitleText = isRoomBooking
      ? `Requested by ${escapeHtml(r.requested_by_name || "Student Mayor")} (${escapeHtml(r.section_name || "Section")})`
      : `${escapeHtml(r.subject_title || "")} (${escapeHtml(r.faculty_name || "Instructor")})`;

    return `
      <div class="reschedule-card" data-id="${r.id}" style="${isRoomBooking ? 'border-left: 4px solid #10B981;' : ''}">
        <div class="reschedule-card-header">
          <div>
            <div class="reschedule-card-title">${titleText}</div>
            <div style="font-size: 12px; color: var(--text-muted);">${subtitleText}</div>
          </div>
          <div>${statusPill}</div>
        </div>

        <div class="reschedule-details-row">
          ${isRoomBooking ? `
            <div><strong>Type:</strong> <span style="font-weight: 700; color: #047857;">Ad-Hoc Room Reservation</span></div>
            <div style="color: var(--sidebar-bg);">&bull;</div>
            <div><strong>Reserved Slot:</strong> <span style="color: #065F46; font-weight: 700;">${r.proposed_day} ${r.proposed_start_time ? r.proposed_start_time.slice(0, 5) : ""}&ndash;${r.proposed_end_time ? r.proposed_end_time.slice(0, 5) : ""}</span></div>
            <div><strong>Room:</strong> <strong>${escapeHtml(r.proposed_room_code || r.room_code || "Facility")}</strong></div>
          ` : `
            <div><strong>Current:</strong> ${r.current_day || "—"} ${r.current_start_time || ""}&ndash;${r.current_end_time || ""}</div>
            <div style="color: var(--sidebar-bg);">&rarr;</div>
            <div><strong>Proposed:</strong> <span style="color: #065F46; font-weight: 700;">${r.proposed_day} ${r.proposed_start_time ? r.proposed_start_time.slice(0, 5) : ""}&ndash;${r.proposed_end_time ? r.proposed_end_time.slice(0, 5) : ""}</span></div>
            <div><strong>Room:</strong> ${escapeHtml(r.proposed_room_code || r.room_code || "Auto/Current")}</div>
          `}
        </div>

        <div style="font-size: 12px; background: var(--bg-page); padding: 8px 12px; border-radius: var(--radius-xs); margin-top: 6px;">
          <strong>Reason:</strong> ${escapeHtml(r.reason)}
        </div>

        <!-- 7-Day TTL Expiration & Conflict Radar Badges -->
        <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:4px;">
          <span style="background: #FEF3C7; color: #92400E; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 9999px;">
            ⏳ Expires in ${expDays} day${expDays === 1 ? '' : 's'} (Auto-deletes after 1 week without response)
          </span>
          <span style="background: #DCFCE7; color: #166534; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 9999px;">
            ✓ Pre-Flight Conflict Free
          </span>
        </div>

        ${r.faculty_feedback ? `
          <div style="font-size: 12px; color: #065F46; background: #D1FAE5; padding: 6px 10px; border-radius: var(--radius-xs); margin-top: 4px;">
            <strong>Faculty Feedback:</strong> ${escapeHtml(r.faculty_feedback)}
          </div>
        ` : ""}

        ${r.chair_feedback ? `
          <div style="font-size: 12px; color: #1E40AF; background: #DBEAFE; padding: 6px 10px; border-radius: var(--radius-xs); margin-top: 4px;">
            <strong>Chair Decision / Remarks:</strong> ${escapeHtml(r.chair_feedback)}
          </div>
        ` : ""}

        ${canReview ? `
          <div class="reschedule-actions-row" style="margin-top: 8px; display:flex; gap: 8px; align-items: center; flex-wrap: wrap;">
            ${(r.status === "PENDING_FACULTY" || r.status === "PENDING") ? `
              ${role === "FACULTY" ? `
                <button class="btn btn-sm btn-primary" onclick="handleDirectApprove(${r.id})">
                  ✓ Endorse Proposal (Faculty Review)
                </button>
                <button class="btn btn-sm btn-secondary" style="color: #DC2626;" onclick="handleDirectReject(${r.id})">
                  ✕ Decline
                </button>
              ` : (role === "CHAIR" ? `
                <span style="font-size: 11px; color: var(--text-muted); margin-right: 4px;">⏳ Awaiting Faculty Endorsement</span>
                <button class="btn btn-sm btn-outline" style="font-size: 11px;" title="Program Chair override" onclick="handleDirectApprove(${r.id})">
                  ⚡ Chair Override &amp; Approve
                </button>
                <button class="btn btn-sm btn-secondary" style="color: #DC2626;" onclick="handleDirectReject(${r.id})">
                  ✕ Decline
                </button>
              ` : `
                <button class="btn btn-sm btn-primary" onclick="handleDirectApprove(${r.id})">
                  ⚡ Admin Override &amp; Approve
                </button>
                <button class="btn btn-sm btn-secondary" style="color: #DC2626;" onclick="handleDirectReject(${r.id})">
                  ✕ Decline
                </button>
              `)}
            ` : (r.status === "PENDING_CHAIR" ? `
              ${(role === "CHAIR" || role === "ADMIN") ? `
                <button class="btn btn-sm btn-primary" onclick="handleDirectApprove(${r.id})">
                  ${isRoomBooking ? "✓ Authorize &amp; Reserve Room" : "✓ Authorize &amp; Update Timetable"}
                </button>
                <button class="btn btn-sm btn-secondary" style="color: #DC2626;" onclick="handleDirectReject(${r.id})">
                  ✕ Decline
                </button>
              ` : `
                <span style="font-size: 11px; color: #047857; font-weight: 600;">✓ Endorsed by Faculty &bull; Forwarded to Chair</span>
              `}
            ` : "")}
          </div>
        ` : ""}
      </div>
    `;
  }).join("");
}

window.handleDirectApprove = async function (id) {
  try {
    const res = await API.post(`/api/reschedule/${id}/approve`, {});
    showToast(res.message || "Reschedule request approved & timetable updated!");
    await updateReschedulesBadge();
    renderRescheduleCards(_activeRescheduleTab);
    if (window.fetchAndRender) window.fetchAndRender();
  } catch (err) {
    showToast(err.message || "Failed to approve request", true);
  }
};

window.handleDirectReject = async function (id) {
  const reason = prompt("Optional reason for declining request:") || "";
  try {
    const res = await API.post(`/api/reschedule/${id}/reject`, { reason });
    showToast(res.message || "Reschedule request declined.");
    await updateReschedulesBadge();
    renderRescheduleCards(_activeRescheduleTab);
  } catch (err) {
    showToast(err.message || "Failed to decline request", true);
  }
};

window.handleFacultyReview = async function (id, approved) {
  if (approved) {
    await handleDirectApprove(id);
  } else {
    await handleDirectReject(id);
  }
};

window.handleChairDecision = async function (id, approved) {
  if (approved) {
    await handleDirectApprove(id);
  } else {
    await handleDirectReject(id);
  }
};

async function populateRescheduleScheduleSelect(preselectedId = null) {
  const select = document.getElementById("resched-select-schedule");
  const roomSelect = document.getElementById("resched-room");
  if (!select) return;

  select.innerHTML = '<option value="">Loading classes...</option>';
  try {
    const [resSched, resRooms] = await Promise.all([
      API.getSchedules(),
      API.getRooms().catch(() => ({ data: [] }))
    ]);

    if (resSched.status === "success" && Array.isArray(resSched.data)) {
      select.innerHTML = '<option value="">-- Choose scheduled class --</option>' +
        resSched.data.map((s) => `
          <option value="${s.id}" ${preselectedId && String(preselectedId) === String(s.id) ? "selected" : ""}>
            ${escapeHtml(s.subject_code)} &bull; ${escapeHtml(s.section_name)} (${s.day_of_week} ${s.start_time.slice(0, 5)}-${s.end_time.slice(0, 5)} in ${escapeHtml(s.room_code)})
          </option>
        `).join("");
    }

    if (roomSelect && resRooms.data) {
      roomSelect.innerHTML = '<option value="">-- Keep Current Room or Auto-Assign --</option>' +
        resRooms.data.map((r) => `
          <option value="${r.id}">${escapeHtml(r.room_code)} (${escapeHtml(r.building || 'COE')})</option>
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
  const room = document.getElementById("resched-room")?.value;
  const reason = document.getElementById("resched-reason")?.value;

  const banner = document.getElementById("resched-feedback-banner");
  if (banner) banner.style.display = "none";

  if (!scheduleId || !day || !start || !end || !reason) {
    showToast("Please fill all required fields.", true);
    return;
  }

  try {
    const payload = {
      schedule_id: parseInt(scheduleId),
      proposed_day: day,
      proposed_start_time: start,
      proposed_end_time: end,
      proposed_room_id: room ? parseInt(room) : null,
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

// -------------------------------------------------------------
// Academic Term Synchronization (localStorage: coe_sync_active_term)
// -------------------------------------------------------------
function initAcademicTermSync() {
  const storedTerm = localStorage.getItem("coe_sync_active_term") || "1";
  const globalSelect = document.getElementById("global-term-select");
  if (globalSelect) {
    globalSelect.value = storedTerm;
    globalSelect.addEventListener("change", (e) => {
      const newTerm = e.target.value;
      localStorage.setItem("coe_sync_active_term", newTerm);
      window.dispatchEvent(new CustomEvent("academicTermChanged", { detail: { term: newTerm } }));
    });
  }

  window.addEventListener("academicTermChanged", (e) => {
    const term = e.detail?.term || "1";
    if (globalSelect && globalSelect.value !== term) {
      globalSelect.value = term;
    }
    const pageTermSelects = document.querySelectorAll("#filter-term, #sg-semester, #manual-semester");
    pageTermSelects.forEach((sel) => {
      if (sel && sel.value !== term) {
        sel.value = term;
        sel.dispatchEvent(new Event("change"));
      }
    });
  });
}

// Initial bootstrap
document.addEventListener("DOMContentLoaded", () => {
  initHealthCheck();
  initAcademicTermSync();
  initViewAsSelector();
  initChairStatus();
  initReschedulePipeline();
  initCredentialsManagement();
  initSeedButton();
});


