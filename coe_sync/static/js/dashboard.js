/**
 * COE SYNC 2026 - Dashboard Controller (dashboard.js)
 * Implements KPI cards, live Conflict Radar overview, Schedule Table browser,
 * filters (Program, Section, Room), View Toggle, Export CSV, Print, and Draft Generator.
 */

let _dashSchedules = [];
let _dashSections = [];
let _dashRooms = [];

document.addEventListener("DOMContentLoaded", async () => {
  await loadDashboardMetrics();
  await loadDashboardData();
  bindDashboardEvents();

  window.addEventListener("roleChanged", () => {
    loadDashboardMetrics();
    loadDashboardData();
  });
});

async function loadDashboardMetrics() {
  try {
    const [analyticsRes, roomsRes, facultyRes, schedRes] = await Promise.all([
      API.getAnalyticsSummary(),
      API.get("/api/rooms"),
      API.get("/api/faculty"),
      API.get("/api/schedules"),
    ]);

    if (analyticsRes.status === "success") {
      const d = analyticsRes.data;
      const schedElem = document.getElementById("kpi-schedules");
      const confElem = document.getElementById("kpi-conflicts");
      const confCard = document.getElementById("kpi-card-conflicts");
      const radarCount = document.getElementById("radar-count-link");
      const radarList = document.getElementById("radar-list");
      const qScore = document.getElementById("dash-quality-score");
      const rUtil = document.getElementById("dash-room-util");

      if (schedElem) schedElem.textContent = d.total_classes;
      if (confElem) confElem.textContent = d.unresolved_conflicts;
      const utilPct = d.overall_room_utilization_pct !== undefined ? d.overall_room_utilization_pct : (d.room_utilization || 0);
      if (rUtil) rUtil.textContent = `${Number(utilPct).toFixed(2)}%`;

      if (d.unresolved_conflicts > 0) {
        if (confCard) confCard.classList.add("kpi-card-conflict");
        if (radarCount) {
          radarCount.textContent = `View all ${d.unresolved_conflicts}`;
          radarCount.style.display = "inline";
        }
      } else {
        if (confCard) confCard.classList.remove("kpi-card-conflict");
        if (radarCount) radarCount.style.display = "none";
      }

      // Populate Live Conflict Radar List
      if (radarList) {
        const rawSchedules = schedRes?.data || [];
        const detected = detectConflictsSimple(rawSchedules);

        if (detected.length === 0) {
          radarList.innerHTML = `
            <div class="radar-row" style="padding: 24px 0; justify-content: center; color: #059669; font-weight: 600;">
              <span>✓ All Academic Timetables Clean &bull; Zero Hard Constraint Collisions</span>
            </div>
          `;
        } else {
          radarList.innerHTML = detected.slice(0, 5).map(c => `
            <div class="radar-row">
              <div class="radar-title">
                <span class="radar-dot" style="background-color: var(--event-conflict-indicator);"></span>
                <span>${escapeHtml(c.title)}</span>
              </div>
              <div class="radar-meta">${escapeHtml(c.meta)}</div>
            </div>
          `).join("");
        }
      }
    }

    if (roomsRes.status === "success") {
      const roomElem = document.getElementById("kpi-rooms");
      if (roomElem) roomElem.textContent = roomsRes.count;
    }

    if (facultyRes.status === "success") {
      const facElem = document.getElementById("kpi-faculty");
      if (facElem) facElem.textContent = facultyRes.count;
    }
  } catch (err) {
    console.warn("Failed to load dashboard metrics:", err);
  }
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
  if (p === "GEN") return "GEN";
  return p;
}

