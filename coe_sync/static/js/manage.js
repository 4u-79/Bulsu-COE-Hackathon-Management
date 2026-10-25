/**
 * COE SYNC 2026 - Master Data Management CRUD Controller (manage.js)
 * Implements tab switching, real-time validation, dynamic modals, and REST API calls.
 */

let activeTab = "rooms";
let currentRoomMode = "availability";
let masterDataCache = {
  rooms: [],
  faculty: [],
  sections: [],
  subjects: [],
};
let schedulesCache = [];

document.addEventListener("DOMContentLoaded", () => {
  initManageTabs();
  initModalHandlers();
  initTableFilters();
  initRoomModeSwitcher();
  initRoomAvailabilityControls();
  loadAllMasterData();

  // Listen for role changes from the sticky "View As" selector
  window.addEventListener("roleChanged", () => {
    window.applyRolePermissions(window.CURRENT_ROLE);
  });
});

// -------------------------------------------------------------
// Tab Switching
// -------------------------------------------------------------
function switchTab(tabName) {
  activeTab = tabName;

  // 1. Hide all tab panels
  document.querySelectorAll('.tab-panel, .manage-panel').forEach((panel) => {
    panel.classList.add('hidden');
    panel.classList.remove('active');
    panel.style.display = 'none';
  });

  // 2. Show the targeted panel
  const activePanel =
    document.getElementById(`tab-panel-${tabName}`) ||
    document.getElementById(`panel-${tabName}`);
  if (activePanel) {
    activePanel.classList.remove('hidden');
    activePanel.classList.add('active');
    activePanel.style.display = 'block';
  }

  // 3. Update tab button active states
  document.querySelectorAll('.tab-btn, .manage-tab-btn').forEach((btn) => {
    btn?.classList.toggle('active', btn.dataset?.tab === tabName);
  });

  // 3b. Update sidebar link active states dynamically
  document.querySelectorAll('#nav-rooms, #nav-faculty, #nav-sections, #nav-subjects').forEach((link) => {
    link?.classList.remove('active');
  });
  const currentNav = document.getElementById(`nav-${tabName}`);
  if (currentNav) {
    currentNav.classList.add('active');
  }

  // 4. Update the top breadcrumb and page title
  const breadcrumbEl = document.getElementById('breadcrumb-page-name');
  const mainTitleEl = document.getElementById('page-main-title');
  if (tabName === 'rooms') {
    if (breadcrumbEl) breadcrumbEl.textContent = 'Rooms';
    if (mainTitleEl) mainTitleEl.textContent = 'Room Availability';
  } else if (tabName === 'faculty') {
    if (breadcrumbEl) breadcrumbEl.textContent = 'Faculty';
    if (mainTitleEl) mainTitleEl.textContent = 'Faculty Management';
  } else if (tabName === 'sections') {
    if (breadcrumbEl) breadcrumbEl.textContent = 'Sections';
    if (mainTitleEl) mainTitleEl.textContent = 'Sections Management';
  } else if (tabName === 'subjects') {
    if (breadcrumbEl) breadcrumbEl.textContent = 'Subjects';
    if (mainTitleEl) mainTitleEl.textContent = 'Curricular Subjects';
  }

  // 5. Update the top "+ Add" button
  const addBtn =
    document.getElementById('btn-add-entity') ||
    document.getElementById('add-entity-btn');
  if (addBtn) {
    if (tabName === 'rooms') {
      addBtn.style.display = 'none'; // Inside rooms, CRUD sub-panel has its own + Add Room button
    } else {
      addBtn.style.display = '';
      const singularName =
        tabName.charAt(0).toUpperCase() + tabName.slice(1).replace(/s$/, '');
      addBtn.textContent = `+ Add ${singularName}`;
      addBtn.setAttribute('data-target-modal', `modal-add-${tabName}`);
    }
  }

  if (tabName === 'rooms') {
    updateRoomAvailabilityBoard();
  }

  if (typeof window.applyRolePermissions === 'function') {
    window.applyRolePermissions(window.CURRENT_ROLE);
  }
}
window.switchTab = switchTab;

function initManageTabs() {
  const tabs = document.querySelectorAll('.tab-btn, .manage-tab-btn');
  const addBtn =
    document.getElementById('btn-add-entity') ||
    document.getElementById('add-entity-btn');

  // Read URL query param ?tab= or hash
  const urlParams = new URLSearchParams(window.location.search);
  const hashTab = window.location.hash
    ? window.location.hash.replace('#', '')
    : null;
  const initialTab = urlParams.get('tab') || hashTab || 'rooms';

  tabs.forEach((tab) => {
    tab?.addEventListener('click', (e) => {
      e.preventDefault();
      const target = tab.dataset?.tab;
      if (target) {
        switchTab(target);
        history.replaceState(null, '', `?tab=${target}`);
      }
    });
  });

  // Activate initial tab on load
  switchTab(initialTab);

  if (initialTab === 'faculty') {
    const viewParam = urlParams.get('view');
    const idParam = urlParams.get('id');
    if (viewParam === 'detailed' || idParam || window.CURRENT_ROLE === 'FACULTY') {
      const targetId = idParam || window.CURRENT_REF_ID || 109;
      setTimeout(() => openFacultyDetailed(targetId), 300);
    }
  }

  if (addBtn) {
    addBtn.addEventListener('click', (e) => {
      e.preventDefault();
      openAddModal(activeTab);
    });
  }
}

// -------------------------------------------------------------
// Data Fetching & Table Rendering
// -------------------------------------------------------------
async function loadAllMasterData() {
  await Promise.all([
    fetchRooms(),
    fetchFaculty(),
    fetchSections(),
    fetchSubjects(),
    fetchSchedulesData(),
  ]);
  populateRoomAvailabilityFilters();
  updateRoomAvailabilityBoard();
  initRoomTimetableSubpanel();
  window.applyRolePermissions(window.CURRENT_ROLE);
}

async function fetchSchedulesData() {
  try {
    const res = await API.get("/api/schedules");
    if (res.status === "success") {
      schedulesCache = res.data || [];
    }
  } catch (err) {
    schedulesCache = [];
  }
}

async function fetchRooms() {
  try {
    const res = await API.get("/api/rooms");
    if (res.status === "success") {
      masterDataCache.rooms = res.data;
      const countEl = document.getElementById("count-rooms");
      if (countEl) countEl.textContent = res.count;
      const kpiTotal = document.getElementById("kpi-rooms-total");
      if (kpiTotal) kpiTotal.textContent = res.count;
      renderRoomsTable(res.data);
    }
  } catch (err) {
    document.getElementById("table-rooms-body").innerHTML =
      `<tr><td colspan="6" style="color:#EF4444; text-align:center;">Failed to load rooms.</td></tr>`;
  }
}

function renderRoomsTable(rooms) {
  const tbody = document.getElementById("table-rooms-body");
  if (!tbody) return;

  if (rooms.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: var(--text-muted); padding: 24px;">No rooms found.</td></tr>`;
    return;
  }

  tbody.innerHTML = rooms
    .map(
      (r) => `
    <tr>
      <td><strong>${escapeHtml(r.room_code)}</strong></td>
      <td>${escapeHtml(r.building || 'COE Building')}</td>
      <td><span class="badge badge-${r.room_type}">${r.room_type}</span></td>
      <td>
        <span class="${r.is_available ? "status-dot-active" : "status-dot-inactive"}">
          ${r.is_available ? "Available" : "Maintenance"}
        </span>
      </td>
      <td>
        <div class="table-actions">
          <button class="btn btn-secondary btn-sm" onclick="switchRoomModeTimetable(${r.id})" style="display:inline-flex; align-items:center; gap:4px;" title="View Room Timetable">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            Schedule
          </button>
          <span class="admin-only" style="display:inline-flex; gap: 4px;">
            <button class="btn btn-secondary btn-sm" onclick="openEditModal('rooms', ${r.id})">Edit</button>
            <button class="btn btn-danger btn-sm" onclick="deleteEntity('rooms', ${r.id})">Delete</button>
          </span>
        </div>
      </td>
    </tr>
  `
    )
    .join("");
}

async function fetchFaculty() {
  try {
    const res = await API.get("/api/faculty");
    if (res.status === "success") {
      masterDataCache.faculty = res.data;
      document.getElementById("count-faculty").textContent = res.count;
      renderFacultyTable(res.data);
    }
  } catch (err) {
    document.getElementById("table-faculty-body").innerHTML =
      `<tr><td colspan="6" style="color:#EF4444; text-align:center;">Failed to load faculty.</td></tr>`;
  }
}

function renderFacultyTable(faculty) {
  const tbody = document.getElementById("table-faculty-body");
  if (!tbody) return;

  if (faculty.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: var(--text-muted); padding: 24px;">No faculty members found.</td></tr>`;
    return;
  }

  tbody.innerHTML = faculty
    .map((f) => {
      const dept = f.department || normalizeProgram(f.program) || "MEE";
      const assigned = f.assigned_subjects || [];
      const assignedHtml = assigned.length > 0
        ? `<div style="display:flex; flex-wrap:wrap; gap:4px; margin-top:5px;">` +
          assigned.map(s => `
            <span style="background: rgba(104,28,46,0.08); color: var(--bulsu-maroon); font-size: 10.5px; font-weight: 700; padding: 2px 7px; border-radius: 4px; display: inline-flex; align-items: center; gap: 4px; border: 1px solid rgba(104,28,46,0.18);">
              ${escapeHtml(s.subject_code || s.code)}
              ${["ADMIN", "CHAIR", "PROG_CHA"].includes(window.CURRENT_ROLE) ? `
                <button type="button" onclick="event.stopPropagation(); unassignSubjectFromFaculty(${f.id}, ${s.subject_id || s.id})" style="border:none; background:none; color:#DC2626; font-weight:800; cursor:pointer; padding:0 2px; font-size:12px; line-height:1;" title="Remove subject">&times;</button>
              ` : ""}
            </span>
          `).join("") +
          `</div>`
        : `<div style="font-size: 11px; color: var(--text-muted); font-style: italic; margin-top: 3px;">No subjects assigned</div>`;

      return `
      <tr>
        <td>
          <strong style="color: var(--text-dark);">${escapeHtml(f.name)}</strong>
          ${assignedHtml}
        </td>
        <td><span style="font-weight: 600; color: var(--text-secondary);">${escapeHtml(dept)}</span></td>
        <td>
          <span style="background: #86EFAC; color: #14532D; font-size: 11px; font-weight: 700; padding: 4px 12px; border-radius: 9999px; text-transform: capitalize;">Active</span>
        </td>
        <td style="text-align: right;">
          <div style="display:flex; justify-content:flex-end; align-items:center; gap: 8px; flex-wrap:wrap;">
            ${["ADMIN", "CHAIR", "PROG_CHA"].includes(window.CURRENT_ROLE) ? `
              <button class="btn btn-primary btn-sm" onclick="openAssignSubjectModal(${f.id})" style="display:inline-flex; align-items:center; gap:4px; font-weight:700; background:var(--bulsu-maroon); color:#FFFFFF; border:none; padding:4px 14px; border-radius:9999px; font-size:11.5px;" title="Assign Subject to Faculty">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                Assign Subject
              </button>
            ` : ""}
            <button class="btn btn-sm" onclick="openFacultyDetailed(${f.id})" style="background: #60A5FA; color: #FFFFFF; font-weight: 600; padding: 4px 18px; border-radius: 9999px; border:none; cursor:pointer;" title="View Faculty Profile">
              About
            </button>
            <a href="/schedules?faculty=${f.id}" class="btn btn-secondary btn-sm" style="display:inline-flex; align-items:center; gap:4px; text-decoration:none;" title="View Faculty Timetable">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
              Schedule
            </a>
            <span class="admin-only" style="display:inline-flex; gap: 4px;">
              <button class="btn btn-secondary btn-sm" onclick="openEditModal('faculty', ${f.id})">Edit</button>
              <button class="btn btn-danger btn-sm" onclick="deleteEntity('faculty', ${f.id})">Delete</button>
            </span>
          </div>
        </td>
      </tr>
    `;
    })
    .join("");
}

