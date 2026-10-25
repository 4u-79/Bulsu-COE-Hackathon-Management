/**
 * COE SYNC 2026 — Phase 4: Interactive Weekly Timetable (schedules_view.js)
 *
 * Architecture:
 *  - Pure CSS Grid pixel-spanning timetable (7:00–19:30, 30-min rows = 52px each)
 *  - Filter toolbar with live re-render on change
 *  - Conflict Radar slide-out drawer with re-scan
 *  - Add/Edit Schedule modal with pre-flight conflict check & 1-Click Apply Alternative
 *  - Delete / Edit via event card context actions
 *  - Week navigation (local display only, data always reflects current week filter)
 */

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────
const GRID_START_HOUR   = 7;    // 7:00 AM
const GRID_END_HOUR     = 19;   // 7:00 PM (12 hours = 768px height at 32px per 30-min slot)
const SLOT_MINUTES      = 30;   // each row = 30 min
const ROW_PX            = 32;   // pixel height of one 30-min slot (64px per hour)
const PIXELS_PER_MINUTE = ROW_PX / SLOT_MINUTES; // 32px / 30min
const DAYS = ["MON","TUE","WED","THU","FRI","SAT"];
const DAY_LABELS = ["Mon","Tue","Wed","Thu","Fri","Sat"];

// ─────────────────────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────────────────────
let _weekOffset      = 0;       // 0 = current week, ±N weeks
let _activeViewMode  = "WEEK";  // "WEEK" | "DAY"
let _activeDayIndex  = 3;       // Default Thursday (index 3) to match reference preview
let _schedules       = [];      // raw API data
let _draggedSchedule = null;    // currently dragged schedule object
let _editingId       = null;    // null = create, number = update
let _radarCategory   = "ALL";   // "ALL" | "ROOM" | "FACULTY" | "SECTION"
let _allConflicts    = [];      // current detected conflicts
let _masterData      = {
  sections: [],
  faculty: [],
  rooms: [],
  subjects: [],
};

// ─────────────────────────────────────────────────────────────────────────────
// Subject Category Mapping (6-Category System)
// ─────────────────────────────────────────────────────────────────────────────
function getSubjectCategoryClass(subject) {
  if (!subject) return "cat-engineering";
  const code = String(subject.subject_code || subject.code || "").toUpperCase();
  const title = String(subject.subject_title || subject.subject_name || subject.title || "").toUpperCase();
  const type = String(subject.subject_type || subject.type || "").toUpperCase();

  // 1. Laboratory: subject_type === 'LAB' or code ends with L/D/F or title contains 'Laboratory'
  if (type === "LAB" || code.endsWith("L") || code.endsWith("D") || code.endsWith("F") || title.includes("LABORATORY") || title.includes("LAB")) {
    return "cat-lab";
  }
  // 2. NSTP / PE: code starts with 'PE' or 'NSTP' or title contains 'PATHFIT'
  if (code.startsWith("PE") || code.startsWith("NSTP") || title.includes("PATHFIT") || title.includes("PHYSICAL EDUCATION") || title.includes("ROTC") || title.includes("CWTS")) {
    return "cat-nstp-pe";
  }
  // 3. Math & Physics: title/code contains Calculus, Physics, Differential, Mathematics, MMW, Statics, Dynamics
  if (title.includes("CALCULUS") || title.includes("PHYSICS") || title.includes("DIFFERENTIAL") || title.includes("MATHEMATICS") || title.includes("MMW") || title.includes("STATICS") || title.includes("DYNAMICS") || code.includes("MATH") || code.includes("PHYS")) {
    return "cat-math-physics";
  }
  // 4. Language: code/title contains PCM, PAL, AE 101, English, Panitikan, Communication
  if (code.includes("PCM") || code.includes("PAL") || code.includes("AE 101") || title.includes("ENGLISH") || title.includes("PANITIKAN") || title.includes("COMMUNICATION") || title.includes("PURPOSIVE")) {
    return "cat-language";
  }
  // 5. General Education: code/title contains UTS, RPH, TCW, AAP, ETH, STS, RLW, SSP
  if (code.includes("UTS") || code.includes("RPH") || code.includes("TCW") || code.includes("AAP") || code.includes("ETH") || code.includes("STS") || code.includes("RLW") || code.includes("SSP") || title.includes("UNDERSTANDING THE SELF") || title.includes("READINGS IN PHILIPPINE HISTORY") || title.includes("CONTEMPORARY WORLD") || title.includes("ART APPRECIATION") || title.includes("ETHICS") || title.includes("SCIENCE, TECHNOLOGY")) {
    return "cat-gened";
  }
  // 6. Engineering: default for all core COE, CIV, ECE, MEE, MFE
  return "cat-engineering";
}

function formatTimeDisplay(timeStr) {
  if (!timeStr) return "0:00";
  const s = String(timeStr).trim();
  if (s.includes(".5")) {
    const parts = s.split(":");
    const h = Math.floor(parseFloat(parts[0]));
    return `${h}:30`;
  }
  const parts = s.split(":");
  if (parts.length >= 2) {
    const h = parseInt(parts[0], 10);
    const m = parts[1].slice(0, 2);
    return `${h}:${m}`;
  }
  return s;
}