function cascadeDashboardSections() {
  const prog = document.getElementById("dash-filter-prog")?.value || "";
  const year = document.getElementById("dash-filter-year")?.value || "";
  const secSelect = document.getElementById("dash-filter-sec");
  if (!secSelect) return;

  const currentSecVal = secSelect.value;
  let matchingSections = _dashSections;
  if (prog) {
    matchingSections = matchingSections.filter(s => normalizeProgram(s.program) === normalizeProgram(prog));
  }
  if (year) {
    matchingSections = matchingSections.filter(s => String(s.year_level) === String(year));
  }

  secSelect.innerHTML = `<option value="">All Sections</option>` +
    matchingSections.map(s => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join("");

  if (currentSecVal && matchingSections.some(s => String(s.id) === String(currentSecVal))) {
    secSelect.value = currentSecVal;
  } else {
    secSelect.value = "";
  }
}

async function loadDashboardData() {
  try {
    const [schedRes, secRes, rmRes] = await Promise.all([
      API.get("/api/schedules"),
      API.get("/api/sections"),
      API.get("/api/rooms"),
    ]);

    _dashSchedules = schedRes?.data || [];
    _dashSections = secRes?.data || [];
    _dashRooms = rmRes?.data || [];

    // Populate filter dropdowns
    const rmSelect = document.getElementById("dash-filter-room");
    if (rmSelect) {
      rmSelect.innerHTML = `<option value="">All Rooms</option>` +
        _dashRooms.map(r => `<option value="${r.id}">${escapeHtml(r.room_code)}</option>`).join("");
    }

    cascadeDashboardSections();
    renderDashboardTable();
  } catch (err) {
    console.warn("Failed to load dashboard schedule data:", err);
  }
}

function renderDashboardTable() {
  const tbody = document.getElementById("dash-table-body");
  if (!tbody) return;

  const prog = document.getElementById("dash-filter-prog")?.value;
  const year = document.getElementById("dash-filter-year")?.value;
  const sec = document.getElementById("dash-filter-sec")?.value;
  const rm = document.getElementById("dash-filter-room")?.value;
  const status = document.getElementById("dash-filter-status")?.value;

  let filtered = _dashSchedules;

  if (prog) {
    const sectionIds = _dashSections
      .filter(s => normalizeProgram(s.program) === normalizeProgram(prog))
      .map(s => s.id);
    filtered = filtered.filter(s => sectionIds.includes(s.section_id));
  }
  if (year) {
    const sectionIds = _dashSections
      .filter(s => String(s.year_level) === String(year))
      .map(s => s.id);
    filtered = filtered.filter(s => sectionIds.includes(s.section_id));
  }
  if (sec) {
    filtered = filtered.filter(s => s.section_id === parseInt(sec));
  }
  if (rm) {
    filtered = filtered.filter(s => s.room_id === parseInt(rm));
  }
  if (status) {
    filtered = filtered.filter(s => (s.status || "").toUpperCase() === status.toUpperCase());
  }

  // Row-level security for student
  if (window.CURRENT_ROLE === "STUDENT") {
    filtered = filtered.filter(s => s.status === "PUBLISHED");
  }

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 24px; color: var(--text-muted);">No matching schedules found.</td></tr>`;
    renderDashboardGrid(filtered);
    return;
  }

  tbody.innerHTML = filtered.map(s => `
    <tr>
      <td><strong>${s.day_of_week}</strong></td>
      <td>${formatTimeTo12(s.start_time)} – ${formatTimeTo12(s.end_time)}</td>
      <td><strong>${escapeHtml(s.subject_code || "")}</strong> <span style="font-size:11px; color:var(--text-muted);">${escapeHtml(s.subject_name || "")}</span></td>
      <td>${escapeHtml(s.section_name || "—")}</td>
      <td>${escapeHtml(s.faculty_name || "—")}</td>
      <td>${escapeHtml(s.room_code || "—")}</td>
      <td>
        <span class="badge ${s.status === "PUBLISHED" ? "badge-LECTURE" : "badge-secondary"}" style="font-size:11px;">
          ${s.status}
        </span>
      </td>
    </tr>
  `).join("");

  renderDashboardGrid(filtered);
}

