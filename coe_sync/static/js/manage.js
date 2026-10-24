/**
 * COE SYNC 2026 - Master Data Management CRUD Controller (manage.js)
 * Implements tab switching, real-time validation, dynamic modals, and REST API calls.
 */

let activeTab = "rooms";
let masterDataCache = {
  rooms: [],
  faculty: [],
  sections: [],
  subjects: [],
};

document.addEventListener("DOMContentLoaded", () => {
  initManageTabs();
  initModalHandlers();
  initTableFilters();
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
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });

  // 4. Update the top "+ Add" button
  const addBtn =
    document.getElementById('btn-add-entity') ||
    document.getElementById('add-entity-btn');
  if (addBtn) {
    const singularName =
      tabName.charAt(0).toUpperCase() + tabName.slice(1).replace(/s$/, '');
    addBtn.textContent = `+ Add ${singularName}`;
    addBtn.setAttribute('data-target-modal', `modal-add-${tabName}`);
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
    tab.addEventListener('click', (e) => {
      e.preventDefault();
      const target = tab.dataset.tab;
      switchTab(target);
      history.replaceState(null, '', `?tab=${target}`);
    });
  });

  // Activate initial tab on load
  switchTab(initialTab);

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
  ]);
  window.applyRolePermissions(window.CURRENT_ROLE);
}

async function fetchRooms() {
  try {
    const res = await API.get("/api/rooms");
    if (res.status === "success") {
      masterDataCache.rooms = res.data;
      document.getElementById("count-rooms").textContent = res.count;
      renderRoomsTable(res.data);
    }
  } catch (err) {
    document.getElementById("table-rooms-body").innerHTML =
      `<tr><td colspan="5" style="color:#EF4444; text-align:center;">Failed to load rooms.</td></tr>`;
  }
}

function renderRoomsTable(rooms) {
  const tbody = document.getElementById("table-rooms-body");
  if (!tbody) return;

  if (rooms.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color: var(--text-muted); padding: 24px;">No rooms found.</td></tr>`;
    return;
  }

  tbody.innerHTML = rooms
    .map(
      (r) => `
    <tr>
      <td><strong>${escapeHtml(r.room_code)}</strong></td>
      <td><span class="badge badge-${r.room_type}">${r.room_type}</span></td>
      <td>${r.capacity} seats</td>
      <td>
        <span class="${r.is_available ? "status-dot-active" : "status-dot-inactive"}">
          ${r.is_available ? "Available" : "Maintenance"}
        </span>
      </td>
      <td>
        <div class="table-actions">
          <a href="/schedules?room=${r.id}" class="btn btn-secondary btn-sm" style="display:inline-flex; align-items:center; gap:4px; text-decoration:none;" title="View Room Timetable">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            Schedule
          </a>
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
      const pct = Math.min(100, Math.round((f.current_units / f.max_units) * 100));
      const fillClass = f.current_units > f.max_units ? "danger" : pct >= 80 ? "warning" : "";

      return `
      <tr>
        <td><strong>${escapeHtml(f.name)}</strong></td>
        <td>${escapeHtml(f.email)}</td>
        <td>${f.max_units} Units</td>
        <td>
          <div style="font-size: 13px; font-weight: 600;">${f.current_units} / ${f.max_units} u (${pct}%)</div>
          <div class="workload-bar-wrap">
            <div class="workload-bar-fill ${fillClass}" style="width: ${pct}%;"></div>
          </div>
        </td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="openFacultyAvailabilityModal(${f.id}, '${escapeAttr(f.name)}')">
            Availability
          </button>
        </td>
        <td>
          <div class="table-actions">
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

async function fetchSections() {
  try {
    const res = await API.get("/api/sections");
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
      <td>${s.student_count} Students</td>
      <td>
        <div class="table-actions">
          <a href="/schedules?section=${s.id}" class="btn btn-secondary btn-sm" style="display:inline-flex; align-items:center; gap:4px; text-decoration:none;" title="View Section Timetable">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            Schedule
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

async function fetchSubjects() {
  try {
    const res = await API.get("/api/subjects");
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

function renderSubjectsTable(subjects) {
  const tbody = document.getElementById("table-subjects-body");
  if (!tbody) return;

  if (subjects.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: var(--text-muted); padding: 24px;">No curricular subjects found.</td></tr>`;
    return;
  }

  tbody.innerHTML = subjects
    .map(
      (sub) => `
    <tr>
      <td><strong>${escapeHtml(sub.code)}</strong></td>
      <td>${escapeHtml(sub.title)}</td>
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
  `
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
        <label class="form-label" for="inp-capacity">Seating Capacity *</label>
        <input class="form-input" type="number" id="inp-capacity" name="capacity" min="1" max="500" required placeholder="e.g. 45" value="${data ? data.capacity : "40"}">
        <span class="form-error" id="err-capacity"></span>
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
        <label class="form-label" for="inp-student-count">Enrolled Student Count *</label>
        <input class="form-input" type="number" id="inp-student-count" name="student_count" min="1" max="200" required placeholder="e.g. 40" value="${data ? data.student_count : "40"}">
        <span class="form-error" id="err-student_count"></span>
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
    const cap = parseInt(payload.capacity);
    if (isNaN(cap) || cap <= 0) {
      showFieldError("capacity", "Capacity must be greater than 0.");
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
    const sc = parseInt(payload.student_count);
    if (isNaN(sc) || sc <= 0) {
      showFieldError("student_count", "Student count must be greater than 0.");
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
      if (q && !sec.name.toLowerCase().includes(q)) return false;
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
  const fSubjType = document.getElementById("filter-subject-type");
  const fSubjUnits = document.getElementById("filter-subject-units");
  const fSubjProg = document.getElementById("filter-subject-prog");
  const fSubjYear = document.getElementById("filter-subject-year");

  function applySubjectsFilter() {
    const q = (sSubjects?.value || "").toLowerCase().trim();
    const t = fSubjType?.value || "";
    const u = fSubjUnits?.value || "";
    const p = fSubjProg?.value || "";
    const y = fSubjYear?.value || "";

    const filtered = masterDataCache.subjects.filter((sub) => {
      if (q && !sub.code.toLowerCase().includes(q) && !sub.title.toLowerCase().includes(q)) return false;
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
  fSubjType?.addEventListener("change", applySubjectsFilter);
  fSubjUnits?.addEventListener("change", applySubjectsFilter);
  fSubjProg?.addEventListener("change", applySubjectsFilter);
  fSubjYear?.addEventListener("change", applySubjectsFilter);
}

function normalizeProgram(prog) {
  if (!prog) return "";
  const p = prog.trim().toUpperCase();
  if (p === "BSCE" || p === "CE") return "CE";
  if (p === "BSEE" || p === "BSECE" || p === "ECE" || p === "BSCpE" || p === "CPE") return "ECE";
  if (p === "BSME" || p === "MEE" || p === "ME") return "MEE";
  if (p === "BSMFE" || p === "MFE") return "MFE";
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

