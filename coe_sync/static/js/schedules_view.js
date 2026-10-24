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
const GRID_END_HOUR     = 19;   // last row starts at 19:00, ends 19:30
const SLOT_MINUTES      = 30;   // each row = 30 min
const ROW_PX            = 52;   // pixel height of one 30-min slot
const DAYS = ["MON","TUE","WED","THU","FRI","SAT","SUN"];
const DAY_LABELS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];

// ─────────────────────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────────────────────
let _weekOffset    = 0;       // 0 = current week, ±N weeks
let _schedules     = [];      // raw API data
let _editingId     = null;    // null = create, number = update
let _masterData    = { sections:[], faculty:[], rooms:[], subjects:[] };
let _radarCategory = "ALL";   // "ALL" | "ROOM" | "FACULTY" | "SECTION" | "CAPACITY"
let _allConflicts  = [];      // current detected conflicts

// ─────────────────────────────────────────────────────────────────────────────
// Boot
// ─────────────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  buildStaticGrid();
  await loadMasterData();
  populateFilterSelects();
  populateModalSelects();
  buildTimeSlotOptions();
  bindEvents();
  await fetchAndRender();
  updateWeekLabel();

  // Check URL query parameters
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get("radar") === "open") {
    setTimeout(openRadar, 300);
  }
  if (urlParams.get("section_id")) {
    setSelectVal("filter-section", urlParams.get("section_id"));
    fetchAndRender();
  }
  if (urlParams.get("program")) {
    setSelectVal("filter-program", urlParams.get("program"));
    fetchAndRender();
  }
});

window.addEventListener("roleChanged", () => {
  fetchAndRender();
  if (document.getElementById("radar-drawer")?.classList.contains("radar-drawer--open")) {
    runRadarScan();
  }
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

  const today = new Date();
  const monday = getWeekMonday(today, _weekOffset);

  DAYS.forEach((_, i) => {
    const date = new Date(monday);
    date.setDate(monday.getDate() + i);
    const isToday = date.toDateString() === today.toDateString();

    const cell = document.createElement("div");
    cell.className = "th-day" + (isToday ? " th-day--today" : "");
    cell.dataset.dayIndex = i;
    cell.innerHTML = `
      <span class="th-day-label">${DAY_LABELS[i]}</span>
      <span class="th-day-num ${isToday ? "th-day-num--today" : ""}">${date.getDate()}</span>
    `;
    header.appendChild(cell);
  });
}

function buildTimeGutter() {
  const gutter = document.getElementById("timetable-gutter");
  if (!gutter) return;
  gutter.innerHTML = "";

  let hour = GRID_START_HOUR;
  let min  = 0;

  while (hour < GRID_END_HOUR || (hour === GRID_END_HOUR && min === 0)) {
    const label = document.createElement("div");
    label.className = "gutter-slot" + (min === 30 ? " gutter-slot--half" : "");
    label.textContent = min === 0 ? formatTimeLabel(hour, 0) : "";
    gutter.appendChild(label);
    min += 30;
    if (min >= 60) { min = 0; hour++; }
  }
}

function buildDayColumns() {
  const container = document.getElementById("timetable-columns");
  if (!container) return;
  container.innerHTML = "";

  const totalSlots = (GRID_END_HOUR - GRID_START_HOUR) * 2 + 1; // +1 for 19:00 row

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
      if (h > GRID_END_HOUR) return;
      openModal(null, { day_of_week: day, start_time: `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}` });
    });

    container.appendChild(col);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. Master Data Load