function formatTimeRange(start, end) {
  return `${formatTimeDisplay(start)} – ${formatTimeDisplay(end)}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Boot
// ─────────────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  buildStaticGrid();
  await loadMasterData();

  // Sync Academic Term with global state
  const termSelect = document.getElementById("filter-term");
  const storedTerm = localStorage.getItem("coe_sync_active_term") || "1";
  if (termSelect) {
    termSelect.value = storedTerm;
  }

  populateFilterSelects();
  populateModalSelects();
  buildTimeSlotOptions();
  bindEvents();
  updateRoleAdaptiveFilters();

  // Check URL query parameters
  const urlParams = new URLSearchParams(window.location.search);
  const conflict = urlParams.get("conflict");
  if (conflict === "true" || urlParams.get("radar") === "open") {
    setTimeout(openRadar, 300);
  }
  const sec = urlParams.get("section_id") || urlParams.get("section");
  const progParam = urlParams.get("program");
  const rm = urlParams.get("room_id") || urlParams.get("room");
  const fac = urlParams.get("faculty_id") || urlParams.get("faculty");
  const statParam = urlParams.get("status");

  if (progParam) {
    setSelectVal("filter-program", progParam);
    cascadeScheduleFilters();
  }
  if (sec) {
    setSelectVal("filter-section", sec);
  } else if (window.CURRENT_ROLE === "STUDENT" && window.CURRENT_REF_ID) {
    setSelectVal("filter-section", window.CURRENT_REF_ID);
  } else if (!progParam && !rm && !fac && (window.CURRENT_ROLE === "CHAIR" || window.CURRENT_ROLE === "ADMIN")) {
    // Smart default scope guard: auto-select first section to prevent dumping 200 concurrent classes
    const secSel = document.getElementById("filter-section");
    if (secSel && secSel.options.length > 1) {
      secSel.selectedIndex = 1;
    }
  }
  if (rm) {
    setSelectVal("filter-room", rm);
  }
  if (fac) {
    setSelectVal("filter-faculty", fac);
  } else if (window.CURRENT_ROLE === "FACULTY" && window.CURRENT_REF_ID) {
    setSelectVal("filter-faculty", window.CURRENT_REF_ID);
  }
  if (statParam) {
    setSelectVal("filter-status", statParam);
  }

  await fetchAndRender();
  await fetchLiveUtilization();
  updateWeekLabel();
});

window.addEventListener("roleChanged", (e) => {
  updateRoleAdaptiveFilters();
  const refId = e.detail?.reference_id || window.CURRENT_REF_ID;
  if (window.CURRENT_ROLE === "FACULTY" && refId) {
    setSelectVal("filter-faculty", refId);
  } else if (window.CURRENT_ROLE === "STUDENT" && refId) {
    setSelectVal("filter-section", refId);
  }
  cascadeScheduleFilters();
  fetchAndRender();
  fetchLiveUtilization();
  if (document.getElementById("radar-drawer")?.classList.contains("radar-drawer--open")) {
    runRadarScan();
  }
});

window.addEventListener("academicTermChanged", (e) => {
  const term = e.detail?.term || localStorage.getItem("coe_sync_active_term") || "1";
  const termSelect = document.getElementById("filter-term");
  if (termSelect && termSelect.value !== term) {
    termSelect.value = term;
  }
  cascadeScheduleFilters();
  fetchAndRender();
});

// ─────────────────────────────────────────────────────────────────────────────
// 1. Static Grid Scaffolding
// ─────────────────────────────────────────────────────────────────────────────
function buildStaticGrid() {
  buildDayHeaders();
  buildTimeGutter();
  buildDayColumns();
}

function buildDayHeaders() {
  const header = document.getElementById("timetable-header");
  if (!header) return;
  header.innerHTML = '<div class="th-gutter"></div>';

  const today = new Date();
  const monday = getWeekMonday(today, _weekOffset);

  if (_activeViewMode === "DAY") {
    header.style.gridTemplateColumns = "64px 1fr";
    const date = new Date(monday);
    date.setDate(monday.getDate() + _activeDayIndex);
    const isToday = date.toDateString() === today.toDateString();

    const cell = document.createElement("div");
    cell.className = "th-day th-day--single" + (isToday ? " th-day--today" : "");
    cell.innerHTML = `
      <span class="th-day-label" style="font-size: 13px; font-weight: 800; letter-spacing: 1px;">${DAYS[_activeDayIndex]}</span>
      <span class="th-day-num ${isToday ? "th-day-num--today" : ""}" style="font-size: 15px;">${date.toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>
    `;
    header.appendChild(cell);
  } else {
    header.style.gridTemplateColumns = "64px repeat(6, 1fr)";
    DAYS.forEach((_, i) => {
      const date = new Date(monday);
      date.setDate(monday.getDate() + i);
      const isToday = date.toDateString() === today.toDateString();

      const cell = document.createElement("div");
      cell.className = "th-day" + (isToday ? " th-day--today" : "");
      cell.dataset.dayIndex = i;
      cell.innerHTML = `
        <span class="th-day-label">${DAYS[i]}</span>
        <span class="th-day-num ${isToday ? "th-day-num--today" : ""}">${date.getDate()}</span>
      `;
      header.appendChild(cell);
    });
  }
}

function buildTimeGutter() {
  const gutter = document.getElementById("timetable-gutter");
  if (!gutter) return;
  gutter.innerHTML = "";

  const totalSlots = (GRID_END_HOUR - GRID_START_HOUR) * 2;
  for (let s = 0; s < totalSlots; s++) {
    const totalMin = GRID_START_HOUR * 60 + s * SLOT_MINUTES;
    const h = Math.floor(totalMin / 60);
    const m = totalMin % 60;
    const label = document.createElement("div");
    label.className = "gutter-slot" + (m === 30 ? " gutter-slot--half" : "");
    label.textContent = m === 0 ? `${h}:00` : "";
    gutter.appendChild(label);
  }
}

function buildDayColumns() {
  const container = document.getElementById("timetable-columns");
  if (!container) return;
  container.innerHTML = "";

  const totalSlots = (GRID_END_HOUR - GRID_START_HOUR) * 2;

  DAYS.forEach((day, di) => {
    const col = document.createElement("div");
    col.className = "day-column";
    col.id        = `col-${day}`;
    col.style.gridColumn = di + 1;

    // Background slot rows (for visual grid lines)
    for (let s = 0; s < totalSlots; s++) {
      const bg = document.createElement("div");
      bg.className = "bg-slot" + (s % 2 === 0 ? "" : " bg-slot--half");
      col.appendChild(bg);
    }

    // Click-to-add overlay on empty slots (Chair & Admin only)
    col.addEventListener("click", (e) => {
      if (e.target.closest(".event-card-v2")) return;
      if (window.CURRENT_ROLE !== "CHAIR" && window.CURRENT_ROLE !== "ADMIN") return;
      const rect = col.getBoundingClientRect();
      const relY = e.clientY - rect.top + col.scrollTop;
      const slotIndex = Math.floor(relY / ROW_PX);
      const totalMin  = GRID_START_HOUR * 60 + slotIndex * SLOT_MINUTES;
      const h = Math.floor(totalMin / 60);
      const m = totalMin % 60;
      if (h >= GRID_END_HOUR) return;
      openModal(null, { day_of_week: day, start_time: `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}` });
    });

    // Drag and Drop rescheduling target on empty day slots
    col.addEventListener("dragover", (e) => {
      handleColumnDragOver(e, col, day);
    });
    col.addEventListener("dragleave", (e) => {
      handleColumnDragLeave(e, col);
    });
    col.addEventListener("drop", (e) => {
      handleColumnDrop(e, col, day);
    });

    container.appendChild(col);
  });

  // Single Day View column container setup
  const dayCol = document.getElementById("timetable-day-column");
  if (dayCol) {
    dayCol.innerHTML = "";
    for (let s = 0; s < totalSlots; s++) {
      const bg = document.createElement("div");
      bg.className = "bg-slot" + (s % 2 === 0 ? "" : " bg-slot--half");
      dayCol.appendChild(bg);
    }
    dayCol.addEventListener("click", (e) => {
      if (e.target.closest(".event-card-day")) return;
      if (window.CURRENT_ROLE !== "CHAIR" && window.CURRENT_ROLE !== "ADMIN") return;
      const rect = dayCol.getBoundingClientRect();
      const relY = e.clientY - rect.top + dayCol.scrollTop;
      const slotIndex = Math.floor(relY / ROW_PX);
      const totalMin  = GRID_START_HOUR * 60 + slotIndex * SLOT_MINUTES;
      const h = Math.floor(totalMin / 60);
      const m = totalMin % 60;
      if (h >= GRID_END_HOUR) return;
      openModal(null, { day_of_week: DAYS[_activeDayIndex], start_time: `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}` });
    });

    // Drag and Drop target for Day View
    dayCol.addEventListener("dragover", (e) => {
      handleColumnDragOver(e, dayCol, DAYS[_activeDayIndex]);
    });
    dayCol.addEventListener("dragleave", (e) => {
      handleColumnDragLeave(e, dayCol);
    });
    dayCol.addEventListener("drop", (e) => {
      handleColumnDrop(e, dayCol, DAYS[_activeDayIndex]);
    });
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. Master Data Load
// ─────────────────────────────────────────────────────────────────────────────
async function loadMasterData() {
  try {
    const [secRes, facRes, roomRes, subjRes] = await Promise.all([
      API.get("/api/sections").catch(() => ({ data: [] })),
      API.get("/api/faculty").catch(() => ({ data: [] })),
      API.get("/api/rooms").catch(() => ({ data: [] })),
      API.get("/api/subjects").catch(() => ({ data: [] })),
    ]);
    _masterData.sections = secRes?.data  || [];
    _masterData.faculty  = facRes?.data  || [];
    _masterData.rooms    = roomRes?.data || [];
    _masterData.subjects = subjRes?.data || [];
  } catch (err) {
    console.warn("Master data load error:", err);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. Populate Selects
function normalizeProgram(prog) {
  if (!prog) return "";
  const p = String(prog).toUpperCase().trim();
  if (p === "BSCE" || p === "CIVIL" || p === "CE") return "CE";
  if (p === "BSCPE" || p === "CPE") return "CPE";
  if (p === "BSEE" || p === "EE") return "EE";
  if (p === "BSECE" || p === "ECE" || p === "ELECTRONICS") return "ECE";
  if (p === "BSIE" || p === "IE") return "IE";
  if (p === "BSMFGE" || p === "BSMFE" || p === "MFGE" || p === "MFE" || p === "MANUFACTURING") return "MFGE";
  if (p === "BSME" || p === "ME") return "ME";
  if (p === "BSMEE" || p === "MEE" || p === "MECHANICAL") return "MEE";
  if (p === "GEN" || p === "GENERAL") return "GEN";
  return p;
}

function cascadeScheduleFilters() {
  const progVal = document.getElementById("filter-program")?.value || "";
  const yearVal = document.getElementById("filter-year")?.value || "";
  const termVal = document.getElementById("filter-term")?.value || localStorage.getItem("coe_sync_active_term") || "";
  const secSel  = document.getElementById("filter-section");
  const facSel  = document.getElementById("filter-faculty");
  const subjSel = document.getElementById("filter-subject");

  const normProg = normalizeProgram(progVal);

  if (secSel) {
    const prevVal = secSel.value;
    const filtered = _masterData.sections.filter(s => {
      if (normProg && normalizeProgram(s.program) !== normProg) return false;
      if (yearVal && String(s.year_level) !== String(yearVal)) return false;
      return true;
    });
    const defaultSecText = window.CURRENT_ROLE === "STUDENT" ? "Viewing Cohort: [Select Section ▾]" : "All Section ▾";
    secSel.innerHTML = `<option value="">${defaultSecText}</option>` +
      filtered.map(s => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join("");
    if (filtered.some(s => String(s.id) === String(prevVal))) {
      secSel.value = prevVal;
    } else if (normProg && filtered.length > 0) {
      secSel.value = filtered[0].id; // Auto-select first section when program chosen
    } else {
      secSel.value = "";
    }
  }

  if (facSel) {
    const prevVal = facSel.value;
    const filtered = _masterData.faculty.filter(f => {
      if (normProg) {
        const fp = normalizeProgram(f.program);
        if (fp !== normProg && fp !== "GEN") return false;
      }
      return true;
    });
    const defaultFacText = window.CURRENT_ROLE === "FACULTY" ? "Viewing Instructor: [Select Faculty ▾]" : "All Faculty ▾";
    facSel.innerHTML = `<option value="">${defaultFacText}</option>` +
      filtered.map(f => `<option value="${f.id}">${escapeHtml(f.name)}</option>`).join("");
    if (filtered.some(f => String(f.id) === String(prevVal))) {
      facSel.value = prevVal;
    } else {
      facSel.value = "";
    }
  }

  if (subjSel) {
    const prevVal = subjSel.value;
    const filtered = _masterData.subjects.filter(s => {
      if (normProg) {
        const sp = normalizeProgram(s.program);
        if (sp !== normProg && sp !== "GEN") return false;
      }
      if (yearVal && String(s.year_level) !== String(yearVal)) return false;
      if (termVal && s.semester && String(s.semester) !== String(termVal)) return false;
      return true;
    });
    subjSel.innerHTML = `<option value="">All Subject ▾</option>` +
      filtered.map(s => `<option value="${s.id}">${escapeHtml(s.code || s.name)}</option>`).join("");
    if (filtered.some(s => String(s.id) === String(prevVal))) {
      subjSel.value = prevVal;
    } else {
      subjSel.value = "";
    }
  }
}

function populateFilterSelects() {
  const roomSel = document.getElementById("filter-room");
  if (roomSel) {
    roomSel.innerHTML = `<option value="">All Room ▾</option>` +
      _masterData.rooms.map(r => `<option value="${r.id}">${escapeHtml(r.room_code)}</option>`).join("");
  }
  cascadeScheduleFilters();
}

function populateModalSelects() {
  const mSubj = document.getElementById("m-subject");
  const mSec  = document.getElementById("m-section");
  const mFac  = document.getElementById("m-faculty");
  const mRoom = document.getElementById("m-room");

  if (mSubj) {
    const prev = mSubj.value;
    mSubj.innerHTML = `<option value="">Select subject…</option>` +
      (_masterData.subjects || []).map(s => {
        const clsTag = (s.classification || "MAJOR") === "MINOR" ? " · Minor" : " · Major";
        return `<option value="${s.id}">[${escapeHtml(s.code || "")}] ${escapeHtml(s.title || s.name || "")} (${escapeHtml(s.program || "GEN")}${clsTag})</option>`;
      }).join("");
    if (prev) mSubj.value = prev;
  }

  if (mSec) {
    const prev = mSec.value;
    mSec.innerHTML = `<option value="">Select section…</option>` +
      (_masterData.sections || []).map(s =>
        `<option value="${s.id}">${escapeHtml(s.name || "")} (${escapeHtml(s.program || "")})</option>`
      ).join("");
    if (prev) mSec.value = prev;
  }

  if (mFac) {
    const prev = mFac.value;
    mFac.innerHTML = `<option value="">Select faculty…</option>` +
      (_masterData.faculty || []).map(f =>
        `<option value="${f.id}">${escapeHtml(f.name || "")}</option>`
      ).join("");
    if (prev) mFac.value = prev;
  }

  if (mRoom) {
    const prev = mRoom.value;
    mRoom.innerHTML = `<option value="">Select room…</option>` +
      (_masterData.rooms || []).map(r =>
        `<option value="${r.id}">${escapeHtml(r.room_code || "")} (${escapeHtml(r.room_type || "LECTURE")})</option>`
      ).join("");
    if (prev) mRoom.value = prev;
  }
}

function buildTimeSlotOptions() {
  const slots = [];
  for (let h = GRID_START_HOUR; h <= GRID_END_HOUR; h++) {
    for (let m = 0; m < 60; m += 30) {
      if (h === GRID_END_HOUR && m > 0) break;
      slots.push(`${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}`);
    }
  }

  const mStart = document.getElementById("m-start");
  const mEnd   = document.getElementById("m-end");

  if (mStart) {
    const prev = mStart.value;
    mStart.innerHTML = `<option value="">Select start time…</option>` +
      slots.map(t => `<option value="${t}">${formatTimeTo12(t)}</option>`).join("");
    if (prev) mStart.value = prev;
  }
  if (mEnd) {
    const prev = mEnd.value;
    const endSlots = [];
    for (let h = GRID_START_HOUR; h <= GRID_END_HOUR; h++) {
      for (let m = 0; m < 60; m += 30) {
        if (h === GRID_START_HOUR && m === 0) continue;
        endSlots.push(`${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}`);
      }
    }
    if (!endSlots.includes(`${GRID_END_HOUR}:00`)) {
      endSlots.push(`${GRID_END_HOUR}:00`);
    }
    mEnd.innerHTML = `<option value="">Select end time…</option>` +
      endSlots.map(t => `<option value="${t}">${formatTimeTo12(t)}</option>`).join("");
    if (prev) mEnd.value = prev;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. Role-Adaptive Filters Helper
// ─────────────────────────────────────────────────────────────────────────────
function updateRoleAdaptiveFilters() {
  const role = window.CURRENT_ROLE;
  const wrapProg = document.getElementById("filter-wrap-program");
  const wrapSec = document.getElementById("filter-wrap-section");
  const wrapFac = document.getElementById("filter-wrap-faculty");
  const wrapRoom = document.getElementById("filter-wrap-room");
  const wrapSubj = document.getElementById("filter-wrap-subject");
  const wrapRoomType = document.getElementById("filter-wrap-room-type");
  const utilBadge = document.getElementById("sched-utilization-badge");
  const chairRow = document.getElementById("chair-action-row");
  const facLoadBar = document.getElementById("faculty-teaching-load-bar");
  const studentBanner = document.getElementById("student-portal-banner");

  if (role === "STUDENT") {
    if (wrapProg) wrapProg.style.display = "none";
    if (wrapSec) wrapSec.style.display = "inline-flex";
    if (wrapFac) wrapFac.style.display = "none";
    if (wrapRoom) wrapRoom.style.display = "inline-flex";
    if (wrapSubj) wrapSubj.style.display = "inline-flex";
    if (wrapRoomType) wrapRoomType.style.display = "none";
    if (utilBadge) utilBadge.style.display = "none";
    if (chairRow) chairRow.style.display = "none";
    if (facLoadBar) facLoadBar.style.display = "none";
    if (studentBanner) studentBanner.style.display = "flex";
  } else if (role === "FACULTY") {
    if (wrapProg) wrapProg.style.display = "none";
    if (wrapSec) wrapSec.style.display = "inline-flex";
    if (wrapFac) wrapFac.style.display = "inline-flex";
    if (wrapRoom) wrapRoom.style.display = "none";
    if (wrapSubj) wrapSubj.style.display = "inline-flex";
    if (wrapRoomType) wrapRoomType.style.display = "none";
    if (utilBadge) utilBadge.style.display = "none";
    if (chairRow) chairRow.style.display = "none";
    if (facLoadBar) facLoadBar.style.display = "flex";
    if (studentBanner) studentBanner.style.display = "none";
  } else {
    // CHAIR or ADMIN
    if (wrapProg) wrapProg.style.display = "inline-flex";
    if (wrapSec) wrapSec.style.display = "inline-flex";
    if (wrapFac) wrapFac.style.display = "inline-flex";
    if (wrapRoom) wrapRoom.style.display = "inline-flex";
    if (wrapSubj) wrapSubj.style.display = "none";
    if (wrapRoomType) wrapRoomType.style.display = "inline-flex";
    if (utilBadge) utilBadge.style.display = "inline-flex";
    if (chairRow) chairRow.style.display = "flex";
    if (facLoadBar) facLoadBar.style.display = "none";
    if (studentBanner) studentBanner.style.display = "none";
  }
}

async function fetchLiveUtilization() {
  try {
    const res = await API.getAnalyticsSummary();
    if (res?.status === "success") {
      const utilVal = document.getElementById("sched-room-util-val");
      const utilPct = res.data.overall_room_utilization_pct !== undefined ? res.data.overall_room_utilization_pct : (res.data.room_utilization || 0);
      if (utilVal) utilVal.textContent = `${Number(utilPct).toFixed(2)}%`;
    }
  } catch (e) {}
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. Fetch Schedules + Render
// ─────────────────────────────────────────────────────────────────────────────
async function fetchAndRender() {
  const params = {};
  const secVal   = document.getElementById("filter-section")?.value;
  const facVal   = document.getElementById("filter-faculty")?.value;
  const roomVal  = document.getElementById("filter-room")?.value;
  const progVal  = document.getElementById("filter-program")?.value;
  const yearVal  = document.getElementById("filter-year")?.value;
  const statVal  = document.getElementById("filter-status")?.value;
  const termVal  = document.getElementById("filter-term")?.value || localStorage.getItem("coe_sync_active_term") || "1";

  if (secVal)  params.section_id = secVal;
  if (facVal)  params.faculty_id = facVal;
  if (roomVal) params.room_id    = roomVal;
  if (progVal) params.program    = progVal;
  if (yearVal) params.year_level = yearVal;
  if (termVal) params.semester   = parseInt(termVal, 10);

  try {
    let res = await API.getSchedules(params);
    _schedules = res?.data || [];

    // Smart default fallback: if presenter is in Faculty or Student mode and has 0 classes,
    // auto-select first faculty/section that actually has scheduled classes to prevent blank screen
    if (_schedules.length === 0) {
      if (window.CURRENT_ROLE === "FACULTY") {
        const poolRes = await API.getSchedules({ semester: params.semester });
        const targetClass = poolRes?.data?.find(s => s.faculty_id);
        if (targetClass && String(targetClass.faculty_id) !== String(facVal)) {
          setSelectVal("filter-faculty", targetClass.faculty_id);
          params.faculty_id = targetClass.faculty_id;
          res = await API.getSchedules(params);
          _schedules = res?.data || [];
        }
      } else if (window.CURRENT_ROLE === "STUDENT") {
        const poolRes = await API.getSchedules({ semester: params.semester });
        const targetClass = poolRes?.data?.find(s => s.section_id);
        if (targetClass && String(targetClass.section_id) !== String(secVal)) {
          setSelectVal("filter-section", targetClass.section_id);
          params.section_id = targetClass.section_id;
          res = await API.getSchedules(params);
          _schedules = res?.data || [];
        }
      }
    }

    // Tag schedules involved in detected hard conflicts
    _allConflicts = detectConflictsLocally(_schedules);
    const conflictingIds = new Set();
    _allConflicts.forEach(c => {
      if (c.schedA) conflictingIds.add(c.schedA.id);
      if (c.schedB) conflictingIds.add(c.schedB.id);
    });

    _schedules.forEach(s => {
      s.has_conflict = conflictingIds.has(s.id);
    });

    let visible = _schedules;

    // Client-side status filter
    if (statVal === "CONFLICT") {
      visible = visible.filter(s => s.has_conflict);
    } else if (statVal === "PUBLISHED") {
      visible = visible.filter(s => s.status === "PUBLISHED");
    } else if (statVal === "DRAFT") {
      visible = visible.filter(s => s.status === "DRAFT");
    }

    // Role-level safety: Genuine students must see only PUBLISHED schedules.
    // Impersonating Chair/Admin demoing student portal may view drafts with notice.
    if (window.CURRENT_ROLE === "STUDENT") {
      if (window.AUTHENTIC_USER_ROLE !== "CHAIR" && window.AUTHENTIC_USER_ROLE !== "ADMIN") {
        visible = visible.filter(s => s.status === "PUBLISHED");
      }
    }

    renderEventCards(visible);
    updateRadarBadge(_schedules);
    updateRoleSpecificPortals(_schedules);
  } catch (err) {
    console.warn("Schedule fetch error:", err);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 6. Render Event Cards (Week & Day Mode)
// ─────────────────────────────────────────────────────────────────────────────
function renderEventCards(schedules) {
  const weekContainer = document.getElementById("timetable-columns");
  const dayContainer = document.getElementById("timetable-day-column");
  const watermark = document.getElementById("timetable-empty-state");

  // Client-side Subject & Room Type filters
  const subjVal = document.getElementById("filter-subject")?.value;
  const roomTypeVal = document.getElementById("filter-room-type-sched")?.value;

  let filtered = schedules;
  if (subjVal) {
    filtered = filtered.filter(s => String(s.subject_id) === String(subjVal));
  }
  if (roomTypeVal) {
    const matchingRoomIds = _masterData.rooms
      .filter(r => r.room_type === roomTypeVal)
      .map(r => r.id);
    filtered = filtered.filter(s => matchingRoomIds.includes(s.room_id));
  }

  // Handle Empty State Watermark
  if (watermark) {
    watermark.style.display = filtered.length === 0 ? "flex" : "none";
  }

  if (_activeViewMode === "DAY") {
    if (weekContainer) weekContainer.style.display = "none";
    if (dayContainer) {
      dayContainer.style.display = "block";
      dayContainer.style.position = "relative";
      dayContainer.style.height = "768px";
      dayContainer.style.overflow = "hidden";
      dayContainer.style.width = "100%";
      dayContainer.querySelectorAll(".event-card-day").forEach(el => el.remove());
    }

    const currentDay = DAYS[_activeDayIndex];
    const daySchedules = filtered.filter(s => s.day_of_week === currentDay);

    if (watermark && daySchedules.length === 0) {
      watermark.style.display = "flex";
    }

    resolveDayOverlaps(daySchedules);

    daySchedules.forEach(s => {
      const card = buildDayEventCard(s);
      if (dayContainer) dayContainer.appendChild(card);
    });
  } else {
    // Week Mode
    if (dayContainer) dayContainer.style.display = "none";
    if (weekContainer) weekContainer.style.display = "grid";

    // Clear all columns
    DAYS.forEach(day => {
      const col = document.getElementById(`col-${day}`);
      if (!col) return;
      col.querySelectorAll(".event-card-v2, .event-card-more").forEach(el => el.remove());
    });

    // Bucket by day
    const byDay = {};
    DAYS.forEach(d => byDay[d] = []);
    filtered.forEach(s => {
      if (byDay[s.day_of_week]) byDay[s.day_of_week].push(s);
    });

    DAYS.forEach(day => {
      const col = document.getElementById(`col-${day}`);
      if (!col) return;

      const items = byDay[day];
      resolveOverlaps(items);

      items.filter(s => !s._hiddenByMore).forEach(s => {
        const card = buildEventCard(s);
        col.appendChild(card);
      });
    });
  }
}

/** Assign column position for overlapping cards within the same day (max 2 side-by-side) */
function resolveOverlaps(items) {
  items.forEach(s => {
    s._startMin = timeToMin(s.start_time);
    s._endMin   = timeToMin(s.end_time);
    s._col = 0;
    s._cols = 1;
    s._hiddenByMore = false;
    s._moreCount = 0;
    s._moreItems = [];
  });

  items.sort((a, b) => a._startMin - b._startMin || (b._endMin - b._startMin) - (a._endMin - a._startMin));

  for (let i = 0; i < items.length; i++) {
    if (items[i]._hiddenByMore) continue;
    const cluster = [items[i]];
    for (let j = 0; j < items.length; j++) {
      if (i !== j && !items[j]._hiddenByMore && overlapping(items[i], items[j])) {
        cluster.push(items[j]);
      }
    }

    if (cluster.length <= 2) {
      cluster.forEach((item, idx) => {
        item._cols = cluster.length;
        item._col = idx;
      });
    } else {
      // More than 2 classes overlap in this exact slot:
      // Render at most 2 side-by-side cards (width ~50%) and add a compact +N more badge on card 2
      cluster[0]._cols = 2;
      cluster[0]._col = 0;

      cluster[1]._cols = 2;
      cluster[1]._col = 1;
      cluster[1]._moreCount = cluster.length - 2;
      cluster[1]._moreItems = cluster.slice(2);

      for (let k = 2; k < cluster.length; k++) {
        cluster[k]._hiddenByMore = true;
      }
    }
  }
}

/** Resolve overlaps in Day View (place up to 2 cards side-by-side) */
function resolveDayOverlaps(items) {
  items.forEach(s => {
    s._startMin = timeToMin(s.start_time);
    s._endMin   = timeToMin(s.end_time);
    s._col = 0;
    s._cols = 1;
  });

  items.sort((a, b) => a._startMin - b._startMin);

  for (let i = 0; i < items.length; i++) {
    const overlaps = [items[i]];
    for (let j = 0; j < items.length; j++) {
      if (i !== j && overlapping(items[i], items[j])) {
        overlaps.push(items[j]);
      }
    }
    items[i]._cols = Math.min(2, overlaps.length);
    items[i]._col  = overlaps.indexOf(items[i]) % 2;
  }
}

function overlapping(a, b) {
  return a._startMin < b._endMin && b._startMin < a._endMin;
}

function buildEventCard(s) {
  const startMin  = timeToMin(s.start_time);
  const endMin    = timeToMin(s.end_time);
  const startMinutesFrom7AM = startMin - (GRID_START_HOUR * 60);
  const durationMinutes = endMin - startMin;
  const topPx     = Math.max(0, startMinutesFrom7AM * PIXELS_PER_MINUTE);
  const heightPx  = Math.max(28, durationMinutes * PIXELS_PER_MINUTE - 4);

  const isConflict = s.has_conflict;
  const catClass   = getSubjectCategoryClass(s);
  const isDraft    = (s.status || "").toUpperCase() === "DRAFT";
  const cardClass  = isConflict ? `event-card-v2 ev-conflict ${catClass}`
                   : isDraft ? `event-card-v2 ev-draft ${catClass}`
                   : `event-card-v2 ev-published ${catClass}`;

  const widthPct   = 100 / (s._cols || 1);
  const leftPct    = widthPct * (s._col || 0);

  const card = document.createElement("div");
  card.className    = cardClass;
  card.dataset.id   = s.id;
  card.style.top    = `${topPx}px`;
  card.style.height = `${heightPx}px`;
  card.style.left   = `calc(${leftPct}% + 2px)`;
  card.style.width  = `calc(${widthPct}% - 4px)`;

  const dur = endMin - startMin;
  const isShort = dur <= 30;
  const isAdmin = window.CURRENT_ROLE === "CHAIR" || window.CURRENT_ROLE === "ADMIN";
  const isStudent = window.CURRENT_ROLE === "STUDENT";
  const displayTitle = s.subject_code ? `${s.subject_code} – ${s.subject_title || s.subject_name || ""}` : (s.subject_name || "Unknown");

  card.innerHTML = `
    <div class="ev-body" style="position: relative; width: 100%; height: 100%;">
      ${isDraft ? `<span class="ev-badge-draft">DRAFT</span>` : `<span class="ev-badge-published">✓</span>`}
      <div class="ev-title" style="padding-right: 32px; font-weight: 700; line-height: 1.2;">${escapeHtml(displayTitle)}</div>
      ${!isShort ? `
        <div class="ev-meta" style="font-weight: 600;">${escapeHtml(s.section_name || "—")}</div>
        <div class="ev-meta ev-faculty" style="opacity: 0.9;">${escapeHtml(s.faculty_name || "—")}</div>
        <div class="ev-meta" style="font-size: 9.5px; opacity: 0.85;">${escapeHtml(s.room_code || "—")}</div>
      ` : ""}
      ${isConflict ? `<div class="ev-conflict-badge">⚠ Conflict</div>` : ""}
      ${s._moreCount ? `
        <button type="button" class="event-card-more" style="bottom: 2px; right: 2px;" title="View all ${s._moreCount + 2} concurrent classes">
          +${s._moreCount} more
        </button>
      ` : ""}
    </div>
    ${isAdmin ? `
      <div class="ev-actions">
        <button class="ev-btn ev-btn-edit" data-id="${s.id}" title="Edit" aria-label="Edit schedule">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
        </button>
        <button class="ev-btn ev-btn-delete" data-id="${s.id}" title="Delete" aria-label="Delete schedule">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
        </button>
      </div>
    ` : isStudent && !isDraft ? `
      <div class="ev-actions" style="opacity: 1;">
        <button class="btn-card-reschedule" data-schedule-id="${s.id}" title="Request Reschedule for this class">
          ✎ Reschedule
        </button>
      </div>
    ` : ""}
  `;

  // Bind +N more button
  if (s._moreCount) {
    card.querySelector(".event-card-more")?.addEventListener("click", (e) => {
      e.stopPropagation();
      openOverlappingClassesModal(s, s._moreItems);
    });
  }

  // Bind action buttons for admin
  if (isAdmin) {
    card.querySelector(".ev-btn-edit")?.addEventListener("click", (e) => {
      e.stopPropagation();
      openModal(s.id);
    });
    card.querySelector(".ev-btn-delete")?.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteSchedule(s.id, s.subject_code, s.section_name);
    });

    // Drag-and-drop rescheduling support for Chair & Admin
    card.setAttribute("draggable", "true");
    card.addEventListener("dragstart", (e) => {
      e.stopPropagation();
      _draggedSchedule = s;
      card.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", String(s.id));
    });
    card.addEventListener("dragend", () => {
      card.classList.remove("dragging");
      _draggedSchedule = null;
      document.querySelectorAll(".drop-target-hover").forEach(el => el.classList.remove("drop-target-hover"));
      document.querySelectorAll(".drag-over").forEach(el => el.classList.remove("drag-over"));
      document.querySelectorAll(".drag-drop-slot-guide").forEach(el => el.remove());
    });
    card.addEventListener("dragover", (e) => {
      if (_draggedSchedule && _draggedSchedule.id !== s.id) {
        e.preventDefault();
        e.stopPropagation();
        e.dataTransfer.dropEffect = "move";
        card.classList.add("drop-target-hover");
      }
    });
    card.addEventListener("dragleave", (e) => {
      card.classList.remove("drop-target-hover");
    });
    card.addEventListener("drop", (e) => {
      if (_draggedSchedule && _draggedSchedule.id !== s.id) {
        e.preventDefault();
        e.stopPropagation();
        card.classList.remove("drop-target-hover");
        const draggedId = _draggedSchedule.id;
        _draggedSchedule = null;
        executeScheduleMove(draggedId, s.day_of_week, s.start_time ? s.start_time.slice(0, 5) : "08:00", s.id);
      }
    });
  }

  // Bind student reschedule button
  if (isStudent && !isDraft) {
    card.querySelector(".btn-card-reschedule")?.addEventListener("click", (e) => {
      e.stopPropagation();
      if (typeof window.openRescheduleModal === "function") {
        window.openRescheduleModal("new", s.id);
      }
    });
  }

  // Click card: Chair/Admin gets full Edit/Delete/Details modal; Students can propose reschedule
  card.addEventListener("click", () => {
    if (isAdmin) {
      openModal(s.id);
    } else if (isStudent) {
      if (typeof window.openRescheduleModal === "function") {
        window.openRescheduleModal("new", s.id);
      }
    } else if (s.has_conflict) {
      openRadar();
    }
  });

  return card;
}

function buildDayEventCard(s) {
  const startMin  = timeToMin(s.start_time);
  const endMin    = timeToMin(s.end_time);
  const startMinutesFrom7AM = startMin - (GRID_START_HOUR * 60);
  const durationMinutes = endMin - startMin;
  const topPx     = Math.max(0, startMinutesFrom7AM * PIXELS_PER_MINUTE);
  const heightPx  = Math.max(36, durationMinutes * PIXELS_PER_MINUTE - 4);

  const isConflict = s.has_conflict;
  const catClass   = getSubjectCategoryClass(s);
  const isDraft    = (s.status || "").toUpperCase() === "DRAFT";
  const cardClass  = isConflict ? `event-card-day ev-conflict ${catClass}`
                   : isDraft ? `event-card-day ev-draft ${catClass}`
                   : `event-card-day ev-published ${catClass}`;

  const card = document.createElement("div");
  card.className    = cardClass;
  card.dataset.id   = s.id;
  card.style.top    = `${topPx}px`;
  card.style.height = `${heightPx}px`;

  // Side-by-side positioning when 2 cards overlap in Day View
  if (s._cols > 1) {
    card.style.width = `calc(50% - 8px)`;
    card.style.left  = s._col === 1 ? `calc(50% + 4px)` : `4px`;
  } else {
    card.style.width = `calc(100% - 8px)`;
    card.style.left  = `4px`;
  }

  const isAdmin = window.CURRENT_ROLE === "CHAIR" || window.CURRENT_ROLE === "ADMIN";
  const displayTitle = s.subject_code ? `${s.subject_code} – ${s.subject_title || s.subject_name || ""}` : (s.subject_name || "Unknown");

  card.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
      <div class="day-card-title" style="font-weight: 700;">${escapeHtml(displayTitle)}</div>
      ${isDraft ? `<span class="ev-badge-draft">DRAFT</span>` : `<span class="ev-badge-published">✓ Published</span>`}
    </div>
    <div class="day-card-section" style="font-weight: 600; margin-top: 2px;">${escapeHtml(s.section_name || "—")} · Room ${escapeHtml(s.room_code || "—")}</div>
    <div class="day-card-faculty" style="opacity: 0.9; margin-top: 1px;">${escapeHtml(s.faculty_name || "—")}</div>
    <div class="day-card-time" style="font-size: 11px; margin-top: 2px;">${formatTimeRange(s.start_time, s.end_time)}</div>
    ${isConflict ? `<div class="ev-conflict-badge" style="margin-top: 4px;">⚠ Conflict Detected</div>` : ""}
  `;

  card.addEventListener("click", () => {
    if (isAdmin) {
      openModal(s.id);
    } else if (window.CURRENT_ROLE === "STUDENT") {
      if (typeof window.openRescheduleModal === "function") {
        window.openRescheduleModal("new", s.id);
      }
    } else if (s.has_conflict) {
      openRadar();
    }
  });

  if (isAdmin) {
    card.setAttribute("draggable", "true");
    card.addEventListener("dragstart", (e) => {
      e.stopPropagation();
      _draggedSchedule = s;
      card.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", String(s.id));
    });
    card.addEventListener("dragend", () => {
      card.classList.remove("dragging");
      _draggedSchedule = null;
      document.querySelectorAll(".drop-target-hover").forEach(el => el.classList.remove("drop-target-hover"));
      document.querySelectorAll(".drag-over").forEach(el => el.classList.remove("drag-over"));
      document.querySelectorAll(".drag-drop-slot-guide").forEach(el => el.remove());
    });
    card.addEventListener("dragover", (e) => {
      if (_draggedSchedule && _draggedSchedule.id !== s.id) {
        e.preventDefault();
        e.stopPropagation();
        e.dataTransfer.dropEffect = "move";
        card.classList.add("drop-target-hover");
      }
    });
    card.addEventListener("dragleave", (e) => {
      card.classList.remove("drop-target-hover");
    });
    card.addEventListener("drop", (e) => {
      if (_draggedSchedule && _draggedSchedule.id !== s.id) {
        e.preventDefault();
        e.stopPropagation();
        card.classList.remove("drop-target-hover");
        const draggedId = _draggedSchedule.id;
        _draggedSchedule = null;
        executeScheduleMove(draggedId, s.day_of_week, s.start_time ? s.start_time.slice(0, 5) : "08:00", s.id);
      }
    });
  }

  return card;
}