// -------------------------------------------------------------
// Faculty Detailed Profile & Availability Controller (Screenshot 2026-10-24 192019.png)
// -------------------------------------------------------------
let _currentDetailedFaculty = null;

window.openFacultyDetailed = async function (facultyId) {
  if (!facultyId) return;
  const dirCont = document.getElementById("faculty-directory-container");
  const detCont = document.getElementById("faculty-detailed-container");
  if (dirCont) dirCont.style.display = "none";
  if (detCont) detCont.style.display = "block";

  const breadcrumbEl = document.getElementById("breadcrumb-page-name");
  const mainTitleEl = document.getElementById("page-main-title");
  if (breadcrumbEl) breadcrumbEl.textContent = "Faculty";
  if (mainTitleEl) mainTitleEl.textContent = "Faculty Detailed";

  const backBtn = document.getElementById("btn-back-to-faculty-list");
  if (backBtn) {
    backBtn.style.display = (window.CURRENT_ROLE === "FACULTY" && !["ADMIN", "CHAIR"].includes(window.AUTHENTIC_USER_ROLE)) ? "none" : "inline-flex";
  }

  try {
    const res = await API.get(`/api/faculty/${facultyId}`);
    if (res.status === "success") {
      const f = res.data;
      _currentDetailedFaculty = f;

      document.getElementById("detailed-faculty-name").textContent = f.name || "Faculty Member";
      document.getElementById("detailed-faculty-dept").textContent = f.department || f.program || "Engineering";
      document.getElementById("detailed-faculty-email").textContent = f.email || "";

      // Check edit permissions: ADMIN, CHAIR, or if the faculty user owns this profile
      const canEdit = ["ADMIN", "CHAIR"].includes(window.CURRENT_ROLE) ||
                      (window.CURRENT_ROLE === "FACULTY" && String(window.CURRENT_REF_ID) === String(f.id));
      const editWrap = document.getElementById("detailed-edit-btn-wrap");
      if (editWrap) {
        editWrap.style.display = canEdit ? "block" : "none";
      }

      // Check assign permissions: ADMIN, CHAIR
      const canAssign = ["ADMIN", "CHAIR", "PROG_CHA"].includes(window.CURRENT_ROLE);
      const assignBtn = document.getElementById("btn-detailed-assign-subject");
      if (assignBtn) {
        assignBtn.style.display = canAssign ? "inline-flex" : "none";
      }

      // 1. Column 1: Subjects
      const subjectsList = document.getElementById("detailed-subjects-list");
      if (subjectsList) {
        const subjects = f.assigned_subjects || [];
        if (subjects.length === 0) {
          subjectsList.innerHTML = `
            <div style="color: #64748B; font-size: 13px; font-style: italic; margin-bottom: 8px;">No subjects assigned yet.</div>
            ${canAssign ? `
              <button type="button" class="btn btn-secondary btn-sm" onclick="openAssignSubjectModal(${f.id})" style="font-size:11.5px;">
                + Assign Subject Offering
              </button>
            ` : ''}
          `;
        } else {
          subjectsList.innerHTML = subjects.map(s => {
            const secText = (s.sections && s.sections.length > 0) ? s.sections.join(", ") : (s.section_name || "");
            const slotText = (s.day_of_week && s.start_time) ? `${s.day_of_week} ${s.start_time}-${s.end_time}` : "";
            const roomText = s.room_code ? `@ ${s.room_code}` : "";
            return `
            <div style="background: rgba(255,255,255,0.7); border: 1px solid rgba(255,255,255,0.6); border-radius: 8px; padding: 10px 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.03); position:relative;">
              <div style="display:flex; justify-content:space-between; align-items:flex-start; gap: 8px;">
                <div>
                  <div style="font-size: 13.5px; font-weight: 800; color: #1E293B;">${escapeHtml(s.code || "")}</div>
                  <div style="font-size: 12px; color: #475569; margin: 2px 0;">${escapeHtml(s.title || "")}</div>
                  <div style="font-size: 11px; font-weight: 700; color: var(--bulsu-maroon);">${s.units || 3} Units &bull; ${escapeHtml(s.subject_type || s.type || "Lecture")}</div>
                </div>
                ${(canAssign && (s.subject_id || s.id || s.schedule_id)) ? `
                  <button type="button" class="btn btn-sm" onclick="unassignSubjectFromFaculty(${f.id}, ${s.subject_id || s.id || 'null'}, ${s.schedule_id || 'null'})" style="color: #DC2626; background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.2); font-size: 10.5px; font-weight: 700; padding: 2px 8px; border-radius: 6px; cursor:pointer;" title="Unassign subject from faculty">
                    Unassign
                  </button>
                ` : ''}
              </div>
              ${(secText || slotText) ? `
                <div style="margin-top: 8px; padding-top: 6px; border-top: 1px solid rgba(0,0,0,0.05); font-size: 11px; color: #64748B; display:flex; justify-content:space-between; flex-wrap:wrap; gap:4px;">
                  ${secText ? `<span style="font-weight:700; color:#3B82F6;">Cohort: ${escapeHtml(secText)}</span>` : ''}
                  ${slotText ? `<span>${escapeHtml(slotText)} ${escapeHtml(roomText)}</span>` : ''}
                </div>
              ` : ''}
            </div>
            `;
          }).join("");
        }
      }

      // 2. Column 2: Availability (Monday - Saturday)
      const availList = document.getElementById("detailed-availability-list");
      if (availList) {
        const days = [
          { code: "MON", label: "Monday" },
          { code: "TUE", label: "Tuesday" },
          { code: "WED", label: "Wednesday" },
          { code: "THU", label: "Thursday" },
          { code: "FRI", label: "Friday" },
          { code: "SAT", label: "Saturday" },
        ];
        const avails = f.availabilities || [];

        availList.innerHTML = days.map(d => {
          const match = avails.find(a => a.day_of_week === d.code);
          let badgeHtml = "";
          if (match) {
            if (match.is_preferred) {
              badgeHtml = `<span style="background: #C7D2FE; color: #3730A3; font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 9999px;">Preferred (${match.start_time.slice(0,5)}–${match.end_time.slice(0,5)})</span>`;
            } else {
              badgeHtml = `<span style="background: #FECACA; color: #991B1B; font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 9999px;">Unavailable (${match.start_time.slice(0,5)}–${match.end_time.slice(0,5)})</span>`;
            }
          } else {
            badgeHtml = `<span style="background: #86EFAC; color: #14532D; font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 9999px;">Available</span>`;
          }

          return `
            <div style="display:flex; justify-content:space-between; align-items:center; padding: 6px 0; border-bottom: 1px solid rgba(0,0,0,0.05);">
              <span style="font-size: 13.5px; font-weight: 600; color: #334155;">${d.label}</span>
              ${badgeHtml}
            </div>
          `;
        }).join("");
      }

      // 3. Column 3: Preferred & Current Load & Session Preference
      const maxU = f.max_units || 21;
      const curU = f.current_units || 0;
      const prefEl = document.getElementById("detailed-preferred-units");
      const prefBar = document.getElementById("detailed-preferred-bar");
      const curEl = document.getElementById("detailed-current-units");
      const curBar = document.getElementById("detailed-current-bar");
      const prefSessionBadge = document.getElementById("detailed-session-pref-badge");

      if (prefEl) prefEl.textContent = maxU;
      if (prefBar) prefBar.style.width = `${Math.min(100, Math.round((maxU / 24) * 100))}%`;
      if (curEl) curEl.textContent = curU;
      if (curBar) curBar.style.width = `${Math.min(100, Math.round((curU / maxU) * 100))}%`;

      if (prefSessionBadge) {
        const isStraight = f.preferred_session_type === "STRAIGHT";
        prefSessionBadge.textContent = isStraight ? "3-Hr Straight Block" : "2x 1.5-Hr Split";
        prefSessionBadge.style.background = isStraight ? "#FEF3C7" : "#EDE9FE";
        prefSessionBadge.style.color = isStraight ? "#92400E" : "#6D28D9";
      }
    }
  } catch (err) {
    showToast(err.message || "Failed to load faculty details", true);
  }
};

window.closeFacultyDetailed = function () {
  const dirCont = document.getElementById("faculty-directory-container");
  const detCont = document.getElementById("faculty-detailed-container");
  if (dirCont) dirCont.style.display = "block";
  if (detCont) detCont.style.display = "none";

  const mainTitleEl = document.getElementById("page-main-title");
  if (mainTitleEl) mainTitleEl.textContent = "Faculty Status";
};

window.openFacultyDetailedEditModal = function () {
  if (!_currentDetailedFaculty) return;
  const f = _currentDetailedFaculty;
  document.getElementById("edit-fac-name").value = f.name || "";
  document.getElementById("edit-fac-email").value = f.email || "";
  document.getElementById("edit-fac-max-units").value = f.max_units || 21;
  const sessPref = document.getElementById("edit-fac-session-pref");
  if (sessPref) sessPref.value = f.preferred_session_type || "SPLIT";

  const daysList = document.getElementById("edit-fac-days-list");
  if (daysList) {
    const days = [
      { code: "MON", label: "Monday" },
      { code: "TUE", label: "Tuesday" },
      { code: "WED", label: "Wednesday" },
      { code: "THU", label: "Thursday" },
      { code: "FRI", label: "Friday" },
      { code: "SAT", label: "Saturday" },
    ];
    const avails = f.availabilities || [];
    daysList.innerHTML = days.map(d => {
      const match = avails.find(a => a.day_of_week === d.code);
      const isBlackout = match && !match.is_preferred;
      return `
        <div style="display:grid; grid-template-columns: 85px 1.2fr 1fr 1fr; gap: 8px; align-items:center; background:#F8FAFC; padding: 6px 10px; border-radius: 6px; border: 1px solid #E2E8F0;">
          <span style="font-size: 12px; font-weight: 700; color: #334155;">${d.label}</span>
          <select id="edit-avail-type-${d.code}" class="form-select" style="font-size: 11.5px; padding: 4px;">
            <option value="available" ${!match ? "selected" : ""}>Available</option>
            <option value="blackout" ${isBlackout ? "selected" : ""}>Unavailable</option>
            <option value="preferred" ${match && match.is_preferred ? "selected" : ""}>Preferred</option>
          </select>
          <input type="time" id="edit-avail-start-${d.code}" class="form-input" value="${match ? match.start_time.slice(0,5) : "08:00"}" style="font-size: 11.5px; padding: 4px;">
          <input type="time" id="edit-avail-end-${d.code}" class="form-input" value="${match ? match.end_time.slice(0,5) : "12:00"}" style="font-size: 11.5px; padding: 4px;">
        </div>
      `;
    }).join("");
  }

  const modal = document.getElementById("modal-edit-faculty-detailed");
  if (modal) modal.style.display = "flex";
};