// ─────────────────────────────────────────────────────────────────────────────
async function loadMasterData() {
  try {
    const [secRes, facRes, roomRes, subjRes] = await Promise.all([
      API.get("/api/sections"),
      API.get("/api/faculty"),
      API.get("/api/rooms"),
      API.get("/api/subjects"),
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
// ─────────────────────────────────────────────────────────────────────────────
function populateFilterSelects() {
  const secSel  = document.getElementById("filter-section");
  const facSel  = document.getElementById("filter-faculty");
  const roomSel = document.getElementById("filter-room");

  if (secSel) {
    secSel.innerHTML = `<option value="">All Sections</option>` +
      _masterData.sections.map(s => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join("");
  }
  if (facSel) {
    facSel.innerHTML = `<option value="">All Faculty</option>` +
      _masterData.faculty.map(f => `<option value="${f.id}">${escapeHtml(f.name)}</option>`).join("");
  }
  if (roomSel) {
    roomSel.innerHTML = `<option value="">All Rooms</option>` +
      _masterData.rooms.map(r => `<option value="${r.id}">${escapeHtml(r.room_code)}</option>`).join("");
  }
}

function populateModalSelects() {
  const mSubj = document.getElementById("m-subject");
  const mSec  = document.getElementById("m-section");
  const mFac  = document.getElementById("m-faculty");
  const mRoom = document.getElementById("m-room");

  if (mSubj) mSubj.innerHTML = `<option value="">Select subject…</option>` +
    _masterData.subjects.map(s =>
      `<option value="${s.id}">${escapeHtml(s.code)} — ${escapeHtml(s.name)}</option>`
    ).join("");

  if (mSec) mSec.innerHTML = `<option value="">Select section…</option>` +
    _masterData.sections.map(s =>
      `<option value="${s.id}">${escapeHtml(s.name)} (${escapeHtml(s.program)})</option>`
    ).join("");

  if (mFac) mFac.innerHTML = `<option value="">Select faculty…</option>` +
    _masterData.faculty.map(f =>
      `<option value="${f.id}">${escapeHtml(f.name)}</option>`
    ).join("");

  if (mRoom) mRoom.innerHTML = `<option value="">Select room…</option>` +
    _masterData.rooms.map(r =>
      `<option value="${r.id}">${escapeHtml(r.room_code)} (cap ${r.capacity})</option>`
    ).join("");
}

function buildTimeSlotOptions() {
  const slots = [];
  for (let h = GRID_START_HOUR; h <= GRID_END_HOUR + 1; h++) {
    for (let m = 0; m < 60; m += 30) {
      if (h === GRID_END_HOUR + 1 && m > 0) break;
      slots.push(`${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}`);
    }
  }

  const mStart = document.getElementById("m-start");
  const mEnd   = document.getElementById("m-end");

  if (mStart) {
    mStart.innerHTML = `<option value="">Start time…</option>` +
      slots.map(t => `<option value="${t}">${formatTimeTo12(t)}</option>`).join("");
  }
  if (mEnd) {
    mEnd.innerHTML = `<option value="">End time…</option>` +
      slots.map(t => `<option value="${t}">${formatTimeTo12(t)}</option>`).join("");
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. Fetch Schedules + Render
// ─────────────────────────────────────────────────────────────────────────────
async function fetchAndRender() {
  const params = {};
  const secVal   = document.getElementById("filter-section")?.value;
  const facVal   = document.getElementById("filter-faculty")?.value;
  const roomVal  = document.getElementById("filter-room")?.value;
  const progVal  = document.getElementById("filter-program")?.value;
  const yearVal  = document.getElementById("filter-year")?.value;
  const statVal  = document.getElementById("filter-status")?.value;

  if (secVal)  params.section_id = secVal;
  if (facVal)  params.faculty_id = facVal;
  if (roomVal) params.room_id    = roomVal;
  if (progVal) params.program    = progVal;
  if (yearVal) params.year_level = yearVal;

  try {
    const res = await API.getSchedules(params);
    _schedules = res?.data || [];

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

    // Role-level safety: Students must never see DRAFT schedules
    if (window.CURRENT_ROLE === "STUDENT") {
      visible = visible.filter(s => s.status === "PUBLISHED");
    }

    renderEventCards(visible);
    updateRadarBadge(_schedules);
    updateRoleSpecificPortals(visible);
  } catch (err) {
    console.warn("Schedule fetch error:", err);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. Render Event Cards (pixel-spanning)
// ─────────────────────────────────────────────────────────────────────────────
function renderEventCards(schedules) {
  // Clear all columns
  DAYS.forEach(day => {
    const col = document.getElementById(`col-${day}`);
    if (!col) return;
    col.querySelectorAll(".event-card-v2").forEach(el => el.remove());
  });

  // Bucket by day
  const byDay = {};
  DAYS.forEach(d => byDay[d] = []);
  schedules.forEach(s => {
    if (byDay[s.day_of_week]) byDay[s.day_of_week].push(s);
  });

  DAYS.forEach(day => {
    const col = document.getElementById(`col-${day}`);
    if (!col) return;

    const items = byDay[day];
    resolveOverlaps(items); // adds .col & .cols fields for side-by-side

    items.forEach(s => {
      const card = buildEventCard(s);
      col.appendChild(card);
    });
  });
}

/** Assign column position for overlapping cards within the same day */
function resolveOverlaps(items) {
  items.forEach(s => {
    s._startMin = timeToMin(s.start_time);
    s._endMin   = timeToMin(s.end_time);
    s._col = 0;
    s._cols = 1;
  });

  for (let i = 0; i < items.length; i++) {
    const overlaps = [items[i]];
    for (let j = 0; j < items.length; j++) {
      if (i !== j && overlapping(items[i], items[j])) {
        overlaps.push(items[j]);
      }
    }
    items[i]._cols = overlaps.length;
    items[i]._col  = overlaps.indexOf(items[i]);
  }
}

function overlapping(a, b) {
  return a._startMin < b._endMin && b._startMin < a._endMin;
}

function buildEventCard(s) {
  const startMin  = timeToMin(s.start_time);
  const endMin    = timeToMin(s.end_time);
  const topPx     = ((startMin - GRID_START_HOUR * 60) / SLOT_MINUTES) * ROW_PX;
  const heightPx  = ((endMin - startMin) / SLOT_MINUTES) * ROW_PX;

  const isConflict = s.has_conflict;
  const cardClass  = isConflict ? "event-card-v2 ev-conflict"
                   : s.status === "DRAFT" ? "event-card-v2 ev-draft"
                   : "event-card-v2 ev-scheduled";

  const widthPct   = 100 / (s._cols || 1);
  const leftPct    = widthPct * (s._col || 0);

  const card = document.createElement("div");
  card.className    = cardClass;
  card.dataset.id   = s.id;
  card.style.top    = `${topPx}px`;
  card.style.height = `${Math.max(heightPx - 4, 20)}px`;
  card.style.left   = `calc(${leftPct}% + 2px)`;
  card.style.width  = `calc(${widthPct}% - 4px)`;

  const dur = endMin - startMin;
  const isShort = dur <= 30;
  const isAdmin = window.CURRENT_ROLE === "CHAIR" || window.CURRENT_ROLE === "ADMIN";
  const isStudent = window.CURRENT_ROLE === "STUDENT";

  card.innerHTML = `
    <div class="ev-body">
      <div class="ev-title">${escapeHtml(s.subject_code || s.subject_name || "Unknown")}</div>
      ${!isShort ? `
        <div class="ev-meta">${escapeHtml(s.room_code || "—")}</div>
        <div class="ev-meta">${escapeHtml(s.section_name || "—")}</div>
        <div class="ev-meta ev-faculty">${escapeHtml(s.faculty_name || "—")}</div>
      ` : ""}
      ${isConflict ? `<div class="ev-conflict-badge">⚠ Conflict</div>` : ""}
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
    ` : isStudent && s.status === "PUBLISHED" ? `
      <div class="ev-actions" style="opacity: 1;">
        <button class="btn-card-reschedule" data-schedule-id="${s.id}" title="Request Reschedule for this class">
          ✎ Reschedule
        </button>
      </div>
    ` : ""}
  `;

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
  }

  // Bind student reschedule button
  if (isStudent) {
    card.querySelector(".btn-card-reschedule")?.addEventListener("click", (e) => {
      e.stopPropagation();
      if (typeof window.openRescheduleModal === "function") {
        window.openRescheduleModal("new", s.id);
      }
    });
  }

  // Click card: if conflicted, open Conflict Radar; if admin, open edit modal
  card.addEventListener("click", () => {
    if (s.has_conflict) {
      openRadar();
    } else if (isAdmin) {
      openModal(s.id);
    }
  });

  return card;
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

    if (facNameElem && schedules[0]?.faculty_name) {
      facNameElem.textContent = schedules[0].faculty_name;
    }

    // Fetch official workload metrics from API
    API.getAnalyticsReports().then(res => {
      if (res?.data?.faculty_workload?.faculty) {
        const facItem = res.data.faculty_workload.faculty.find(f => schedules.some(s => s.faculty_id === f.id)) || res.data.faculty_workload.faculty[0];
        if (facItem) {
          if (facNameElem) facNameElem.textContent = facItem.name;
          if (facNumbersElem) {
            facNumbersElem.textContent = `${facItem.assigned_units} / ${facItem.max_units} Units (${facItem.teaching_hours} hrs/wk)`;
          }
          if (facMeterFill) {
            facMeterFill.style.width = `${Math.min(100, facItem.utilization_rate)}%`;
            facMeterFill.className = `faculty-meter-fill ${facItem.is_overloaded ? 'overload' : facItem.assigned_units >= 19 ? 'warning' : ''}`;
          }
          if (facBadge) {
            if (facItem.is_overloaded) {
              facBadge.className = "status-badge crimson";
              facBadge.textContent = "OVERLOADED (>21u)";
            } else if (facItem.assigned_units >= 19) {
              facBadge.className = "status-badge amber";
              facBadge.textContent = "NEAR CAPACITY";
            } else {
              facBadge.className = "status-badge mint";
              facBadge.textContent = "NORMAL LOAD";
            }
          }
        }
      }
    }).catch(() => {});

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
    if (secLabel && schedules[0]?.section_name) {
      secLabel.textContent = `Section ${schedules[0].section_name} (Official Published Schedule)`;
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
      CAPACITY: conflicts.filter(c => c.type === "capacity").length,
    };
    const cAll = document.getElementById("cat-count-all");
    const cRoom = document.getElementById("cat-count-room");
    const cFac = document.getElementById("cat-count-faculty");
    const cSec = document.getElementById("cat-count-section");
    const cCap = document.getElementById("cat-count-capacity");
    if (cAll) cAll.textContent = catCounts.ALL;
    if (cRoom) cRoom.textContent = catCounts.ROOM;
    if (cFac) cFac.textContent = catCounts.FACULTY;
    if (cSec) cSec.textContent = catCounts.SECTION;
    if (cCap) cCap.textContent = catCounts.CAPACITY;

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

    // Check capacity overflow
    const sec = _masterData.sections.find(x => x.id === a.section_id);
    const rm  = _masterData.rooms.find(x => x.id === a.room_id);
    if (sec && rm && sec.student_count > rm.capacity) {
      conflicts.push({
        type: "capacity",
        resource: `${rm.room_code} (Cap: ${rm.capacity}) vs ${sec.name} (${sec.student_count} studs)`,
        schedA: a,
        schedB: null,
      });
    }

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
    capacity: "👥",
  };
  const typeLabels = {
    room: "Room Double-Booking",
    faculty: "Faculty Overlap",
    section: "Section Collision",
    capacity: "Capacity Overflow",
  };

  const typeIcon  = typeIcons[c.type] || "⚠️";
  const typeLabel = typeLabels[c.type] || "Constraint Violation";
  const isAdmin   = window.CURRENT_ROLE === "CHAIR" || window.CURRENT_ROLE === "ADMIN";

  if (c.type === "capacity") {
    return `
      <div class="conflict-card">
        <div class="conflict-type">
          <span>${typeIcon} ${typeLabel}</span>
          <span class="conflict-resource">${escapeHtml(c.resource || "")}</span>
        </div>
        <div class="conflict-pair">
          <div class="conflict-entry" style="flex:1;">
            <strong>${escapeHtml(c.schedA.subject_code)}</strong>
            <span>${escapeHtml(c.schedA.section_name)} · ${escapeHtml(c.schedA.faculty_name)} · Room ${escapeHtml(c.schedA.room_code)}</span>
            <span class="conflict-time">${c.schedA.day_of_week} ${formatTimeTo12(c.schedA.start_time)}–${formatTimeTo12(c.schedA.end_time)}</span>
          </div>
        </div>
        <div class="conflict-actions">
          ${isAdmin ? `
            <button class="btn btn-sm btn-outline" onclick="openModal(${c.schedA.id})">Edit #${c.schedA.id}</button>
            <button class="btn btn-sm btn-conflict-alt alt-apply-btn"
              data-sched-id="${c.schedA.id}"
              data-alt="${escapeAttr(JSON.stringify({ subject_id: c.schedA.subject_id, section_id: c.schedA.section_id, faculty_id: c.schedA.faculty_id, room_id: c.schedA.room_id, day_of_week: c.schedA.day_of_week, start_time: c.schedA.start_time, end_time: c.schedA.end_time }))}">
              🔁 Find Larger Room
            </button>
          ` : `
            <span style="font-size:11px; color:var(--text-muted); font-style:italic;">Read-only (Chair access required to resolve)</span>
          `}
        </div>
      </div>
    `;
  }

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
  const titleEl   = document.getElementById("sched-modal-title");
  const saveBtn   = document.getElementById("sched-modal-save");
  const form      = document.getElementById("sched-modal-form");
  const preflightBanner  = document.getElementById("preflight-banner");
  const suggestionsPanel = document.getElementById("suggestions-panel");

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
    }
  } else {
    titleEl.textContent = "Add New Schedule";
    saveBtn.textContent = "Save Schedule";
    // Apply prefill values from click-on-grid
    if (prefill.day_of_week) setSelectVal("m-day", prefill.day_of_week);
    if (prefill.start_time)  setSelectVal("m-start", prefill.start_time);
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
  const monday = getWeekMonday(new Date(), _weekOffset);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  const fmt = (d) => d.toLocaleDateString("en-US", { month:"short", day:"numeric" });
  label.textContent = `${fmt(monday)} – ${fmt(sunday)}`;
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
// ─────────────────────────────────────────────────────────────────────────────
// 10. Event Bindings
// ─────────────────────────────────────────────────────────────────────────────
function bindEvents() {
  // Add schedule button
  document.getElementById("btn-add-schedule")?.addEventListener("click", () => openModal());

  // Print schedule
  document.getElementById("btn-print-schedule")?.addEventListener("click", () => {
    window.print();
  });

  // Batch Publish All button (Chair / Admin)
  document.getElementById("btn-publish-all")?.addEventListener("click", async () => {
    if (!confirm("Validate and publish all conflict-free draft schedules? This will lock the official timetable.")) return;
    const btn = document.getElementById("btn-publish-all");
    btn.disabled = true;
    btn.textContent = "Publishing…";
    try {
      const res = await API.publishAllSchedules();
      showToast(res.message || "All schedules successfully published!", "success");
      await fetchAndRender();
    } catch (err) {
      showToast(err.message || "Cannot publish: Conflicts exist.", "error");
      openRadar();
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg> Publish All`;
    }
  });

  // Week navigation
  document.getElementById("btn-prev-week")?.addEventListener("click", () => {
    _weekOffset--;
    refreshWeekHeaders();
    updateWeekLabel();
  });
  document.getElementById("btn-next-week")?.addEventListener("click", () => {
    _weekOffset++;
    refreshWeekHeaders();
    updateWeekLabel();
  });
  document.getElementById("btn-today")?.addEventListener("click", () => {
    _weekOffset = 0;
    refreshWeekHeaders();
    updateWeekLabel();
  });

  // Filters (Multi-dropdown toolbar)
  [
    "filter-program",
    "filter-year",
    "filter-section",
    "filter-faculty",
    "filter-room",
    "filter-status",
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