function openOverlappingClassesModal(primary, moreItems) {
  const backdrop = document.getElementById("modal-more-classes-backdrop");
  const listEl = document.getElementById("modal-more-list");
  const titleEl = document.getElementById("modal-more-title");
  const subtitleEl = document.getElementById("modal-more-subtitle");
  if (!backdrop || !listEl) return;

  const allItems = [primary, ...(moreItems || [])];
  if (titleEl) titleEl.textContent = `Concurrent Classes (${allItems.length})`;
  if (subtitleEl) subtitleEl.textContent = `${primary.day_of_week} · Overlapping time slot`;

  listEl.innerHTML = allItems.map(s => `
    <div style="background: rgba(255,255,255,0.95); border: 1px solid var(--border-light); border-radius: 8px; padding: 10px; box-shadow: 0 2px 6px rgba(0,0,0,0.06); text-align: left;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <strong style="font-size: 13px; color: #111827;">${escapeHtml(s.subject_code || '')} – ${escapeHtml(s.subject_name || s.subject_title || '')}</strong>
        <span class="badge ${s.status === 'PUBLISHED' ? 'badge-LECTURE' : 'badge-secondary'}" style="font-size: 9.5px;">${s.status}</span>
      </div>
      <div style="font-size: 11.5px; color: #4B5563; margin-top: 4px;">
        <strong>Section:</strong> ${escapeHtml(s.section_name || '—')} &bull; <strong>Room:</strong> ${escapeHtml(s.room_code || '—')}
      </div>
      <div style="font-size: 11.5px; color: #6B7280; margin-top: 2px;">
        <strong>Faculty:</strong> ${escapeHtml(s.faculty_name || '—')} &bull; <strong>Time:</strong> ${formatTimeRange(s.start_time, s.end_time)}
      </div>
    </div>
  `).join("");

  backdrop.style.display = "flex";
  backdrop.classList.add("sched-modal-backdrop--open");

  const closeFn = () => {
    backdrop.style.display = "none";
    backdrop.classList.remove("sched-modal-backdrop--open");
  };
  document.getElementById("modal-more-close")?.addEventListener("click", closeFn, { once: true });
  document.getElementById("modal-more-ok")?.addEventListener("click", closeFn, { once: true });
}