window.closeFacultyDetailedEditModal = function () {
  const modal = document.getElementById("modal-edit-faculty-detailed");
  if (modal) modal.style.display = "none";
};

window.submitFacultyDetailedEdit = async function (e) {
  e.preventDefault();
  if (!_currentDetailedFaculty) return;
  const facultyId = _currentDetailedFaculty.id;
  const name = document.getElementById("edit-fac-name").value.trim();
  const email = document.getElementById("edit-fac-email").value.trim();
  const maxUnits = parseInt(document.getElementById("edit-fac-max-units").value, 10);
  const sessionPref = document.getElementById("edit-fac-session-pref")?.value || "SPLIT";

  const days = ["MON", "TUE", "WED", "THU", "FRI", "SAT"];
  const availability = [];
  days.forEach(code => {
    const type = document.getElementById(`edit-avail-type-${code}`)?.value;
    if (type === "blackout" || type === "preferred") {
      const st = document.getElementById(`edit-avail-start-${code}`)?.value || "08:00";
      const et = document.getElementById(`edit-avail-end-${code}`)?.value || "12:00";
      availability.push({
        day_of_week: code,
        start_time: st,
        end_time: et,
        is_preferred: type === "preferred"
      });
    }
  });

  try {
    const res = await API.put(`/api/faculty/${facultyId}`, {
      name,
      email,
      max_units: maxUnits,
      preferred_session_type: sessionPref,
      availability
    });
    showToast(res.message || "Profile & availability updated successfully!");
    closeFacultyDetailedEditModal();
    await fetchFaculty();
    await openFacultyDetailed(facultyId);
  } catch (err) {
    showToast(err.message || "Failed to update profile", true);
  }
};

async function fetchSections() {
  try {
    let url = "/api/master/sections";
    if (window.CURRENT_ROLE === "FACULTY" && window.CURRENT_REF_ID) {
      url += `?faculty_id=${window.CURRENT_REF_ID}`;
    }
    const res = await API.get(url);
    if (res.status === "success") {
      masterDataCache.sections = res.data;
      document.getElementById("count-sections").textContent = res.count;
      renderSectionsTable(res.data);
    }
  } catch (err) {
    document.getElementById("table-sections-body").innerHTML =
      `<tr><td colspan="5" style="color:#EF4444; text-align:center;">Failed to load sections.</td></tr>`;
  }
}

function renderSectionsTable(sections) {
  const tbody = document.getElementById("table-sections-body");
  if (!tbody) return;

  if (sections.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color: var(--text-muted); padding: 24px;">No cohort sections found.</td></tr>`;
    return;
  }

  tbody.innerHTML = sections
    .map(
      (s) => `
    <tr>
      <td><strong>${escapeHtml(s.name)}</strong></td>
      <td>${escapeHtml(s.program)}</td>
      <td>Year ${s.year_level}</td>
      <td>
        <div style="display:inline-flex; align-items:center; gap:6px; font-weight:500; color:var(--text-dark, #1e293b); background:#f8fafc; padding:4px 10px; border-radius:6px; font-size:12.5px; border:1px solid #e2e8f0;">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
          <span>${escapeHtml(s.class_mayor || "Unassigned")}</span>
        </div>
      </td>
      <td>
        <div class="table-actions">
          <a href="/schedules?section=${s.id}" class="btn btn-secondary btn-sm" style="display:inline-flex; align-items:center; gap:4px; text-decoration:none;" title="View Section Timetable">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            View Section Schedule
          </a>
          <span class="admin-only" style="display:inline-flex; gap: 4px;">
            <button class="btn btn-secondary btn-sm" onclick="openEditModal('sections', ${s.id})">Edit</button>
            <button class="btn btn-danger btn-sm" onclick="deleteEntity('sections', ${s.id})">Delete</button>
          </span>
        </div>
      </td>
    </tr>
  `
    )
    .join("");
}

let _facultyCurriculumMode = false;

window.toggleFacultyCurriculumView = function () {
  _facultyCurriculumMode = !_facultyCurriculumMode;
  const toggleBtn = document.getElementById("btn-toggle-faculty-curriculum");
  if (toggleBtn) {
    toggleBtn.textContent = _facultyCurriculumMode ? "👨‍🏫 View My Assigned Subjects" : "📚 View Full Curriculum";
  }
  fetchSubjects();
};

async function fetchSubjects() {
  const isFaculty = window.CURRENT_ROLE === "FACULTY";
  const toggleBtn = document.getElementById("btn-toggle-faculty-curriculum");
  if (toggleBtn) {
    toggleBtn.style.display = isFaculty ? "inline-flex" : "none";
  }

  try {
    let url = "/api/master/subjects";
    if (isFaculty && window.CURRENT_REF_ID) {
      if (_facultyCurriculumMode) {
        url += "?curriculum=true";
      } else {
        url += `?faculty_id=${window.CURRENT_REF_ID}`;
      }
    }
    const res = await API.get(url);
    if (res.status === "success") {
      masterDataCache.subjects = res.data;
      document.getElementById("count-subjects").textContent = res.count;
      renderSubjectsTable(res.data);
    }
  } catch (err) {
    document.getElementById("table-subjects-body").innerHTML =
      `<tr><td colspan="6" style="color:#EF4444; text-align:center;">Failed to load subjects.</td></tr>`;
  }
}

function getSubjectClassification(sub) {
  if (sub.classification) return sub.classification;
  const c = (sub.code || "").trim().toUpperCase();
  const p = (sub.program || "").trim().toUpperCase();
  const m = c.match(/([1-4])\d\d/);
  const yr = m ? parseInt(m[1], 10) : (sub.year_level || 1);
  if (yr >= 3) return "MAJOR";
  if (c.startsWith("COE")) return "MAJOR";
  if (p === "GEN" || p === "GENERAL" || p === "GENERAL ENGINEERING") return "MINOR";
  return "MAJOR";
}

function renderSubjectsTable(subjects) {
  const tbody = document.getElementById("table-subjects-body");
  if (!tbody) return;

  if (subjects.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color: var(--text-muted); padding: 24px;">No curricular subjects found.</td></tr>`;
    return;
  }

  tbody.innerHTML = subjects
    .map(
      (sub) => {
        const cls = getSubjectClassification(sub);
        const isMajor = cls === "MAJOR";
        const badgeStyle = isMajor
          ? "background: rgba(104, 28, 46, 0.1); color: var(--bulsu-maroon); border: 1px solid rgba(104, 28, 46, 0.25); font-weight: 700; padding: 2px 8px; border-radius: 6px; font-size: 11px; display: inline-flex; align-items: center; gap: 4px;"
          : "background: rgba(217, 119, 6, 0.1); color: #B45309; border: 1px solid rgba(217, 119, 6, 0.25); font-weight: 700; padding: 2px 8px; border-radius: 6px; font-size: 11px; display: inline-flex; align-items: center; gap: 4px;";
        const badgeIcon = isMajor ? "★" : "○";
        const badgeLabel = isMajor ? "Major" : "Minor";

        return `
    <tr>
      <td><strong>${escapeHtml(sub.code)}</strong></td>
      <td>${escapeHtml(sub.title)}</td>
      <td>
        <span class="badge" style="${badgeStyle}">
          <span>${badgeIcon}</span> ${badgeLabel}
        </span>
      </td>
      <td>${sub.units} u</td>
      <td><span class="badge badge-${sub.subject_type}">${sub.subject_type}</span></td>
      <td>${sub.hours_per_week} hrs/wk</td>
      <td>
        <div class="table-actions admin-only">
          <button class="btn btn-secondary btn-sm" onclick="openEditModal('subjects', ${sub.id})">Edit</button>
          <button class="btn btn-danger btn-sm" onclick="deleteEntity('subjects', ${sub.id})">Delete</button>
        </div>
      </td>
    </tr>
  `;
      }
    )
    .join("");
}

// -------------------------------------------------------------
// Standard Reusable Action Modal System
// -------------------------------------------------------------
let currentModalEntity = null;
let currentModalId = null;

function initModalHandlers() {
  const backdrop = document.getElementById("manage-modal-backdrop");
  const closeBtn = document.getElementById("modal-close-btn");
  const cancelBtn = document.getElementById("modal-cancel-btn");
  const form = document.getElementById("manage-modal-form");

  function closeModal() {
    backdrop.classList.remove("open");
    currentModalEntity = null;
    currentModalId = null;
  }

  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
  if (backdrop) {
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) closeModal();
    });
  }

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      await handleModalSubmit();
    });
  }
}

function openAddModal(entity) {
  currentModalEntity = entity;
  currentModalId = null;

  const titles = {
    rooms: "Add New Room / Laboratory",
    faculty: "Add Faculty Member",
    sections: "Add Cohort Section",
    subjects: "Add Curricular Subject",
  };
  document.getElementById("modal-title").textContent = titles[entity] || "Add Entity";
  buildModalForm(entity, null);
  document.getElementById("manage-modal-backdrop").classList.add("open");
}
window.openAddModal = openAddModal;

window.openEditModal = function (entity, id) {
  currentModalEntity = entity;
  currentModalId = id;

  const record = masterDataCache[entity]?.find((item) => item.id === id);
  if (!record) {
    showToast("Record not found", true);
    return;
  }

  const titles = {
    rooms: `Edit Room: ${record.room_code}`,
    faculty: `Edit Faculty: ${record.name}`,
    sections: `Edit Section: ${record.name}`,
    subjects: `Edit Subject: ${record.code}`,
  };
  document.getElementById("modal-title").textContent = titles[entity] || "Edit Entity";
  buildModalForm(entity, record);
  document.getElementById("manage-modal-backdrop").classList.add("open");
};