function renderDashboardGrid(filtered) {
  const gridContainer = document.getElementById("dash-grid-container");
  if (!gridContainer) return;

  const days = ["MON", "TUE", "WED", "THU", "FRI", "SAT"];
  const byDay = {};
  days.forEach(d => byDay[d] = []);
  filtered.forEach(s => {
    if (byDay[s.day_of_week]) byDay[s.day_of_week].push(s);
  });

  gridContainer.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
      <div>
        <h4 style="font-size: 15px; font-weight: 700; color: #1F2937; margin: 0;">Weekly Schedule Overview</h4>
        <span style="font-size: 12px; color: var(--text-muted);">${filtered.length} classes active</span>
      </div>
      <a href="/schedules" class="btn btn-primary btn-sm" style="display: inline-flex; align-items: center; gap: 4px;">
        Open Full Timetable Grid &rarr;
      </a>
    </div>
    <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; text-align: left;">
      ${days.map(d => `
        <div style="background: rgba(255,255,255,0.7); border: 1px solid var(--border-light); border-radius: 8px; padding: 10px;">
          <div style="font-weight: 800; font-size: 12px; color: #6E1717; margin-bottom: 8px; border-bottom: 1.5px solid rgba(110,23,23,0.15); padding-bottom: 4px;">
            ${d} (${byDay[d].length})
          </div>
          <div style="display: flex; flex-direction: column; gap: 6px; max-height: 400px; overflow-y: auto;">
            ${byDay[d].length === 0 ? '<span style="font-size: 11px; color: #9CA3AF;">No classes</span>' : byDay[d].map(s => `
              <div style="background: #FFFFFF; border-radius: 6px; padding: 6px 8px; font-size: 11px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); border-left: 3px solid ${s.status === 'PUBLISHED' ? '#22C55E' : '#F59E0B'};">
                <div style="font-weight: 700; color: #111827;">${escapeHtml(s.subject_code || '')}</div>
                <div style="color: #4B5563; font-size: 10px;">${formatTimeTo12(s.start_time)} - ${formatTimeTo12(s.end_time)}</div>
                <div style="color: #6B7280; font-size: 10px;">${escapeHtml(s.section_name || '')} • ${escapeHtml(s.room_code || '')}</div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
                  <span style="font-size: 9px; font-weight: 700; text-transform: uppercase; color: ${s.status === 'PUBLISHED' ? '#166534' : '#92400E'};">
                    ${s.status === 'PUBLISHED' ? '✓ Published' : 'Draft'}
                  </span>
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

function bindDashboardEvents() {
  // Cascading filters
  document.getElementById("dash-filter-prog")?.addEventListener("change", () => {
    cascadeDashboardSections();
    renderDashboardTable();
  });
  document.getElementById("dash-filter-year")?.addEventListener("change", () => {
    cascadeDashboardSections();
    renderDashboardTable();
  });
  document.getElementById("dash-filter-sec")?.addEventListener("change", renderDashboardTable);
  document.getElementById("dash-filter-room")?.addEventListener("change", renderDashboardTable);
  document.getElementById("dash-filter-status")?.addEventListener("change", renderDashboardTable);

  // View toggles
  const btnTable = document.getElementById("btn-view-table");
  const btnGrid = document.getElementById("btn-view-grid");
  const tableContainer = document.getElementById("dash-table-container");
  const gridContainer = document.getElementById("dash-grid-container");

  btnTable?.addEventListener("click", () => {
    btnTable.classList.add("active");
    btnGrid?.classList.remove("active");
    tableContainer.style.display = "block";
    gridContainer.style.display = "none";
  });

  btnGrid?.addEventListener("click", () => {
    btnGrid.classList.add("active");
    btnTable?.classList.remove("active");
    tableContainer.style.display = "none";
    gridContainer.style.display = "block";
  });

  // Print button
  document.getElementById("btn-dash-print")?.addEventListener("click", () => {
    window.print();
  });

  // Export CSV
  document.getElementById("btn-dash-export")?.addEventListener("click", exportSchedulesToCSV);

  // Generate Draft Schedules (Admin/Chair only)
  document.getElementById("btn-dash-gen")?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-dash-gen");
    if (!confirm("Run heuristic solver to auto-assign conflict-free draft slots for unplaced offerings?")) return;

    btn.disabled = true;
    btn.textContent = "Solving…";
    try {
      const res = await API.generateDraftSchedules();
      showToast(res.message || "Draft generation complete!");
      await loadDashboardMetrics();
      await loadDashboardData();
    } catch (err) {
      showToast(err.message || "Failed to generate drafts", true);
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg> Generate Drafts`;
    }
  });

  // Publish All (Admin/Chair only)
  document.getElementById("btn-dash-pub")?.addEventListener("click", async () => {
    if (!confirm("Lock all conflict-free draft schedules and change status to PUBLISHED?")) return;
    const btn = document.getElementById("btn-dash-pub");
    btn.disabled = true;
    btn.textContent = "Publishing…";
    try {
      const res = await API.publishAllSchedules();
      showToast(res.message || "Timetable locked & published!");
      await loadDashboardMetrics();
      await loadDashboardData();
    } catch (err) {
      showToast(err.message || "Cannot publish: Clashes exist.", true);
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg> Publish All`;
    }
  });
}

function exportSchedulesToCSV() {
  if (_dashSchedules.length === 0) {
    showToast("No schedules available to export.", true);
    return;
  }

  const headers = ["ID", "Day", "Start Time", "End Time", "Course Code", "Course Title", "Section", "Faculty", "Room", "Status"];
  const rows = _dashSchedules.map(s => [
    s.id,
    s.day_of_week,
    s.start_time,
    s.end_time,
    `"${(s.subject_code || "").replace(/"/g, '""')}"`,
    `"${(s.subject_name || "").replace(/"/g, '""')}"`,
    `"${(s.section_name || "").replace(/"/g, '""')}"`,
    `"${(s.faculty_name || "").replace(/"/g, '""')}"`,
    `"${(s.room_code || "").replace(/"/g, '""')}"`,
    s.status,
  ]);

  const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map(r => r.join(","))].join("\n");
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", `COE_SYNC_Schedules_${new Date().toISOString().slice(0,10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  showToast("CSV export generated successfully.");
}

function detectConflictsSimple(schedules) {
  const list = [];
  const n = schedules.length;

  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const a = schedules[i], b = schedules[j];
      if (a.day_of_week !== b.day_of_week) continue;

      const aStart = timeToMin(a.start_time), aEnd = timeToMin(a.end_time);
      const bStart = timeToMin(b.start_time), bEnd = timeToMin(b.end_time);
      if (aStart >= bEnd || bStart >= aEnd) continue;

      if (a.room_id === b.room_id) {
        list.push({
          title: `Room double-booked · ${a.room_code}`,
          meta: `${a.day_of_week} ${formatTimeTo12(a.start_time)}`,
        });
      } else if (a.faculty_id === b.faculty_id) {
        list.push({
          title: `Faculty overlap · ${a.faculty_name}`,
          meta: `${a.day_of_week} ${formatTimeTo12(a.start_time)}`,
        });
      } else if (a.section_id === b.section_id) {
        list.push({
          title: `Section overlap · ${a.section_name}`,
          meta: `${a.day_of_week} ${formatTimeTo12(a.start_time)}`,
        });
      }
    }
  }
  return list;
}

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
  return `${hh}:${String(m).padStart(2, "0")} ${period}`;
}