function updateRoleSpecificPortals(schedules) {
  const role = window.CURRENT_ROLE || "CHAIR";
  const facBanner = document.getElementById("faculty-teaching-load-bar");
  const studentBanner = document.getElementById("student-portal-banner");

  if (role === "FACULTY") {
    if (facBanner) facBanner.style.display = "flex";
    if (studentBanner) studentBanner.style.display = "none";

    const facNameElem = document.getElementById("fac-load-name");
    const facNumbersElem = document.getElementById("fac-load-numbers");
    const facMeterFill = document.getElementById("fac-load-meter-fill");
    const facBadge = document.getElementById("fac-load-badge");

    const currentFacId = document.getElementById("filter-faculty")?.value || window.CURRENT_REF_ID || schedules[0]?.faculty_id;
    const currentFac = _masterData.faculty.find(f => String(f.id) === String(currentFacId));

    if (facNameElem) {
      facNameElem.textContent = currentFac?.name || schedules[0]?.faculty_name || "Faculty Member";
    }

    // Calculate actual units from schedules for this faculty
    const facSchedules = schedules.filter(s => String(s.faculty_id) === String(currentFacId));
    let assignedUnits = 0;
    const countedSubjects = new Set();
    facSchedules.forEach(s => {
      if (!countedSubjects.has(s.subject_id)) {
        countedSubjects.add(s.subject_id);
        const subj = _masterData.subjects.find(sub => sub.id === s.subject_id);
        assignedUnits += (subj?.units || 3);
      }
    });

    const maxUnits = currentFac?.max_units || 21;
    const utilRate = maxUnits > 0 ? (assignedUnits / maxUnits) * 100 : 0;

    if (facNumbersElem) {
      facNumbersElem.textContent = `${assignedUnits} / ${maxUnits} Units`;
    }
    if (facMeterFill) {
      facMeterFill.style.width = `${Math.min(100, utilRate)}%`;
      facMeterFill.className = `faculty-meter-fill ${assignedUnits > maxUnits ? 'overload' : assignedUnits >= 19 ? 'warning' : ''}`;
    }
    if (facBadge) {
      if (assignedUnits > maxUnits) {
        facBadge.className = "status-badge crimson";
        facBadge.textContent = "OVERLOAD (>21u)";
      } else if (assignedUnits >= 19) {
        facBadge.className = "status-badge amber";
        facBadge.textContent = "NEAR MAX";
      } else {
        facBadge.className = "status-badge mint";
        facBadge.textContent = "NORMAL";
      }
    }

    // Wire Faculty Availability modal
    const availBtn = document.getElementById("btn-faculty-avail");
    if (availBtn) {
      availBtn.onclick = () => {
        openFacultyAvailabilityModal(currentFacId);
      };
    }

    // Hook review button
    const reviewBtn = document.getElementById("btn-faculty-review-reschedules");
    if (reviewBtn) {
      reviewBtn.onclick = () => {
        if (typeof window.openRescheduleModal === "function") {
          window.openRescheduleModal("pending");
        }
      };
    }

  } else if (role === "STUDENT") {
    if (facBanner) facBanner.style.display = "none";
    if (studentBanner) studentBanner.style.display = "flex";

    const secLabel = document.getElementById("student-portal-section-label");
    const curSecId = document.getElementById("filter-section")?.value || window.CURRENT_REF_ID || schedules[0]?.section_id;
    const curSec = _masterData.sections.find(s => String(s.id) === String(curSecId));

    if (secLabel) {
      secLabel.textContent = curSec ? `Section ${curSec.name}` : (schedules[0]?.section_name ? `Section ${schedules[0].section_name}` : "Student Timetable");
    }

    // Check if any schedule is in DRAFT status
    const draftNotice = document.getElementById("student-draft-notice");
    if (draftNotice) {
      const hasDrafts = schedules.some(s => (s.status || "").toUpperCase() === "DRAFT");
      draftNotice.style.display = hasDrafts ? "inline-block" : "none";
      if (hasDrafts) {
        draftNotice.textContent = "DRAFT TIMETABLE — Under Review";
      }
    }

    // Hook student request buttons
    const submitBtn = document.getElementById("btn-student-submit-resched");
    const trackBtn = document.getElementById("btn-student-track-reschedules");
    if (submitBtn) {
      submitBtn.onclick = () => {
        if (typeof window.openRescheduleModal === "function") {
          window.openRescheduleModal("new");
        }
      };
    }
    if (trackBtn) {
      trackBtn.onclick = () => {
        if (typeof window.openRescheduleModal === "function") {
          window.openRescheduleModal("all");
        }
      };
    }
  } else {
    // CHAIR or ADMIN
    if (facBanner) facBanner.style.display = "none";
    if (studentBanner) studentBanner.style.display = "none";
  }
}