function buildModalForm(entity, data = null) {
  const container = document.getElementById("modal-fields-container");
  container.innerHTML = "";

  if (entity === "rooms") {
    container.innerHTML = `
      <div class="form-field">
        <label class="form-label" for="inp-room-code">Room Code *</label>
        <input class="form-input" id="inp-room-code" name="room_code" required placeholder="e.g. Eng-204" value="${data ? escapeHtml(data.room_code) : ""}">
        <span class="form-error" id="err-room_code"></span>
      </div>
      <div class="form-field">
        <label class="form-label" for="inp-room-type">Room Type *</label>
        <select class="form-select" id="inp-room-type" name="room_type">
          <option value="LECTURE" ${data && data.room_type === "LECTURE" ? "selected" : ""}>LECTURE</option>
          <option value="LAB" ${data && data.room_type === "LAB" ? "selected" : ""}>LAB</option>
        </select>
      </div>
      <div class="form-field">
        <label class="form-label" for="inp-available">Availability Status</label>
        <select class="form-select" id="inp-available" name="is_available">
          <option value="true" ${!data || data.is_available ? "selected" : ""}>Available</option>
          <option value="false" ${data && !data.is_available ? "selected" : ""}>Under Maintenance</option>
        </select>
      </div>
    `;
  } else if (entity === "faculty") {
    container.innerHTML = `
      <div class="form-field">
        <label class="form-label" for="inp-fac-name">Full Name *</label>
        <input class="form-input" id="inp-fac-name" name="name" required placeholder="e.g. Engr. John Doe" value="${data ? escapeHtml(data.name) : ""}">
        <span class="form-error" id="err-name"></span>
      </div>
      <div class="form-field">
        <label class="form-label" for="inp-fac-email">BulSU Email *</label>
        <input class="form-input" type="email" id="inp-fac-email" name="email" required placeholder="e.g. john.doe@bulsu.edu.ph" value="${data ? escapeHtml(data.email) : ""}">
        <span class="form-error" id="err-email"></span>
      </div>
      <div class="form-field">
        <label class="form-label" for="inp-max-units">Max Teaching Units *</label>
        <input class="form-input" type="number" id="inp-max-units" name="max_units" min="1" max="40" required placeholder="Default 21" value="${data ? data.max_units : "21"}">
        <span class="form-error" id="err-max_units"></span>
      </div>
    `;
  } else if (entity === "sections") {
    container.innerHTML = `
      <div class="form-field">
        <label class="form-label" for="inp-sec-name">Section Identifier *</label>
        <input class="form-input" id="inp-sec-name" name="name" required placeholder="e.g. CpE 2A" value="${data ? escapeHtml(data.name) : ""}">
        <span class="form-error" id="err-name"></span>
      </div>
      <div class="form-field">
        <label class="form-label" for="inp-sec-prog">Degree Program *</label>
        <input class="form-input" id="inp-sec-prog" name="program" required placeholder="e.g. BSCpE" value="${data ? escapeHtml(data.program) : "BSCpE"}">
      </div>
      <div class="form-field">
        <label class="form-label" for="inp-year-level">Year Level *</label>
        <select class="form-select" id="inp-year-level" name="year_level">
          <option value="1" ${data && data.year_level === 1 ? "selected" : ""}>Year 1</option>
          <option value="2" ${data && data.year_level === 2 ? "selected" : ""}>Year 2</option>
          <option value="3" ${data && data.year_level === 3 ? "selected" : ""}>Year 3</option>
          <option value="4" ${data && data.year_level === 4 ? "selected" : ""}>Year 4</option>
        </select>
      </div>
      <div class="form-field">
        <label class="form-label" for="inp-class-mayor">Class Mayor</label>
        <input class="form-input" id="inp-class-mayor" name="class_mayor" placeholder="e.g. Juan Dela Cruz" value="${data && data.class_mayor ? escapeHtml(data.class_mayor) : ""}">
      </div>
    `;
  } else if (entity === "subjects") {
    container.innerHTML = `
      <div class="form-field">
        <label class="form-label" for="inp-sub-code">Subject Code *</label>
        <input class="form-input" id="inp-sub-code" name="code" required placeholder="e.g. CPE 211" value="${data ? escapeHtml(data.code) : ""}">
        <span class="form-error" id="err-code"></span>
      </div>
      <div class="form-field">
        <label class="form-label" for="inp-sub-title">Descriptive Title *</label>
        <input class="form-input" id="inp-sub-title" name="title" required placeholder="e.g. Data Structures & Algorithms" value="${data ? escapeHtml(data.title) : ""}">
        <span class="form-error" id="err-title"></span>
      </div>
      <div class="form-field">
        <label class="form-label" for="inp-units">Credit Units *</label>
        <input class="form-input" type="number" id="inp-units" name="units" min="1" max="10" required placeholder="e.g. 3" value="${data ? data.units : "3"}">
        <span class="form-error" id="err-units"></span>
      </div>
      <div class="form-field">
        <label class="form-label" for="inp-sub-type">Subject Type *</label>
        <select class="form-select" id="inp-sub-type" name="subject_type">
          <option value="LECTURE" ${data && data.subject_type === "LECTURE" ? "selected" : ""}>LECTURE</option>
          <option value="LAB" ${data && data.subject_type === "LAB" ? "selected" : ""}>LAB</option>
        </select>
      </div>
      <div class="form-field">
        <label class="form-label" for="inp-hours">Hours Per Week *</label>
        <input class="form-input" type="number" id="inp-hours" name="hours_per_week" min="1" max="20" required placeholder="e.g. 3" value="${data ? data.hours_per_week : "3"}">
        <span class="form-error" id="err-hours_per_week"></span>
      </div>
    `;
  }
}

async function handleModalSubmit() {
  const form = document.getElementById("manage-modal-form");
  const formData = new FormData(form);
  const payload = {};

  formData.forEach((val, key) => {
    payload[key] = val;
  });

  // Real-time client-side validation
  let hasError = false;
  document.querySelectorAll(".form-error").forEach((el) => {
    el.style.display = "none";
    el.textContent = "";
  });

  if (currentModalEntity === "rooms") {
    if (!payload.room_code || !payload.room_code.trim()) {
      showFieldError("room_code", "Room code is required.");
      hasError = true;
    }
    payload.is_available = payload.is_available === "true";
  } else if (currentModalEntity === "faculty") {
    if (!payload.name || !payload.name.trim()) {
      showFieldError("name", "Name is required.");
      hasError = true;
    }
    if (!payload.email || !payload.email.includes("@")) {
      showFieldError("email", "Valid email address required.");
      hasError = true;
    }
    const mu = parseInt(payload.max_units);
    if (isNaN(mu) || mu <= 0) {
      showFieldError("max_units", "Max units must be greater than 0.");
      hasError = true;
    }
  } else if (currentModalEntity === "sections") {
    if (!payload.name || !payload.name.trim()) {
      showFieldError("name", "Section name is required.");
      hasError = true;
    }
  } else if (currentModalEntity === "subjects") {
    if (!payload.code || !payload.code.trim()) {
      showFieldError("code", "Subject code is required.");
      hasError = true;
    }
    if (!payload.title || !payload.title.trim()) {
      showFieldError("title", "Descriptive title is required.");
      hasError = true;
    }
    const u = parseInt(payload.units);
    if (isNaN(u) || u <= 0) {
      showFieldError("units", "Units must be greater than 0.");
      hasError = true;
    }
    const hpw = parseInt(payload.hours_per_week);
    if (isNaN(hpw) || hpw <= 0) {
      showFieldError("hours_per_week", "Hours per week must be greater than 0.");
      hasError = true;
    }
  }

  if (hasError) return;

  const saveBtn = document.getElementById("modal-save-btn");
  saveBtn.disabled = true;
  saveBtn.textContent = "Saving...";

  try {
    const isEdit = currentModalId !== null;
    const url = isEdit
      ? `/api/${currentModalEntity}/${currentModalId}`
      : `/api/${currentModalEntity}`;

    const res = isEdit
      ? await API.put(url, payload)
      : await API.post(url, payload);

    showToast(res.message || "Record saved successfully!");
    document.getElementById("manage-modal-backdrop").classList.remove("open");

    // Refresh specific table view
    if (currentModalEntity === "rooms") await fetchRooms();
    else if (currentModalEntity === "faculty") await fetchFaculty();
    else if (currentModalEntity === "sections") await fetchSections();
    else if (currentModalEntity === "subjects") await fetchSubjects();
  } catch (err) {
    showToast(err.message || "Failed to save record.", true);
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = "Save Changes";
  }
}

function showFieldError(fieldName, msg) {
  const el = document.getElementById(`err-${fieldName}`);
  if (el) {
    el.textContent = msg;
    el.style.display = "block";
  }
}

window.deleteEntity = async function (entity, id) {
  const labels = {
    rooms: "room",
    faculty: "faculty member",
    sections: "section",
    subjects: "subject",
  };
  const label = labels[entity] || "item";

  if (!confirm(`Are you sure you want to delete this ${label}?`)) return;

  try {
    const res = await API.delete(`/api/${entity}/${id}`);
    showToast(res.message || `${label} deleted successfully.`);

    if (entity === "rooms") await fetchRooms();
    else if (entity === "faculty") await fetchFaculty();
    else if (entity === "sections") await fetchSections();
    else if (entity === "subjects") await fetchSubjects();
  } catch (err) {
    showToast(err.message || `Failed to delete ${label}.`, true);
  }
};

// -------------------------------------------------------------
// Client-side Debouncing & In-Memory Filtering (300ms)
// -------------------------------------------------------------
function debounce(fn, delay = 300) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