async function openFacultyAvailabilityModal(facultyId) {
  const backdrop = document.getElementById("modal-faculty-avail-backdrop");
  if (!backdrop) return;

  const fac = _masterData.faculty.find(f => String(f.id) === String(facultyId));
  const titleEl = document.getElementById("modal-fac-avail-title");
  if (titleEl && fac) {
    titleEl.textContent = `Blackout Windows — ${fac.name}`;
  }

  backdrop.style.display = "flex";
  backdrop.classList.add("sched-modal-backdrop--open");

  await renderFacultyAvailabilities(facultyId);

  // Hook Add Button
  const addBtn = document.getElementById("btn-save-new-avail");
  if (addBtn) {
    addBtn.onclick = async () => {
      const day = document.getElementById("new-avail-day")?.value || "FRI";
      const start = document.getElementById("new-avail-start")?.value || "08:00";
      const end = document.getElementById("new-avail-end")?.value || "12:00";

      addBtn.disabled = true;
      addBtn.textContent = "Saving…";
      try {
        await API.createFacultyAvailability(facultyId, {
          day_of_week: day,
          start_time: start,
          end_time: end,
          is_preferred: false,
        });
        showToast("Blackout window successfully registered.", "success");
        await renderFacultyAvailabilities(facultyId);
      } catch (err) {
        showToast(err.message || "Failed to add blackout window.", "error");
      } finally {
        addBtn.disabled = false;
        addBtn.textContent = "Add Blackout Window";
      }
    };
  }

  const closeFn = () => {
    backdrop.style.display = "none";
    backdrop.classList.remove("sched-modal-backdrop--open");
  };
  document.getElementById("modal-fac-avail-close")?.addEventListener("click", closeFn, { once: true });
  document.getElementById("modal-fac-avail-done")?.addEventListener("click", closeFn, { once: true });
}

async function renderFacultyAvailabilities(facultyId) {
  const listEl = document.getElementById("fac-avail-list");
  if (!listEl) return;
  listEl.innerHTML = `<div style="font-size: 12px; color: var(--text-muted); padding: 8px;">Loading blackout windows…</div>`;

  try {
    const res = await API.getFacultyAvailability(facultyId);
    const avails = res?.data || [];
    if (avails.length === 0) {
      listEl.innerHTML = `<div style="font-size: 12px; color: var(--text-muted); padding: 8px; font-style: italic;">No blackout windows registered. Faculty is available during normal scheduling hours.</div>`;
      return;
    }

    listEl.innerHTML = avails.map(a => `
      <div style="display: flex; justify-content: space-between; align-items: center; background: #FFF5F5; border: 1px solid #FECACA; border-radius: 6px; padding: 8px 12px;">
        <div>
          <strong style="font-size: 13px; color: #991B1B;">${escapeHtml(a.day_of_week)}</strong>
          <span style="font-size: 12px; color: #7F1D1D; margin-left: 8px;">${formatTimeTo12(a.start_time)} – ${formatTimeTo12(a.end_time)}</span>
          <span class="status-badge crimson" style="font-size: 10px; margin-left: 8px;">BLACKOUT</span>
        </div>
        <button type="button" class="btn btn-sm btn-ghost btn-del-avail" data-avail-id="${a.id}" style="color: #DC2626; cursor: pointer;" title="Remove this blackout window">
          ✕ Remove
        </button>
      </div>
    `).join("");

    listEl.querySelectorAll(".btn-del-avail").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.availId;
        if (!confirm("Remove this blackout window?")) return;
        try {
          await API.deleteFacultyAvailability(id);
          showToast("Blackout window removed.", "success");
          await renderFacultyAvailabilities(facultyId);
        } catch (e) {
          showToast(e.message || "Failed to remove blackout window.", "error");
        }
      });
    });
  } catch (err) {
    listEl.innerHTML = `<div style="font-size: 12px; color: #DC2626; padding: 8px;">Failed to load blackout windows: ${escapeHtml(err.message)}</div>`;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 6. Conflict Radar Drawer
// ─────────────────────────────────────────────────────────────────────────────
function openRadar() {
  document.getElementById("radar-drawer")?.classList.add("radar-drawer--open");
  document.getElementById("radar-overlay")?.classList.add("radar-overlay--open");
  runRadarScan();
}

function closeRadar() {
  document.getElementById("radar-drawer")?.classList.remove("radar-drawer--open");
  document.getElementById("radar-overlay")?.classList.remove("radar-overlay--open");
}

async function runRadarScan() {
  const scanFill = document.getElementById("radar-scan-fill");
  const body     = document.getElementById("radar-body");
  const emptyEl  = document.getElementById("radar-empty");
  const listEl   = document.getElementById("radar-conflict-list");
  const lastScan = document.getElementById("radar-last-scan");

  // Animate scan bar
  if (scanFill) {
    scanFill.style.width = "0%";
    scanFill.style.transition = "width 1.2s ease";
    requestAnimationFrame(() => { scanFill.style.width = "100%"; });
  }

  try {
    // Re-fetch all schedules ignoring filters for full picture
    const res = await API.get("/api/schedules");
    const all = res?.data || [];

    // Find conflicts by checking schedules that have overlapping room/faculty/section/capacity
    const conflicts = detectConflictsLocally(all);
    _allConflicts = conflicts;

    updateRadarBadge(all);

    // Update category badge numbers
    const catCounts = {
      ALL: conflicts.length,
      ROOM: conflicts.filter(c => c.type === "room").length,
      FACULTY: conflicts.filter(c => c.type === "faculty").length,
      SECTION: conflicts.filter(c => c.type === "section").length,
    };
    const cAll = document.getElementById("cat-count-all");
    const cRoom = document.getElementById("cat-count-room");
    const cFac = document.getElementById("cat-count-faculty");
    const cSec = document.getElementById("cat-count-section");
    if (cAll) cAll.textContent = catCounts.ALL;
    if (cRoom) cRoom.textContent = catCounts.ROOM;
    if (cFac) cFac.textContent = catCounts.FACULTY;
    if (cSec) cSec.textContent = catCounts.SECTION;

    // Filter by active category
    const filtered = _radarCategory === "ALL"
      ? conflicts
      : conflicts.filter(c => c.type.toUpperCase() === _radarCategory);

    if (filtered.length === 0) {
      emptyEl.style.display   = "flex";
      listEl.style.display    = "none";
      if (conflicts.length > 0 && _radarCategory !== "ALL") {
        emptyEl.querySelector("p").textContent = `No ${_radarCategory.toLowerCase()} conflicts`;
        emptyEl.querySelector("span").textContent = `0 clashes under selected category filter`;
      } else {
        emptyEl.querySelector("p").textContent = "No conflicts detected";
        emptyEl.querySelector("span").textContent = "All schedules pass hard constraints";
      }
    } else {
      emptyEl.style.display   = "none";
      listEl.style.display    = "block";
      listEl.innerHTML = filtered.map(c => buildConflictCard(c)).join("");

      // Bind 1-click apply alternative buttons (if admin/chair)
      const isAdmin = window.CURRENT_ROLE === "CHAIR" || window.CURRENT_ROLE === "ADMIN";
      if (isAdmin) {
        listEl.querySelectorAll(".alt-apply-btn").forEach(btn => {
          btn.addEventListener("click", () => {
            const data = JSON.parse(btn.dataset.alt);
            applyAlternative(data, parseInt(btn.dataset.schedId));
          });
        });
      }
    }

    if (scanFill) setTimeout(() => { scanFill.style.width = "0%"; scanFill.style.transition = "width 0.2s ease"; }, 1200);
    if (lastScan) lastScan.textContent = `Scanned at ${new Date().toLocaleTimeString()}`;

  } catch (err) {
    console.warn("Radar scan error:", err);
    if (scanFill) scanFill.style.width = "0%";
  }
}

function detectConflictsLocally(schedules) {
  const conflicts = [];
  const n = schedules.length;

  for (let i = 0; i < n; i++) {
    const a = schedules[i];

    for (let j = i + 1; j < n; j++) {
      const b = schedules[j];
      if (a.day_of_week !== b.day_of_week) continue;
      const aStart = timeToMin(a.start_time), aEnd = timeToMin(a.end_time);
      const bStart = timeToMin(b.start_time), bEnd = timeToMin(b.end_time);
      if (aStart >= bEnd || bStart >= aEnd) continue;

      // Check hard constraints
      if (a.room_id === b.room_id) {
        conflicts.push({ type: "room", resource: a.room_code, schedA: a, schedB: b });
      }
      if (a.faculty_id === b.faculty_id) {
        conflicts.push({ type: "faculty", resource: a.faculty_name, schedA: a, schedB: b });
      }
      if (a.section_id === b.section_id) {
        conflicts.push({ type: "section", resource: a.section_name, schedA: a, schedB: b });
      }
    }
  }
  return conflicts;
}

function buildConflictCard(c) {
  const typeIcons = {
    room: "🏫",
    faculty: "👨‍🏫",
    section: "🎓",
  };
  const typeLabels = {
    room: "Room Double-Booking",
    faculty: "Faculty Overlap",
    section: "Section Collision",
  };

  const typeIcon  = typeIcons[c.type] || "⚠️";
  const typeLabel = typeLabels[c.type] || "Constraint Violation";
  const isAdmin   = window.CURRENT_ROLE === "CHAIR" || window.CURRENT_ROLE === "ADMIN";



  return `
    <div class="conflict-card">
      <div class="conflict-type">
        <span>${typeIcon} ${typeLabel}</span>
        <span class="conflict-resource">${escapeHtml(c.resource || "")}</span>
      </div>
      <div class="conflict-pair">
        <div class="conflict-entry">
          <strong>${escapeHtml(c.schedA.subject_code)}</strong>
          <span>${escapeHtml(c.schedA.section_name)} · ${escapeHtml(c.schedA.faculty_name)}</span>
          <span class="conflict-time">${c.schedA.day_of_week} ${formatTimeTo12(c.schedA.start_time)}–${formatTimeTo12(c.schedA.end_time)}</span>
        </div>
        <div class="conflict-vs">vs</div>
        <div class="conflict-entry">
          <strong>${escapeHtml(c.schedB.subject_code)}</strong>
          <span>${escapeHtml(c.schedB.section_name)} · ${escapeHtml(c.schedB.faculty_name)}</span>
          <span class="conflict-time">${c.schedB.day_of_week} ${formatTimeTo12(c.schedB.start_time)}–${formatTimeTo12(c.schedB.end_time)}</span>
        </div>
      </div>
      <div class="conflict-actions">
        ${isAdmin ? `
          <button class="btn btn-sm btn-outline" onclick="openModal(${c.schedA.id})">Edit #${c.schedA.id}</button>
          <button class="btn btn-sm btn-outline" onclick="openModal(${c.schedB.id})">Edit #${c.schedB.id}</button>
          <button class="btn btn-sm btn-conflict-alt alt-apply-btn" 
            data-sched-id="${c.schedA.id}"
            data-alt="${escapeAttr(JSON.stringify({ subject_id: c.schedA.subject_id, section_id: c.schedA.section_id, faculty_id: c.schedA.faculty_id, room_id: c.schedA.room_id, day_of_week: c.schedA.day_of_week, start_time: c.schedA.start_time, end_time: c.schedA.end_time }))}">
            🔁 Find Alternative
          </button>
        ` : `
          <span style="font-size:11px; color:var(--text-muted); font-style:italic;">Read-only (Chair access required to resolve)</span>
        `}
      </div>
    </div>
  `;
}

function updateRadarBadge(schedules) {
  const badge = document.getElementById("radar-badge");
  const dot   = document.getElementById("radar-dot");
  const conflicts = detectConflictsLocally(schedules);
  const count = conflicts.length;

  if (badge) {
    if (count > 0) {
      badge.textContent = count;
      badge.style.display = "inline-flex";
    } else {
      badge.style.display = "none";
    }
  }
  if (dot) {
    dot.classList.toggle("radar-dot--conflict", count > 0);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 7. Schedule Modal (Add / Edit)
// ─────────────────────────────────────────────────────────────────────────────
function openModal(editId = null, prefill = {}) {
  _editingId = editId;
  const backdrop  = document.getElementById("sched-modal-backdrop");
  if (!backdrop) return;

  const titleEl   = document.getElementById("sched-modal-title");
  const saveBtn   = document.getElementById("sched-modal-save");
  const form      = document.getElementById("sched-modal-form");
  const preflightBanner  = document.getElementById("preflight-banner");
  const suggestionsPanel = document.getElementById("suggestions-panel");
  const deleteBtn = document.getElementById("sched-modal-delete");
  const conflictBanner = document.getElementById("modal-conflict-banner");

  // Ensure options are populated with latest master data
  populateModalSelects();
  buildTimeSlotOptions();

  // Reset form
  form.reset();
  if (preflightBanner) preflightBanner.style.display = "none";
  if (suggestionsPanel) suggestionsPanel.style.display = "none";
  document.getElementById("sched-edit-id").value = "";

  if (editId) {
    titleEl.textContent = `Edit Schedule #${editId}`;
    saveBtn.textContent = "Update Schedule";
    const sched = _schedules.find(s => s.id === editId);
    if (sched) {
      document.getElementById("sched-edit-id").value = sched.id;
      setSelectVal("m-subject", sched.subject_id);
      setSelectVal("m-section", sched.section_id);
      setSelectVal("m-faculty", sched.faculty_id);
      setSelectVal("m-room",    sched.room_id);
      setSelectVal("m-day",     sched.day_of_week);
      setSelectVal("m-status",  sched.status);
      setSelectVal("m-start",   sched.start_time?.slice(0, 5));
      setSelectVal("m-end",     sched.end_time?.slice(0, 5));

      if (sched.has_conflict && conflictBanner) {
        conflictBanner.style.display = "block";
        const btnRadar = document.getElementById("btn-modal-open-radar");
        if (btnRadar) {
          btnRadar.onclick = () => {
            closeModal();
            openRadar();
          };
        }
      } else if (conflictBanner) {
        conflictBanner.style.display = "none";
      }

      if (deleteBtn) {
        deleteBtn.style.display = "inline-flex";
        deleteBtn.onclick = async () => {
          closeModal();
          await deleteSchedule(sched.id, sched.subject_code, sched.section_name);
        };
      }
    }
  } else {
    titleEl.textContent = "Add New Schedule";
    saveBtn.textContent = "Save Schedule";
    if (conflictBanner) conflictBanner.style.display = "none";
    if (deleteBtn) deleteBtn.style.display = "none";

    // Apply prefill values from active filters or grid-click
    const activeSec = prefill.section_id || document.getElementById("filter-section")?.value;
    if (activeSec) setSelectVal("m-section", activeSec);

    const activeFac = prefill.faculty_id || document.getElementById("filter-faculty")?.value;
    if (activeFac) setSelectVal("m-faculty", activeFac);

    const activeRoom = prefill.room_id || document.getElementById("filter-room")?.value;
    if (activeRoom) setSelectVal("m-room", activeRoom);

    if (prefill.day_of_week) setSelectVal("m-day", prefill.day_of_week);
    if (prefill.start_time)  setSelectVal("m-start", prefill.start_time);
    if (prefill.end_time)    setSelectVal("m-end", prefill.end_time);
  }

  backdrop.classList.add("sched-modal-backdrop--open");
  document.getElementById("m-subject")?.focus();
}

function closeModal() {
  document.getElementById("sched-modal-backdrop")?.classList.remove("sched-modal-backdrop--open");
  _editingId = null;
}

async function runPreflight() {
  const payload = collectFormPayload();
  if (!payload) return;

  const banner = document.getElementById("preflight-banner");
  const sugPanel = document.getElementById("suggestions-panel");
  const sugList  = document.getElementById("suggestions-list");

  banner.style.display = "block";
  banner.className     = "preflight-banner preflight-checking";
  banner.textContent   = "⏳ Checking constraints…";

  try {
    const params = _editingId ? `?exclude_id=${_editingId}` : "";
    const res = await API.post(`/api/conflicts/check${params}`, payload);

    if (res.valid) {
      banner.className   = "preflight-banner preflight-ok";
      banner.textContent = "✅ No conflicts detected — safe to save.";
      sugPanel.style.display = "none";
    } else {
      banner.className   = "preflight-banner preflight-conflict";
      banner.innerHTML   = `⚠️ Conflict: ${res.conflicts.map(escapeHtml).join("; ")}`;

      if (res.suggestions && res.suggestions.length > 0) {
        sugPanel.style.display = "block";
        sugList.innerHTML = res.suggestions.map((alt, idx) => `
          <div class="suggestion-item">
            <div class="suggestion-detail">
              <strong>${alt.day_of_week}</strong> ·
              ${formatTimeTo12(alt.start_time)}–${formatTimeTo12(alt.end_time)} ·
              ${escapeHtml(alt.room_code || alt.room_id || "Same room")}
              <span class="suggestion-score">Score ${alt.score ?? "—"}</span>
            </div>
            <button type="button" class="btn btn-sm btn-apply-alt"
              data-alt='${JSON.stringify(alt).replace(/'/g, "&#39;")}'>
              1-Click Apply
            </button>
          </div>
        `).join("");

        sugList.querySelectorAll(".btn-apply-alt").forEach(btn => {
          btn.addEventListener("click", () => {
            const alt = JSON.parse(btn.dataset.alt);
            applyAlternativeToForm(alt);
          });
        });
      } else {
        sugPanel.style.display = "none";
      }
    }
  } catch (err) {
    banner.className   = "preflight-banner preflight-conflict";
    banner.textContent = `Error: ${err.message}`;
  }
}

function applyAlternativeToForm(alt) {
  if (alt.day_of_week) setSelectVal("m-day",   alt.day_of_week);
  if (alt.start_time)  setSelectVal("m-start",  alt.start_time?.slice(0,5));
  if (alt.end_time)    setSelectVal("m-end",     alt.end_time?.slice(0,5));
  if (alt.room_id)     setSelectVal("m-room",    alt.room_id);

  document.getElementById("preflight-banner").className = "preflight-banner preflight-ok";
  document.getElementById("preflight-banner").textContent = "✅ Alternative applied — re-check or save.";
  document.getElementById("suggestions-panel").style.display = "none";
  showToast("Alternative slot applied to form.", "success");
}

async function applyAlternative(payload, schedId) {
  try {
    const res = await API.post("/api/conflicts/check", payload);
    if (res.suggestions && res.suggestions.length > 0) {
      openModal(schedId);
      setTimeout(() => applyAlternativeToForm(res.suggestions[0]), 300);
    } else {
      showToast("No alternatives found from API.", "info");
      openModal(schedId);
    }
  } catch (err) {
    openModal(schedId);
  }
}

async function submitScheduleForm(e) {
  e.preventDefault();
  const payload = collectFormPayload();
  if (!payload) return;

  const saveBtn = document.getElementById("sched-modal-save");
  saveBtn.disabled   = true;
  saveBtn.textContent = _editingId ? "Updating…" : "Saving…";

  try {
    if (_editingId) {
      await API.put(`/api/schedules/${_editingId}`, payload);
      showToast("Schedule updated successfully.", "success");
    } else {
      await API.createSchedule(payload);
      showToast("Schedule created successfully.", "success");
    }
    closeModal();
    await fetchAndRender();
  } catch (err) {
    const banner = document.getElementById("preflight-banner");
    banner.style.display = "block";
    banner.className     = "preflight-banner preflight-conflict";
    const conflicts = err.data?.conflicts || [];
    const suggestions = err.data?.suggestions || [];
    banner.innerHTML = `⚠️ Save failed: ${err.data?.error || err.message}${conflicts.length ? " — " + conflicts.join("; ") : ""}`;

    if (suggestions.length > 0) {
      const sugPanel = document.getElementById("suggestions-panel");
      const sugList  = document.getElementById("suggestions-list");
      sugPanel.style.display = "block";
      sugList.innerHTML = suggestions.map(alt => `
        <div class="suggestion-item">
          <div class="suggestion-detail">
            <strong>${alt.day_of_week}</strong> · ${formatTimeTo12(alt.start_time)}–${formatTimeTo12(alt.end_time)} · ${escapeHtml(alt.room_code || "Same room")}
          </div>
          <button type="button" class="btn btn-sm btn-apply-alt"
            data-alt='${JSON.stringify(alt).replace(/'/g, "&#39;")}'>
            1-Click Apply
          </button>
        </div>
      `).join("");
      sugList.querySelectorAll(".btn-apply-alt").forEach(btn => {
        btn.addEventListener("click", () => applyAlternativeToForm(JSON.parse(btn.dataset.alt)));
      });
    }
  } finally {
    saveBtn.disabled    = false;
    saveBtn.textContent = _editingId ? "Update Schedule" : "Save Schedule";
  }
}

function collectFormPayload() {
  const get = id => document.getElementById(id)?.value?.trim();
  const payload = {
    subject_id:  parseInt(get("m-subject")),
    section_id:  parseInt(get("m-section")),
    faculty_id:  parseInt(get("m-faculty")),
    room_id:     parseInt(get("m-room")),
    day_of_week: get("m-day"),
    start_time:  get("m-start"),
    end_time:    get("m-end"),
    status:      get("m-status") || "DRAFT",
  };
  const missing = Object.entries(payload).filter(([k,v]) => k !== "status" && !v).map(([k]) => k);
  if (missing.length > 0) {
    showToast(`Please fill in: ${missing.join(", ")}`, "error");
    return null;
  }
  return payload;
}

// ─────────────────────────────────────────────────────────────────────────────
// 8. Delete Schedule
// ─────────────────────────────────────────────────────────────────────────────
async function deleteSchedule(id, subjectCode, sectionName) {
  if (!confirm(`Delete schedule: ${subjectCode} for ${sectionName}?`)) return;
  try {
    await API.delete(`/api/schedules/${id}`);
    showToast("Schedule deleted.", "success");
    await fetchAndRender();
  } catch (err) {
    showToast(`Delete failed: ${err.message}`, "error");
  }
}
window.deleteSchedule = deleteSchedule;

// ─────────────────────────────────────────────────────────────────────────────
// 9. Week Navigation
// ─────────────────────────────────────────────────────────────────────────────
function updateWeekLabel() {
  const label = document.getElementById("week-label");
  if (!label) return;
  if (_activeViewMode === "DAY") {
    const dayNames = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
    const monday = getWeekMonday(new Date(), _weekOffset);
    const date = new Date(monday);
    date.setDate(monday.getDate() + _activeDayIndex);
    label.textContent = `${dayNames[_activeDayIndex]} (${date.toLocaleDateString("en-US", { month:"short", day:"numeric" })})`;
  } else {
    const monday = getWeekMonday(new Date(), _weekOffset);
    const saturday = new Date(monday);
    saturday.setDate(monday.getDate() + 5);
    const fmt = (d) => d.toLocaleDateString("en-US", { month:"short", day:"numeric" });
    label.textContent = `${fmt(monday)} – ${fmt(saturday)}`;
  }
}

function getWeekMonday(base, offset = 0) {
  const d = new Date(base);
  const day = d.getDay(); // 0 = Sunday
  const diff = day === 0 ? -6 : 1 - day;
  d.setDate(d.getDate() + diff + offset * 7);
  d.setHours(0,0,0,0);
  return d;
}

function refreshWeekHeaders() {
  const header = document.getElementById("timetable-header");
  if (!header) return;
  header.querySelectorAll(".th-day").forEach(el => el.remove());
  buildDayHeaders();
}

// ─────────────────────────────────────────────────────────────────────────────
// 10. Event Bindings
// ─────────────────────────────────────────────────────────────────────────────
function bindEvents() {
  // Add schedule button & Smart Generator CTA
  document.getElementById("btn-add-schedule")?.addEventListener("click", () => openModal());
  document.getElementById("btn-create-schedule-cta")?.addEventListener("click", () => {
    window.location.href = "/schedules/create";
  });

  // Week | Day View Toggle
  document.getElementById("toggle-view-week")?.addEventListener("click", () => {
    _activeViewMode = "WEEK";
    document.getElementById("toggle-view-week")?.classList.add("active");
    document.getElementById("toggle-view-day")?.classList.remove("active");
    refreshWeekHeaders();
    updateWeekLabel();
    renderEventCards(_schedules);
  });
  document.getElementById("toggle-view-day")?.addEventListener("click", () => {
    _activeViewMode = "DAY";
    document.getElementById("toggle-view-day")?.classList.add("active");
    document.getElementById("toggle-view-week")?.classList.remove("active");
    refreshWeekHeaders();
    updateWeekLabel();
    renderEventCards(_schedules);
  });

  // Print schedule
  document.getElementById("btn-print-schedule")?.addEventListener("click", () => {
    window.print();
  });

  // Batch Publish All button (Chair / Admin)
  document.getElementById("btn-publish-all")?.addEventListener("click", async () => {
    const progVal = document.getElementById("filter-program")?.value;
    const secVal = document.getElementById("filter-section")?.value;
    const scopeLabel = secVal ? `Section` : progVal ? `Program ${progVal}` : "all";
    if (!confirm(`Validate and publish ${scopeLabel} conflict-free draft schedules? This will lock the official timetable.`)) return;
    const btn = document.getElementById("btn-publish-all");
    btn.disabled = true;
    btn.textContent = "Publishing…";

    const payload = {};
    if (progVal) payload.program = progVal;
    if (secVal) payload.section_id = parseInt(secVal, 10);

    try {
      const res = await API.publishAllSchedules(payload);
      showToast(res.message || "Schedules successfully published!", "success");
      await fetchAndRender();
    } catch (err) {
      const msg = err.data?.message || err.message || "Cannot publish: Unresolved hard conflicts exist. Please resolve them in the Conflict Radar.";
      showToast(msg, "error");
      openRadar();
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg> Publish`;
    }
  });

  // Batch Unpublish All button (Chair / Admin)
  document.getElementById("btn-unpublish-all")?.addEventListener("click", async () => {
    const progVal = document.getElementById("filter-program")?.value;
    const secVal = document.getElementById("filter-section")?.value;
    const scopeLabel = secVal ? `Section` : progVal ? `Program ${progVal}` : "all";
    if (!confirm(`Revert ${scopeLabel} published schedules back to DRAFT mode? This will make schedules editable again.`)) return;
    const btn = document.getElementById("btn-unpublish-all");
    btn.disabled = true;
    btn.textContent = "Unpublishing…";

    const payload = {};
    if (progVal) payload.program = progVal;
    if (secVal) payload.section_id = parseInt(secVal, 10);

    try {
      const res = await API.unpublishAllSchedules(payload);
      showToast(res.message || "Schedules reverted to draft mode.", "info");
      await fetchAndRender();
    } catch (err) {
      showToast(err.message || "Unpublish failed.", "error");
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12h18M12 3v18"/></svg> Unpublish`;
    }
  });

  // Term synchronization
  document.getElementById("filter-term")?.addEventListener("change", (e) => {
    localStorage.setItem("coe_sync_active_term", e.target.value);
    window.dispatchEvent(new CustomEvent("academicTermChanged", { detail: { term: e.target.value } }));
    cascadeScheduleFilters();
    fetchAndRender();
  });

  // Immediate preflight conflict checks on modal fields
  ["m-room", "m-day", "m-start", "m-end", "m-faculty"].forEach(id => {
    document.getElementById(id)?.addEventListener("change", () => {
      const get = elId => document.getElementById(elId)?.value?.trim();
      if (get("m-room") && get("m-day") && get("m-start") && get("m-end")) {
        runPreflight();
      }
    });
  });

  // Week & Day navigation
  document.getElementById("btn-prev-week")?.addEventListener("click", () => {
    if (_activeViewMode === "DAY") {
      _activeDayIndex = (_activeDayIndex - 1 + 7) % 7;
    } else {
      _weekOffset--;
    }
    refreshWeekHeaders();
    updateWeekLabel();
    renderEventCards(_schedules);
  });
  document.getElementById("btn-next-week")?.addEventListener("click", () => {
    if (_activeViewMode === "DAY") {
      _activeDayIndex = (_activeDayIndex + 1) % 7;
    } else {
      _weekOffset++;
    }
    refreshWeekHeaders();
    updateWeekLabel();
    renderEventCards(_schedules);
  });
  document.getElementById("btn-today")?.addEventListener("click", () => {
    _weekOffset = 0;
    const today = new Date().getDay();
    _activeDayIndex = today === 0 ? 6 : today - 1;
    refreshWeekHeaders();
    updateWeekLabel();
    renderEventCards(_schedules);
  });

  // Filters (Multi-dropdown toolbar with dynamic cascading)
  document.getElementById("filter-program")?.addEventListener("change", () => {
    cascadeScheduleFilters();
    fetchAndRender();
  });
  document.getElementById("filter-year")?.addEventListener("change", () => {
    cascadeScheduleFilters();
    fetchAndRender();
  });
  [
    "filter-section",
    "filter-faculty",
    "filter-room",
    "filter-status",
    "filter-subject",
    "filter-room-type-sched",
  ].forEach(id => {
    document.getElementById(id)?.addEventListener("change", fetchAndRender);
  });

  // Radar Open/Close/Refresh
  document.getElementById("btn-conflict-radar")?.addEventListener("click", openRadar);
  document.getElementById("radar-close-btn")?.addEventListener("click", closeRadar);
  document.getElementById("radar-overlay")?.addEventListener("click", closeRadar);
  document.getElementById("radar-refresh-btn")?.addEventListener("click", runRadarScan);

  // Radar Category Navigation tabs
  document.querySelectorAll(".radar-cat-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".radar-cat-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      _radarCategory = btn.dataset.category || "ALL";
      renderRadarConflictList();
    });
  });

  // Modal
  document.getElementById("sched-modal-close")?.addEventListener("click", closeModal);
  document.getElementById("sched-modal-cancel")?.addEventListener("click", closeModal);
  document.getElementById("sched-modal-backdrop")?.addEventListener("click", (e) => {
    if (e.target === e.currentTarget) closeModal();
  });
  document.getElementById("sched-modal-form")?.addEventListener("submit", submitScheduleForm);
  document.getElementById("btn-preflight")?.addEventListener("click", runPreflight);

  // Keyboard
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { closeModal(); closeRadar(); }
  });
}