function initTableFilters() {
  // Rooms Filter
  const sRooms = document.getElementById("search-rooms");
  const fRoomType = document.getElementById("filter-room-type");
  const fRoomStatus = document.getElementById("filter-room-status");

  function applyRoomsFilter() {
    const q = (sRooms?.value || "").toLowerCase().trim();
    const t = fRoomType?.value || "";
    const s = fRoomStatus?.value || "";

    const filtered = masterDataCache.rooms.filter((r) => {
      if (q && !r.room_code.toLowerCase().includes(q)) return false;
      if (t && r.room_type !== t) return false;
      if (s && String(r.is_available) !== s) return false;
      return true;
    });
    renderRoomsTable(filtered);
    window.applyRolePermissions(window.CURRENT_ROLE);
  }

  sRooms?.addEventListener("input", debounce(applyRoomsFilter, 300));
  fRoomType?.addEventListener("change", applyRoomsFilter);
  fRoomStatus?.addEventListener("change", applyRoomsFilter);

  // Faculty Filter
  const sFaculty = document.getElementById("search-faculty");
  const fFacultyStatus = document.getElementById("filter-faculty-status");
  const fFacultyProg = document.getElementById("filter-faculty-prog");

  function applyFacultyFilter() {
    const q = (sFaculty?.value || "").toLowerCase().trim();
    const st = fFacultyStatus?.value || "";
    const p = fFacultyProg?.value || "";

    const filtered = masterDataCache.faculty.filter((f) => {
      if (q && !f.name.toLowerCase().includes(q) && !f.email.toLowerCase().includes(q)) return false;
      if (st === "normal" && f.current_units > f.max_units) return false;
      if (st === "overloaded" && f.current_units <= f.max_units) return false;
      if (p && normalizeProgram(f.program) !== normalizeProgram(p)) return false;
      return true;
    });
    renderFacultyTable(filtered);
    window.applyRolePermissions(window.CURRENT_ROLE);
  }

  sFaculty?.addEventListener("input", debounce(applyFacultyFilter, 300));
  fFacultyStatus?.addEventListener("change", applyFacultyFilter);
  fFacultyProg?.addEventListener("change", applyFacultyFilter);

  // Sections Filter
  const sSections = document.getElementById("search-sections");
  const fSecProg = document.getElementById("filter-section-prog");
  const fSecYear = document.getElementById("filter-section-year");

  function applySectionsFilter() {
    const q = (sSections?.value || "").toLowerCase().trim();
    const p = fSecProg?.value || "";
    const y = fSecYear?.value || "";

    const filtered = masterDataCache.sections.filter((sec) => {
      if (
        q &&
        !sec.name.toLowerCase().includes(q) &&
        !(sec.class_mayor && sec.class_mayor.toLowerCase().includes(q))
      )
        return false;
      if (p && normalizeProgram(sec.program) !== normalizeProgram(p)) return false;
      if (y && String(sec.year_level) !== y) return false;
      return true;
    });
    renderSectionsTable(filtered);
    window.applyRolePermissions(window.CURRENT_ROLE);
  }

  sSections?.addEventListener("input", debounce(applySectionsFilter, 300));
  fSecProg?.addEventListener("change", applySectionsFilter);
  fSecYear?.addEventListener("change", applySectionsFilter);

  // Subjects Filter
  const sSubjects = document.getElementById("search-subjects");
  const fSubjClass = document.getElementById("filter-subject-class");
  const fSubjType = document.getElementById("filter-subject-type");
  const fSubjUnits = document.getElementById("filter-subject-units");
  const fSubjProg = document.getElementById("filter-subject-prog");
  const fSubjYear = document.getElementById("filter-subject-year");

  function applySubjectsFilter() {
    const q = (sSubjects?.value || "").toLowerCase().trim();
    const c = fSubjClass?.value || "";
    const t = fSubjType?.value || "";
    const u = fSubjUnits?.value || "";
    const p = fSubjProg?.value || "";
    const y = fSubjYear?.value || "";

    const filtered = masterDataCache.subjects.filter((sub) => {
      if (q && !sub.code.toLowerCase().includes(q) && !sub.title.toLowerCase().includes(q)) return false;
      if (c && getSubjectClassification(sub) !== c) return false;
      if (t && sub.subject_type !== t) return false;
      if (u && String(sub.units) !== u) return false;
      if (p && normalizeProgram(sub.program) !== normalizeProgram(p)) return false;
      if (y && String(sub.year_level) !== y) return false;
      return true;
    });
    renderSubjectsTable(filtered);
    window.applyRolePermissions(window.CURRENT_ROLE);
  }

  sSubjects?.addEventListener("input", debounce(applySubjectsFilter, 300));
  fSubjClass?.addEventListener("change", applySubjectsFilter);
  fSubjType?.addEventListener("change", applySubjectsFilter);
  fSubjUnits?.addEventListener("change", applySubjectsFilter);
  fSubjProg?.addEventListener("change", applySubjectsFilter);
  fSubjYear?.addEventListener("change", applySubjectsFilter);
}

function normalizeProgram(prog) {
  if (!prog) return "";
  const p = prog.trim().toUpperCase();
  if (p === "BSCE" || p === "CE") return "CE";
  if (p === "BSCPE" || p === "CPE") return "CPE";
  if (p === "BSEE" || p === "EE") return "EE";
  if (p === "BSECE" || p === "ECE") return "ECE";
  if (p === "BSIE" || p === "IE") return "IE";
  if (p === "BSMFGE" || p === "BSMFE" || p === "MFGE" || p === "MFE") return "MFGE";
  if (p === "BSME" || p === "ME") return "ME";
  if (p === "BSMEE" || p === "MEE") return "MEE";
  if (p === "GEN" || p === "GENERAL") return "GEN";
  return p;
}