function renderRadarConflictList() {
  const emptyEl = document.getElementById("radar-empty");
  const listEl  = document.getElementById("radar-conflict-list");
  if (!emptyEl || !listEl) return;

  const filtered = _radarCategory === "ALL"
    ? _allConflicts
    : _allConflicts.filter(c => c.type.toUpperCase() === _radarCategory);

  if (filtered.length === 0) {
    emptyEl.style.display = "flex";
    listEl.style.display  = "none";
    if (_allConflicts.length > 0 && _radarCategory !== "ALL") {
      emptyEl.querySelector("p").textContent = `No ${_radarCategory.toLowerCase()} conflicts`;
      emptyEl.querySelector("span").textContent = `0 clashes under selected category filter`;
    } else {
      emptyEl.querySelector("p").textContent = "No conflicts detected";
      emptyEl.querySelector("span").textContent = "All schedules pass hard constraints";
    }
  } else {
    emptyEl.style.display = "none";
    listEl.style.display  = "block";
    listEl.innerHTML = filtered.map(c => buildConflictCard(c)).join("");

    const isAdmin = window.CURRENT_ROLE === "CHAIR" || window.CURRENT_ROLE === "ADMIN";
    if (isAdmin) {
      listEl.querySelectorAll(".alt-apply-btn").forEach(btn => {
        btn.addEventListener("click", () => {
          const data = JSON.parse(btn.dataset.alt);
          applyAlternative(data, parseInt(btn.dataset.schedId));
        });
      });
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────────────────────────────────────
function timeToMin(t) {
  if (!t) return 0;
  const parts = String(t).split(":");
  return parseInt(parts[0]) * 60 + parseInt(parts[1]);
}

function formatTimeTo12(t) {
  if (!t) return "—";
  const [hStr, mStr] = String(t).split(":");
  const h = parseInt(hStr), m = parseInt(mStr);
  const period = h >= 12 ? "PM" : "AM";
  const hh = h % 12 || 12;
  return `${hh}:${String(m).padStart(2,"0")} ${period}`;
}

function formatTimeLabel(h, m) {
  const period = h >= 12 ? "PM" : "AM";
  const hh = h % 12 || 12;
  return `${hh}${m ? ":"+String(m).padStart(2,"0") : ""} ${period}`;
}

function setSelectVal(id, val) {
  const el = document.getElementById(id);
  if (!el || val === undefined || val === null) return;
  el.value = String(val);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g,"&amp;")
    .replace(/</g,"&lt;")
    .replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;")
    .replace(/'/g,"&#39;");
}

function escapeAttr(str) {
  return String(str).replace(/'/g,"&apos;").replace(/"/g,"&quot;");
}

function showToast(msg, type = "info") {
  if (typeof window.showToast === "function" && window.showToast !== showToast) {
    window.showToast(msg, type);
    return;
  }
  const el = document.getElementById("app-toast");
  if (!el) return;
  el.textContent = msg;
  el.className   = `toast-msg toast-${type} toast-show`;
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.remove("toast-show"), 3500);
}

// Make openModal globally accessible (for conflict radar inline buttons)
window.openModal = openModal;

// ─────────────────────────────────────────────────────────────────────────────
// Drag and Drop Timetable Rescheduling Handlers
// ─────────────────────────────────────────────────────────────────────────────
function handleColumnDragOver(e, col, day) {
  if (!_draggedSchedule) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = "move";
  col.classList.add("drag-over");

  let guide = col.querySelector(".drag-drop-slot-guide");
  if (!guide) {
    guide = document.createElement("div");
    guide.className = "drag-drop-slot-guide";
    col.appendChild(guide);
  }

  const rect = col.getBoundingClientRect();
  const relY = Math.max(0, e.clientY - rect.top + col.scrollTop);
  const slotIndex = Math.floor(relY / ROW_PX);
  const totalMin = GRID_START_HOUR * 60 + slotIndex * SLOT_MINUTES;
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  const timeStr = `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
  const topPx = slotIndex * ROW_PX;

  const startM = timeToMin(_draggedSchedule.start_time);
  const endM = timeToMin(_draggedSchedule.end_time);
  const durMin = (endM > startM ? endM - startM : 90);
  const heightPx = Math.max(28, durMin * PIXELS_PER_MINUTE - 4);

  guide.style.top = `${topPx}px`;
  guide.style.height = `${heightPx}px`;
  guide.textContent = `Drop at ${day} ${timeStr}`;
}

function handleColumnDragLeave(e, col) {
  if (e.relatedTarget && col.contains(e.relatedTarget)) return;
  col.classList.remove("drag-over");
  col.querySelector(".drag-drop-slot-guide")?.remove();
}

function handleColumnDrop(e, col, day) {
  if (!_draggedSchedule) return;
  e.preventDefault();
  col.classList.remove("drag-over");
  col.querySelector(".drag-drop-slot-guide")?.remove();

  const rect = col.getBoundingClientRect();
  const relY = Math.max(0, e.clientY - rect.top + col.scrollTop);
  const slotIndex = Math.floor(relY / ROW_PX);
  const totalMin = GRID_START_HOUR * 60 + slotIndex * SLOT_MINUTES;
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  if (h >= GRID_END_HOUR) return;
  const timeStr = `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
  const draggedId = _draggedSchedule.id;
  _draggedSchedule = null;
  executeScheduleMove(draggedId, day, timeStr, null);
}

async function executeScheduleMove(scheduleId, targetDay, targetStartTime, targetScheduleId) {
  try {
    const payload = {
      target_day: targetDay,
      target_start_time: targetStartTime,
      target_schedule_id: targetScheduleId || null,
    };
    const res = await API.post(`/api/schedules/${scheduleId}/drag-move`, payload);

    if (res && res.status === "success") {
      await fetchAndRender();
      await fetchLiveUtilization();

      const hasDisplaced = res.displaced_adjustments && res.displaced_adjustments.length > 0;
      const hasWarnings = res.warnings && res.warnings.length > 0;

      if (hasDisplaced || hasWarnings) {
        showRescheduleWarning(res.message, res.warnings, res.displaced_adjustments);
      } else {
        showToast(res.message || "Schedule updated successfully.", "success");
      }
    } else {
      showToast(res?.message || "Could not move schedule slot.", "error");
    }
  } catch (err) {
    console.error("Drag move error:", err);
    showToast(err.message || "Error moving schedule slot.", "error");
  }
}

function showRescheduleWarning(titleMsg, warnings = [], displaced = []) {
  const banner = document.getElementById("reschedule-warning-banner");
  const titleEl = document.getElementById("reschedule-warning-title");
  const bodyEl = document.getElementById("reschedule-warning-body");
  if (!banner) return;

  if (titleEl) {
    titleEl.textContent = titleMsg || "Timetable Rescheduling Notice: Automatic Slot Adjustment";
  }

  let bodyHtml = "";
  if (displaced && displaced.length > 0) {
    bodyHtml += `<div style="margin-bottom: 6px;"><strong>Auto-Adjusted Course Slots:</strong><ul style="margin: 4px 0 0 18px; padding: 0;">`;
    displaced.forEach(d => {
      bodyHtml += `<li>${escapeHtml(d.message || (d.subject + " shifted to " + d.new_slot))}</li>`;
    });
    bodyHtml += `</ul></div>`;
  }

  if (warnings && warnings.length > 0) {
    bodyHtml += `<div><strong>Rescheduling Notes & Potential Overlaps:</strong><ul style="margin: 4px 0 0 18px; padding: 0;">`;
    warnings.forEach(w => {
      bodyHtml += `<li>${escapeHtml(w)}</li>`;
    });
    bodyHtml += `</ul></div>`;
  }

  if (bodyEl) {
    bodyEl.innerHTML = bodyHtml || "A class was rescheduled and adjacent slots were shifted accordingly.";
  }

  banner.style.display = "block";
  banner.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

window.dismissRescheduleWarning = function() {
  const banner = document.getElementById("reschedule-warning-banner");
  if (banner) {
    banner.style.display = "none";
  }
};