// -------------------------------------------------------------
// Faculty Availability Modal (Workflow 2)
// -------------------------------------------------------------
window.openFacultyAvailabilityModal = async function (facultyId, facultyName) {
  const backdrop = document.getElementById("manage-modal-backdrop");
  const title = document.getElementById("modal-title");
  const container = document.getElementById("modal-fields-container");
  const saveBtn = document.getElementById("modal-save-btn");
  const cancelBtn = document.getElementById("modal-cancel-btn");

  title.textContent = `Faculty Availability: ${facultyName}`;
  saveBtn.style.display = "none";
  cancelBtn.textContent = "Done / Close";

  container.innerHTML = `<div style="text-align:center; padding: 20px;">Loading availability records…</div>`;
  backdrop.classList.add("open");

  async function loadAvailabilityList() {
    try {
      const res = await API.getFacultyAvailability(facultyId);
      const avails = res.data || [];

      container.innerHTML = `
        <div style="margin-bottom: 16px;">
          <p style="font-size:12.5px; color:var(--text-secondary); margin-bottom:12px;">
            Configure preferred teaching windows or blackout/unavailability hours. Hard-constraint checks will flag any schedule placed during blackout periods.
          </p>

          <div style="border: 1px solid var(--border-light); border-radius: var(--radius-sm); overflow:hidden; margin-bottom:18px;">
            <table style="width:100%; border-collapse:collapse; font-size:12.5px;">
              <thead style="background:var(--bg-main); border-bottom:1px solid var(--border-light);">
                <tr>
                  <th style="padding:8px 12px; text-align:left;">Day</th>
                  <th style="padding:8px 12px; text-align:left;">Time Window</th>
                  <th style="padding:8px 12px; text-align:left;">Type</th>
                  <th style="padding:8px 12px; text-align:right;">Action</th>
                </tr>
              </thead>
              <tbody id="avail-table-body">
                ${avails.length === 0 ? `
                  <tr><td colspan="4" style="padding:16px; text-align:center; color:var(--text-muted);">No availability windows specified. Fully available.</td></tr>
                ` : avails.map(a => `
                  <tr style="border-bottom:1px solid var(--border-subtle);">
                    <td style="padding:8px 12px; font-weight:600;">${a.day_of_week}</td>
                    <td style="padding:8px 12px;">${a.start_time?.slice(0,5)} – ${a.end_time?.slice(0,5)}</td>
                    <td style="padding:8px 12px;">
                      <span class="badge ${a.is_preferred ? "badge-LECTURE" : "badge-danger"}" style="font-size:11px;">
                        ${a.is_preferred ? "Preferred" : "Blackout / Unavailable"}
                      </span>
                    </td>
                    <td style="padding:8px 12px; text-align:right;">
                      <button type="button" class="btn btn-danger btn-sm" onclick="removeAvailability(${a.id})" style="padding:3px 8px !important; font-size:11px !important;">
                        Remove
                      </button>
                    </td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>

          <!-- Mini Add Availability Window Form -->
          <div style="background:var(--bg-main); border:1px solid var(--border-light); border-radius:var(--radius-sm); padding:14px;">
            <h4 style="font-size:13px; font-weight:700; margin-bottom:10px; color:var(--text-main);">+ Add Availability Window</h4>
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px; margin-bottom:10px;">
              <div>
                <label style="font-size:11px; font-weight:600; display:block; margin-bottom:4px;">Day of Week</label>
                <select id="avail-day" class="form-select" style="font-size:12px; padding:6px 10px;">
                  <option value="MON">Monday</option>
                  <option value="TUE">Tuesday</option>
                  <option value="WED">Wednesday</option>
                  <option value="THU">Thursday</option>
                  <option value="FRI">Friday</option>
                  <option value="SAT">Saturday</option>
                </select>
              </div>
              <div>
                <label style="font-size:11px; font-weight:600; display:block; margin-bottom:4px;">Window Type</label>
                <select id="avail-pref" class="form-select" style="font-size:12px; padding:6px 10px;">
                  <option value="false">Blackout / Unavailable</option>
                  <option value="true">Preferred Window</option>
                </select>
              </div>
            </div>
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px; margin-bottom:12px;">
              <div>
                <label style="font-size:11px; font-weight:600; display:block; margin-bottom:4px;">Start Time</label>
                <input type="time" id="avail-start" class="form-input" value="08:00" style="font-size:12px; padding:6px 10px;">
              </div>
              <div>
                <label style="font-size:11px; font-weight:600; display:block; margin-bottom:4px;">End Time</label>
                <input type="time" id="avail-end" class="form-input" value="12:00" style="font-size:12px; padding:6px 10px;">
              </div>
            </div>
            <button type="button" id="btn-save-avail" class="btn btn-primary btn-sm" style="width:100%;">
              Save Availability Window
            </button>
          </div>
        </div>
      `;

      document.getElementById("btn-save-avail")?.addEventListener("click", async () => {
        const day = document.getElementById("avail-day").value;
        const pref = document.getElementById("avail-pref").value === "true";
        const st = document.getElementById("avail-start").value;
        const et = document.getElementById("avail-end").value;

        if (!st || !et) {
          showToast("Please enter valid start and end times", true);
          return;
        }

        try {
          await API.createFacultyAvailability(facultyId, {
            day_of_week: day,
            start_time: st,
            end_time: et,
            is_preferred: pref,
          });
          showToast("Availability window saved.");
          await loadAvailabilityList();
        } catch (err) {
          showToast(err.message || "Failed to save window", true);
        }
      });

    } catch (err) {
      container.innerHTML = `<div style="color:#EF4444; padding:20px; text-align:center;">Failed to load availability: ${err.message}</div>`;
    }
  }

  window.removeAvailability = async function (availId) {
    if (!confirm("Remove this availability window?")) return;
    try {
      await API.deleteFacultyAvailability(availId);
      showToast("Availability window removed.");
      await loadAvailabilityList();
    } catch (err) {
      showToast(err.message || "Failed to delete window", true);
    }
  };

  await loadAvailabilityList();
};

function escapeAttr(str) {
  if (!str) return "";
  return String(str).replace(/'/g, "\\'").replace(/"/g, "&quot;");
}

// -------------------------------------------------------------
// PART 4: Room Availability Dashboard & View Switcher Controller
// -------------------------------------------------------------
function initRoomModeSwitcher() {
  const btnAvail = document.getElementById("btn-mode-availability");
  const btnTime = document.getElementById("btn-mode-timetable");
  const btnCrud = document.getElementById("btn-mode-crud");

  const panelAvail = document.getElementById("room-subpanel-availability");
  const panelTime = document.getElementById("room-subpanel-timetable");
  const panelCrud = document.getElementById("room-subpanel-crud");

  window.setRoomMode = function (mode) {
    currentRoomMode = mode;
    btnAvail?.classList.toggle("active", mode === "availability");
    btnTime?.classList.toggle("active", mode === "timetable");
    btnCrud?.classList.toggle("active", mode === "crud");

    if (panelAvail) panelAvail.style.display = mode === "availability" ? "block" : "none";
    if (panelTime) panelTime.style.display = mode === "timetable" ? "block" : "none";
    if (panelCrud) panelCrud.style.display = mode === "crud" ? "block" : "none";

    if (mode === "availability") {
      updateRoomAvailabilityBoard();
    } else if (mode === "timetable") {
      renderRoomTimetable();
    }
  };

  btnAvail?.addEventListener("click", () => window.setRoomMode("availability"));
  btnTime?.addEventListener("click", () => window.setRoomMode("timetable"));
  btnCrud?.addEventListener("click", () => window.setRoomMode("crud"));

  const timeSelect = document.getElementById("room-timetable-select");
  timeSelect?.addEventListener("change", () => {
    const selId = timeSelect.value;
    const openBtn = document.getElementById("btn-open-schedules-room");
    if (openBtn) {
      openBtn.href = selId ? `/schedules?room=${selId}` : "/schedules";
    }
    renderRoomTimetable();
  });
}

window.switchRoomModeTimetable = function (roomId) {
  window.setRoomMode("timetable");
  const timeSelect = document.getElementById("room-timetable-select");
  if (timeSelect) {
    timeSelect.value = roomId;
    const openBtn = document.getElementById("btn-open-schedules-room");
    if (openBtn) openBtn.href = `/schedules?room=${roomId}`;
  }
  renderRoomTimetable();
};

function initRoomAvailabilityControls() {
  const daySelect = document.getElementById("check-time-day");
  const hourSelect = document.getElementById("check-time-hour");
  const buildingFilter = document.getElementById("room-avail-filter-building");
  const facultyFilter = document.getElementById("room-avail-filter-faculty");
  const programFilter = document.getElementById("room-avail-filter-program");
  const stuGroupFilter = document.getElementById("student-filter-room-group");
  const stuSecFilter = document.getElementById("student-filter-section");

  daySelect?.addEventListener("change", updateRoomAvailabilityBoard);
  hourSelect?.addEventListener("change", updateRoomAvailabilityBoard);
  buildingFilter?.addEventListener("change", updateRoomAvailabilityBoard);
  facultyFilter?.addEventListener("change", updateRoomAvailabilityBoard);
  programFilter?.addEventListener("change", updateRoomAvailabilityBoard);
  stuGroupFilter?.addEventListener("change", updateRoomAvailabilityBoard);
  stuSecFilter?.addEventListener("change", updateRoomAvailabilityBoard);
}

function populateRoomAvailabilityFilters() {
  // Populate faculty filter
  const facSel = document.getElementById("room-avail-filter-faculty");
  if (facSel && masterDataCache.faculty.length > 0) {
    facSel.innerHTML = `<option value="">All Faculty</option>` +
      masterDataCache.faculty
        .slice()
        .sort((a, b) => a.name.localeCompare(b.name))
        .map(f => `<option value="${f.id}">${escapeHtml(f.name)}</option>`)
        .join("");
  }

  // Populate student section filter
  const stuSecSel = document.getElementById("student-filter-section");
  if (stuSecSel && masterDataCache.sections.length > 0) {
    stuSecSel.innerHTML = `<option value="">All Section ▾</option>` +
      masterDataCache.sections
        .slice()
        .sort((a, b) => a.name.localeCompare(b.name))
        .map(s => `<option value="${s.id}">${escapeHtml(s.name)}</option>`)
        .join("");
  }

  // Populate room timetable picker
  const roomSel = document.getElementById("room-timetable-select");
  if (roomSel && masterDataCache.rooms.length > 0) {
    roomSel.innerHTML = masterDataCache.rooms
      .slice()
      .sort((a, b) => a.room_code.localeCompare(b.room_code))
      .map(r => `<option value="${r.id}">${escapeHtml(r.room_code)} (${escapeHtml(r.building || 'COE')})</option>`)
      .join("");
    const openBtn = document.getElementById("btn-open-schedules-room");
    if (openBtn && masterDataCache.rooms[0]) {
      openBtn.href = `/schedules?room=${masterDataCache.rooms[0].id}`;
    }
  }
}

function timeToMinutes(t) {
  if (!t) return 0;
  const parts = t.slice(0, 5).split(":");
  return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
}

function formatTimeShort(t) {
  if (!t) return "";
  const parts = t.slice(0, 5).split(":");
  let h = parseInt(parts[0], 10);
  const m = parts[1];
  const ampm = h >= 12 ? "PM" : "AM";
  h = h % 12 || 12;
  return `${h}:${m} ${ampm}`;
}

function updateRoomAvailabilityBoard() {
  const isStudent = window.CURRENT_ROLE === "STUDENT";
  const defFilters = document.getElementById("filter-controls-default");
  const stuFilters = document.getElementById("filter-controls-student");
  const colOcc = document.getElementById("col-occupied-rooms");
  const splitBoard = document.getElementById("room-split-board");
  const modeToggle = document.getElementById("room-mode-toggle");

  if (isStudent) {
    if (defFilters) defFilters.style.display = "none";
    if (stuFilters) stuFilters.style.display = "grid";
    if (colOcc) colOcc.style.display = "none";
    if (splitBoard) splitBoard.style.gridTemplateColumns = "1fr";
    if (modeToggle) modeToggle.style.display = "none";
  } else {
    if (defFilters) defFilters.style.display = "grid";
    if (stuFilters) stuFilters.style.display = "none";
    if (colOcc) colOcc.style.display = "block";
    if (splitBoard) splitBoard.style.gridTemplateColumns = "1fr 1fr";
    if (modeToggle) modeToggle.style.display = "inline-flex";
  }

  const day = document.getElementById("check-time-day")?.value || "MON";
  const hourVal = document.getElementById("check-time-hour")?.value || "10:00";
  
  let buildingVal = document.getElementById("room-avail-filter-building")?.value || "";
  let facVal = document.getElementById("room-avail-filter-faculty")?.value || "";
  let progVal = document.getElementById("room-avail-filter-program")?.value || "";
  let secVal = "";

  if (isStudent) {
    const stuGroup = document.getElementById("student-filter-room-group")?.value || "";
    secVal = document.getElementById("student-filter-section")?.value || "";
    if (stuGroup === "COE 1" || stuGroup === "COE 2" || stuGroup === "LAB") {
      buildingVal = stuGroup;
    }
  }

  const checkMins = timeToMinutes(hourVal);
  const displayTime = formatTimeShort(hourVal);

  const headingAvail = document.getElementById("heading-available-title");
  if (headingAvail) headingAvail.textContent = `Available at ${displayTime}`;

  // Filter schedules on this day
  const daySchedules = schedulesCache.filter((s) => s.day_of_week === day);

  const occupiedList = [];
  const availableList = [];

  masterDataCache.rooms.forEach((room) => {
    // Check building filter
    if (buildingVal) {
      if (buildingVal === "LAB") {
        if (room.room_type !== "LAB") return;
      } else if (buildingVal === "COE 1") {
        if (!room.room_code.startsWith("COE 1") && room.building !== "COE 1 Building") return;
      } else if (buildingVal === "COE 2") {
        if (!room.room_code.startsWith("COE 2") && room.building !== "COE 2 Building") return;
      }
    }

    const roomScheds = daySchedules.filter((s) => s.room_id === room.id);
    const activeSched = roomScheds.find((s) => {
      const sStart = timeToMinutes(s.start_time);
      const sEnd = timeToMinutes(s.end_time);
      return sStart <= checkMins && checkMins < sEnd;
    });

    if (activeSched) {
      // Room is occupied
      if (facVal && String(activeSched.faculty_id) !== String(facVal)) return;
      if (secVal && String(activeSched.section_id) !== String(secVal)) return;
      if (progVal) {
        const schedProg = normalizeProgram(activeSched.program || (activeSched.section_name ? activeSched.section_name.split("-")[0].trim() : ""));
        if (schedProg !== normalizeProgram(progVal)) return;
      }
      occupiedList.push({ room, schedule: activeSched });
    } else {
      // Room is available
      const upcoming = roomScheds
        .filter((s) => timeToMinutes(s.start_time) >= checkMins)
        .sort((a, b) => timeToMinutes(a.start_time) - timeToMinutes(b.start_time));
      const nextSched = upcoming[0] || null;

      if (facVal && nextSched && String(nextSched.faculty_id) !== String(facVal)) return;
      if (secVal && nextSched && String(nextSched.section_id) !== String(secVal)) return;
      if (progVal && nextSched) {
        const schedProg = normalizeProgram(nextSched.program || (nextSched.section_name ? nextSched.section_name.split("-")[0].trim() : ""));
        if (schedProg !== normalizeProgram(progVal)) return;
      }

      availableList.push({ room, nextSchedule: nextSched });
    }
  });

  // Update KPI 1 (Rooms in Inventory)
  const kpiTotal = document.getElementById("kpi-rooms-total");
  if (kpiTotal) kpiTotal.textContent = masterDataCache.rooms.length;

  // Update KPI 2 (Available at Sample Check)
  const kpiAvail = document.getElementById("kpi-avail-count");
  if (kpiAvail) kpiAvail.textContent = availableList.length;

  // Update KPI 3 (Next Booking)
  const kpiNextTime = document.getElementById("kpi-next-booking-time");
  const kpiNextDesc = document.getElementById("kpi-next-booking-desc");
  const allUpcoming = daySchedules
    .filter((s) => timeToMinutes(s.start_time) >= checkMins)
    .sort((a, b) => timeToMinutes(a.start_time) - timeToMinutes(b.start_time));

  if (allUpcoming.length > 0 && kpiNextTime && kpiNextDesc) {
    const earliest = allUpcoming[0];
    kpiNextTime.textContent = formatTimeShort(earliest.start_time);
    kpiNextDesc.textContent = `${earliest.room_code || 'Room'} - ${earliest.subject_code || ''} ${earliest.subject_title || ''}`;
  } else if (kpiNextTime && kpiNextDesc) {
    kpiNextTime.textContent = "--:--";
    kpiNextDesc.textContent = "No upcoming bookings today";
  }

  // Update column badges
  const badgeOcc = document.getElementById("badge-occupied-count");
  if (badgeOcc) badgeOcc.textContent = `${occupiedList.length} Preoccupied`;

  const badgeAvail = document.getElementById("badge-available-count");
  if (badgeAvail) badgeAvail.textContent = `${availableList.length} Open`;

  // Render Occupied Rooms
  const occContainer = document.getElementById("list-occupied-rooms");
  if (occContainer) {
    if (occupiedList.length === 0) {
      occContainer.innerHTML = `<div style="text-align:center; padding: 32px; color: var(--text-muted); font-size: 13px;">No occupied rooms at this time.</div>`;
    } else {
      occContainer.innerHTML = occupiedList
        .map(({ room, schedule: s }) => {
          const sEndMins = timeToMinutes(s.end_time);
          const remMins = Math.max(0, sEndMins - checkMins);
          const remHours = Math.round((remMins / 60) * 10) / 10;
          const remainingText = remMins >= 60
            ? `${remHours} Hour${remHours === 1 ? '' : 's'} Remaining`
            : `${remMins} Mins Remaining`;

          return `
            <div class="glass-card" style="padding: 14px 16px; background: rgba(255,255,255,0.85); border: 1px solid rgba(239,68,68,0.3); border-radius: var(--radius-sm); box-shadow: 0 2px 8px rgba(0,0,0,0.03);">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <div style="display:flex; align-items:center; gap:6px;">
                  <span style="font-size:15px; font-weight:800; color:var(--text-dark);">${escapeHtml(room.room_code)}</span>
                  <span style="background:#EDE9FE; color:#5B21B6; font-size:10px; font-weight:800; padding:2px 6px; border-radius:4px;">${escapeHtml(room.department || 'GEN')}</span>
                </div>
                <span style="background:#EF4444; color:#FFFFFF; font-size:10.5px; font-weight:700; padding:2px 8px; border-radius:9999px; text-transform:uppercase;">Occupied</span>
              </div>
              <div style="font-size:12px; color:var(--text-secondary); margin-bottom:4px;">${escapeHtml(room.building || 'COE Building')} - ${escapeHtml(room.room_type)}</div>
              ${room.booked_by_label ? `<div style="font-size:11.5px; color:#B45309; font-weight:700; margin-bottom:4px;">🏷️ Requested by: ${escapeHtml(room.booked_by_label)}</div>` : ''}
              <div style="font-size:12.5px; font-weight:600; color:var(--sidebar-bg); margin-bottom:8px;">${escapeHtml(s.section_name || 'Section')} • ${escapeHtml(s.faculty_name || 'Faculty')}</div>
              <div style="display:flex; justify-content:space-between; align-items:center; font-size:11.5px; color:var(--text-muted); border-top:1px solid rgba(0,0,0,0.06); padding-top:6px;">
                <span>Occupied from ${formatTimeShort(s.start_time)} - ${formatTimeShort(s.end_time)}</span>
                <span style="font-weight:700; color:#EF4444;">${remainingText}</span>
              </div>
            </div>
          `;
        })
        .join("");
    }
  }

  // Render Available Rooms (Matches Screenshot 2026-10-24 191953.png)
  const availContainer = document.getElementById("list-available-rooms");
  if (availContainer) {
    if (availableList.length === 0) {
      availContainer.innerHTML = `<div style="text-align:center; padding: 32px; color: var(--text-muted); font-size: 13px;">No available rooms match the selected criteria.</div>`;
    } else {
      const canRequestRoom = window.CURRENT_ROLE === "STUDENT" || window.CURRENT_ROLE === "FACULTY";

      availContainer.innerHTML = availableList
        .map(({ room, nextSchedule: nextS }) => {
          let nextBookingText = "No more bookings today";
          let hoursLeftText = "Open All Day";

          if (nextS) {
            const nextStartMins = timeToMinutes(nextS.start_time);
            const diffMins = Math.max(0, nextStartMins - checkMins);
            const diffHours = Math.round((diffMins / 60) * 10) / 10;
            hoursLeftText = `${diffHours} Hour${diffHours === 1 ? '' : 's'} Left`;
            nextBookingText = `Next booking at ${formatTimeShort(nextS.start_time)}`;
          }

          return `
            <div class="glass-card" style="padding: 14px 18px; background: rgba(255,255,255,0.88); border: 1px solid rgba(34,197,94,0.3); border-radius: var(--radius-sm); box-shadow: 0 2px 8px rgba(0,0,0,0.03);">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <div style="display:flex; align-items:center; gap:6px;">
                  <span style="font-size:15px; font-weight:800; color:var(--text-dark);">${escapeHtml(room.room_code)}</span>
                  <span style="background:#EDE9FE; color:#5B21B6; font-size:10px; font-weight:800; padding:2px 6px; border-radius:4px;">${escapeHtml(room.department || 'GEN')}</span>
                </div>
                <span style="background:#86EFAC; color:#14532D; font-size:10.5px; font-weight:700; padding:3px 10px; border-radius:9999px; text-transform:uppercase;">AVAILABLE</span>
              </div>
              <div style="font-size:12px; color:var(--text-secondary); margin-bottom:6px;">${escapeHtml(room.building || 'COE Building')} - ${escapeHtml(room.room_type)}</div>
              ${room.booked_by_label ? `<div style="font-size:11.5px; color:#B45309; font-weight:700; margin-bottom:6px;">🏷️ Requested by: ${escapeHtml(room.booked_by_label)}</div>` : ''}
              <div style="display:flex; justify-content:space-between; align-items:center; font-size:11.5px; color:var(--text-muted); border-top:1px solid rgba(0,0,0,0.06); padding-top:6px;">
                <span>${nextBookingText}</span>
                <span style="font-weight:700; color:#15803D;">${hoursLeftText}</span>
              </div>
              ${canRequestRoom ? `
                <div style="margin-top: 8px; text-align: right; border-top: 1px dashed rgba(0,0,0,0.06); padding-top: 6px;">
                  <button type="button" class="btn btn-sm btn-primary" onclick="requestRoomBooking(${room.id}, '${escapeAttr(room.room_code)}')" style="font-size: 11px; padding: 3px 10px;">
                    + Request Room
                  </button>
                </div>
              ` : ''}
            </div>
          `;
        })
        .join("");
    }
  }
}

window.requestRoomBooking = async function (roomId, roomCode) {
  const day = prompt(`Enter day of week for booking ${roomCode} (MON, TUE, WED, THU, FRI, SAT):`, "MON");
  if (!day) return;
  const startTime = prompt(`Enter start time (HH:MM):`, "13:00");
  if (!startTime) return;
  const endTime = prompt(`Enter end time (HH:MM):`, "16:00");
  if (!endTime) return;
  const reason = prompt(`Enter justification / reason for requesting ${roomCode}:`, "Department project review and cohort class session");
  if (!reason) return;

  try {
    const res = await API.post("/api/rooms/request", {
      room_id: roomId,
      day_of_week: day.trim().toUpperCase(),
      start_time: startTime.trim(),
      end_time: endTime.trim(),
      reason: reason.trim()
    });
    showToast(res.message || "Room booking request submitted! Pending Program Chair approval.");
    await fetchRooms();
    updateRoomAvailabilityBoard();
    if (typeof updateRequestsInbox === "function") updateRequestsInbox();
  } catch (err) {
    showToast(err.message || "Failed to submit room request", true);
  }
};

function renderRoomTimetable() {
  const roomSelect = document.getElementById("room-timetable-select");
  const container = document.getElementById("room-timetable-grid-container");
  if (!container) return;

  const roomId = roomSelect ? parseInt(roomSelect.value, 10) : null;
  if (!roomId) {
    container.innerHTML = `<div style="text-align:center; padding: 40px; color: var(--text-muted);">Please select a room to view its timetable.</div>`;
    return;
  }

  const room = masterDataCache.rooms.find((r) => r.id === roomId);
  const roomScheds = schedulesCache.filter((s) => s.room_id === roomId);

  const days = ["MON", "TUE", "WED", "THU", "FRI", "SAT"];
  const dayLabels = {
    MON: "Mon",
    TUE: "Tue",
    WED: "Wed",
    THU: "Thu",
    FRI: "Fri",
    SAT: "Sat",
  };

  container.innerHTML = `
    <div style="margin-bottom: 12px; font-size: 14px; font-weight: 700; color: var(--sidebar-bg);">
      Weekly Timetable: ${escapeHtml(room?.room_code || 'Room')} (${escapeHtml(room?.building || 'COE')}, ${escapeHtml(room?.room_type || '')})
    </div>
    <div style="display:grid; grid-template-columns: repeat(6, 1fr); gap: 10px;">
      ${days.map(d => {
        const scheds = roomScheds.filter(s => s.day_of_week === d).sort((a,b) => a.start_time.localeCompare(b.start_time));
        return `
          <div style="background: rgba(255,255,255,0.7); border: 1px solid var(--border-light); border-radius: var(--radius-sm); padding: 10px;">
            <div style="font-size: 13px; font-weight: 700; color: var(--text-dark); margin-bottom: 8px; border-bottom: 2px solid var(--sidebar-bg); padding-bottom: 4px;">${dayLabels[d]}</div>
            ${scheds.length === 0 ? `
              <div style="font-size: 11.5px; color: var(--text-muted); font-style: italic; padding: 8px 0;">No classes scheduled</div>
            ` : scheds.map(s => `
              <div style="background: #FFFFFF; border-left: 3px solid var(--sidebar-bg); border-radius: 4px; padding: 8px; margin-bottom: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.06);">
                <div style="font-size: 11px; font-weight: 700; color: var(--sidebar-bg);">${formatTimeShort(s.start_time)} - ${formatTimeShort(s.end_time)}</div>
                <div style="font-size: 12px; font-weight: 700; color: var(--text-dark); margin: 2px 0;">${escapeHtml(s.subject_code || '')}</div>
                <div style="font-size: 11px; color: var(--text-secondary); text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">${escapeHtml(s.section_name || '')}</div>
                <div style="font-size: 10.5px; color: var(--text-muted);">${escapeHtml(s.faculty_name || '')}</div>
              </div>
            `).join("")}
          </div>
        `;
      }).join("")}
    </div>
  `;
}


// -------------------------------------------------------------
// Faculty Subject Assignment Controller (Chair & Admin)
// -------------------------------------------------------------
let _assignableOptionsCache = null;

window.openAssignSubjectModal = async function(facultyId) {
  const facId = facultyId || _currentDetailedFaculty?.id;
  if (!facId) {
    showToast("Please select a faculty member first.", true);
    return;
  }

  const modal = document.getElementById("modal-assign-subject");
  if (!modal) return;

  // Reset modal state
  document.getElementById("assign-faculty-id").value = facId;
  const conflictAlert = document.getElementById("assign-conflict-alert");
  if (conflictAlert) conflictAlert.style.display = "none";
  const overrideCb = document.getElementById("assign-allow-override");
  if (overrideCb) overrideCb.checked = false;
  const metaBox = document.getElementById("assign-subject-meta");
  if (metaBox) metaBox.style.display = "none";

  // Pre-fill target faculty info if known
  const facObj = (masterDataCache.faculty || []).find(f => String(f.id) === String(facId)) || _currentDetailedFaculty;
  if (facObj) {
    document.getElementById("assign-card-fac-name").textContent = facObj.name || "Faculty Member";
    document.getElementById("assign-card-fac-dept").textContent = `${facObj.department || facObj.program || 'Engineering'} Department`;
    document.getElementById("assign-card-fac-load").textContent = `${facObj.current_units || 0} / ${facObj.max_units || 21} Units`;
  }

  // Load assignable options
  try {
    const res = await API.get(`/api/faculty/${facId}/assignable-options`);
    if (res.status === "success") {
      _assignableOptionsCache = res.data;
      const f = res.data.faculty;
      document.getElementById("assign-card-fac-name").textContent = f.name;
      document.getElementById("assign-card-fac-dept").textContent = `${f.department || f.program} Department`;
      document.getElementById("assign-card-fac-load").textContent = `${f.current_units} / ${f.max_units} Units`;

      // 1. Populate Subject Offering Multi-Select List (Exclude Minor Subjects)
      const majorSubjects = (res.data.subjects || []).filter(sub => (sub.classification || getSubjectClassification(sub)) === "MAJOR");
      renderAssignSubjectMultiList(majorSubjects);

      // 2. Populate Room dropdown (with Do not assign option)
      const roomSelect = document.getElementById("assign-room-select");
      roomSelect.innerHTML = `
        <option value="none">🚫 Do not assign (Unassigned room)</option>
        <option value="auto" selected>✨ Auto-Assign Best Department Room</option>
      `;
      res.data.rooms.forEach(rm => {
        const opt = document.createElement("option");
        opt.value = rm.id;
        opt.textContent = `${rm.room_code} (${rm.room_type} · Cap: ${rm.capacity} · ${rm.building || 'COE'})`;
        roomSelect.appendChild(opt);
      });
    }
  } catch (err) {
    showToast(err.message || "Failed to load assignment options", true);
  }

  modal.style.display = "flex";
};

window._selectedAssignSubjects = new Map(); // subjectId -> { split_preference: "1.5_HOUR_SPLIT" | "3_HOUR_BLOCK" }

window.renderAssignSubjectMultiList = function(subjects) {
  const container = document.getElementById("assign-subject-multiselect-container");
  if (!container) return;
  _selectedAssignSubjects.clear();
  updateAssignSelectedCount();

  if (!subjects || subjects.length === 0) {
    container.innerHTML = `<div style="text-align:center; padding: 16px; color: var(--text-muted); font-size: 12px;">No major subjects available for assignment.</div>`;
    return;
  }

  container.innerHTML = subjects.map(sub => {
    const cls = (sub.classification || getSubjectClassification(sub)) === "MAJOR" ? "Major" : "Minor";
    const subType = sub.subject_type || "LECTURE";
    const hrs = sub.hours_per_week || sub.units || 3;
    const defaultSplit = sub.split_preference || (hrs >= 3 ? "3_HOUR_BLOCK" : "1.5_HOUR_SPLIT");

    return `
      <div class="assign-sub-row" data-id="${sub.id}" data-text="${sub.code} ${sub.title}" style="display: flex; align-items: center; justify-content: space-between; padding: 8px 10px; border-radius: 6px; border: 1px solid #F1F5F9; background: #FAFAFA; transition: background 0.15s ease;">
        <label style="display: flex; align-items: flex-start; gap: 8px; cursor: pointer; flex: 1; margin: 0; font-size: 12px;">
          <input type="checkbox" class="assign-sub-cb" value="${sub.id}" style="margin-top: 3px; accent-color: var(--bulsu-maroon);" onchange="handleAssignSubCheckboxChange(this, ${sub.id}, '${defaultSplit}')">
          <div style="line-height: 1.35;">
            <div style="font-weight: 700; color: var(--text-dark);">
              ${sub.code} — ${sub.title}
            </div>
            <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
              ${sub.units} Units &bull; ${subType} &bull; ${hrs} Hours/Week &bull; <span style="font-weight:700; color:${cls === 'Major' ? 'var(--bulsu-maroon)' : '#B45309'};">${cls} Subject</span>
              <span id="assign-sub-badge-${sub.id}" class="badge-duration-tag" style="margin-left: 6px; font-size: 10px; font-weight: 800; background: rgba(104,28,46,0.1); color: var(--bulsu-maroon); padding: 1px 6px; border-radius: 4px;">
                ${defaultSplit === '3_HOUR_BLOCK' ? '3.0 Hours' : '1.5 Hours'}
              </span>
            </div>
          </div>
        </label>
        
        <!-- 3-Dots Settings Popover Menu Button -->
        <div style="position: relative; margin-left: 8px;">
          <button type="button" class="btn btn-sm btn-dots-settings" onclick="toggleAssignSubSettings(${sub.id}, event)" style="background: none; border: 1px solid #E2E8F0; border-radius: 6px; padding: 3px 7px; color: #64748B; cursor: pointer; font-size: 14px; line-height: 1;" title="Duration Settings (1.5h or 3h)">
            &#8942;
          </button>
          <div id="assign-sub-menu-${sub.id}" class="assign-sub-settings-menu" style="display: none; position: absolute; right: 0; top: 100%; z-index: 1050; background: #FFF; border: 1px solid #CBD5E1; border-radius: 8px; box-shadow: 0 4px 14px rgba(0,0,0,0.12); padding: 6px; min-width: 175px;">
            <div style="font-size: 10.5px; font-weight: 800; color: #475569; text-transform: uppercase; padding: 4px 8px; border-bottom: 1px solid #F1F5F9; margin-bottom: 4px;">
              Slot Duration
            </div>
            <label style="display: flex; align-items: center; gap: 6px; font-size: 11.5px; padding: 4px 8px; cursor: pointer; border-radius: 4px; margin: 0; font-weight: 600;">
              <input type="radio" name="sub-split-${sub.id}" value="1.5_HOUR_SPLIT" ${defaultSplit !== '3_HOUR_BLOCK' ? 'checked' : ''} onchange="setAssignSubDuration(${sub.id}, '1.5_HOUR_SPLIT')">
              <span>1.5 Hours (Split Slot)</span>
            </label>
            <label style="display: flex; align-items: center; gap: 6px; font-size: 11.5px; padding: 4px 8px; cursor: pointer; border-radius: 4px; margin: 0; font-weight: 600;">
              <input type="radio" name="sub-split-${sub.id}" value="3_HOUR_BLOCK" ${defaultSplit === '3_HOUR_BLOCK' ? 'checked' : ''} onchange="setAssignSubDuration(${sub.id}, '3_HOUR_BLOCK')">
              <span>3.0 Hours (Block Slot)</span>
            </label>
          </div>
        </div>
      </div>
    `;
  }).join("");
};

window.toggleAssignSubSettings = function(subId, event) {
  event.stopPropagation();
  // Close any open menus
  document.querySelectorAll(".assign-sub-settings-menu").forEach(el => {
    if (el.id !== `assign-sub-menu-${subId}`) el.style.display = "none";
  });
  const menu = document.getElementById(`assign-sub-menu-${subId}`);
  if (menu) {
    menu.style.display = menu.style.display === "none" ? "block" : "none";
  }
};

// Global click to close popovers
document.addEventListener("click", function(e) {
  if (!e.target.closest(".assign-sub-settings-menu") && !e.target.closest(".btn-dots-settings")) {
    document.querySelectorAll(".assign-sub-settings-menu").forEach(el => el.style.display = "none");
  }
});

window.setAssignSubDuration = function(subId, duration) {
  const badge = document.getElementById(`assign-sub-badge-${subId}`);
  if (badge) {
    badge.textContent = duration === "3_HOUR_BLOCK" ? "3.0 Hours" : "1.5 Hours";
  }
  if (_selectedAssignSubjects.has(subId)) {
    _selectedAssignSubjects.get(subId).split_preference = duration;
  }
  const menu = document.getElementById(`assign-sub-menu-${subId}`);
  if (menu) menu.style.display = "none";
};

window.handleAssignSubCheckboxChange = function(cb, subId, defaultSplit) {
  const row = cb.closest(".assign-sub-row");
  if (cb.checked) {
    const radioVal = document.querySelector(`input[name="sub-split-${subId}"]:checked`)?.value || defaultSplit;
    _selectedAssignSubjects.set(subId, { split_preference: radioVal });
    if (row) {
      row.style.background = "rgba(104,28,46,0.04)";
      row.style.borderColor = "rgba(104,28,46,0.2)";
    }
  } else {
    _selectedAssignSubjects.delete(subId);
    if (row) {
      row.style.background = "#FAFAFA";
      row.style.borderColor = "#F1F5F9";
    }
  }
  updateAssignSelectedCount();
};

window.updateAssignSelectedCount = function() {
  const countSpan = document.getElementById("assign-selected-count");
  if (countSpan) {
    countSpan.textContent = `${_selectedAssignSubjects.size} Selected`;
  }
};

window.filterAssignSubjectList = function() {
  const q = (document.getElementById("assign-subject-search")?.value || "").toLowerCase().trim();
  document.querySelectorAll(".assign-sub-row").forEach(row => {
    const txt = (row.dataset.text || "").toLowerCase();
    row.style.display = !q || txt.includes(q) ? "flex" : "none";
  });
};

window.toggleSelectAllSubjects = function() {
  const cbs = Array.from(document.querySelectorAll(".assign-sub-cb"));
  const allChecked = cbs.length > 0 && cbs.every(cb => cb.checked);
  cbs.forEach(cb => {
    cb.checked = !allChecked;
    const subId = parseInt(cb.value, 10);
    window.handleAssignSubCheckboxChange(cb, subId, "1.5_HOUR_SPLIT");
  });
};

window.closeAssignSubjectModal = function() {
  const modal = document.getElementById("modal-assign-subject");
  if (modal) modal.style.display = "none";
};

window.submitAssignSubject = async function(event) {
  event.preventDefault();
  const facId = document.getElementById("assign-faculty-id").value;
  const roomId = document.getElementById("assign-room-select").value;
  const allowOverride = document.getElementById("assign-allow-override")?.checked || false;

  if (_selectedAssignSubjects.size === 0) {
    showToast("Please select at least one Subject Offering.", true);
    return;
  }

  const subjectsPayload = [];
  _selectedAssignSubjects.forEach((val, subId) => {
    subjectsPayload.push({
      subject_id: subId,
      split_preference: val.split_preference || "1.5_HOUR_SPLIT"
    });
  });

  const payload = {
    subjects: subjectsPayload,
    room_id: roomId === "none" ? "none" : (roomId === "auto" ? "auto" : parseInt(roomId, 10)),
    allow_override: allowOverride
  };

  const btn = document.getElementById("btn-submit-assign-subject");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Assigning Subject Offerings...";
  }

  try {
    const res = await API.post(`/api/faculty/${facId}/assign-subject`, payload);
    if (res.status === "success") {
      showToast(res.message || "Subjects assigned successfully!");
      closeAssignSubjectModal();
      // Refresh faculty list
      fetchFaculty();
      // If detailed view is open, refresh detailed view
      const detCont = document.getElementById("faculty-detailed-container");
      if (detCont && detCont.style.display !== "none") {
        openFacultyDetailed(facId);
      }
    }
  } catch (err) {
    const conflictAlert = document.getElementById("assign-conflict-alert");
    const conflictMsg = document.getElementById("assign-conflict-message");
    if (conflictAlert && conflictMsg) {
      conflictAlert.style.display = "block";
      const detailStr = (err.conflicts && err.conflicts.length > 0) ? err.conflicts.join("<br>&bull; ") : (err.message || "Collision detected.");
      conflictMsg.innerHTML = detailStr;
    }
    showToast(err.message || "Failed to assign subjects", true);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Assign Subject Offering";
    }
  }
};

window.unassignSubjectFromFaculty = async function(facultyId, subjectId, scheduleId) {
  if (!confirm("Are you sure you want to unassign this subject offering from the instructor?")) return;
  try {
    const payload = {};
    if (subjectId) payload.subject_id = subjectId;
    if (scheduleId) payload.schedule_id = scheduleId;
    const res = await API.post(`/api/faculty/${facultyId}/unassign-subject`, payload);
    if (res.status === "success") {
      showToast(res.message || "Subject unassigned successfully!");
      fetchFaculty();
      const detCont = document.getElementById("faculty-detailed-container");
      if (detCont && detCont.style.display !== "none") {
        openFacultyDetailed(facultyId);
      }
    }
  } catch (err) {
    showToast(err.message || "Failed to unassign subject", true);
  }
};

