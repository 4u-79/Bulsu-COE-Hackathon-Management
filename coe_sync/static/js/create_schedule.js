/**
 * COE SYNC 2026 - Create Schedule Module (static/js/create_schedule.js)
 *
 * Implements dual-mode scheduling for Program Chairs & Administrators:
 * 1. Smart Generate: Intelligent AI multi-criteria timetable synthesis with dynamic heuristics
 * 2. Manual Scheduling: Fine-grained single-slot placement with dynamic cascading filters and pre-flight checks
 */

document.addEventListener("DOMContentLoaded", () => {
  // Central Master Data Cache
  const masterState = {
    programs: ["CE", "ECE", "MEE", "MFE"],
    allSections: [], // { id, name, program, year_level, student_count }
    allSubjects: [], // { id, code, title, program, units, subject_type, year_level, semester }
    allFaculty: [],  // { id, name, email, program, max_units, current_units }
    allRooms: [],    // { id, room_code, room_type, capacity, is_available }
    activeTab: "smart",
    activeRoomFilter: "ALL", // "ALL" | "LECTURE" | "LAB"
    isGenerating: false,
    checkDebounceTimer: null,
  };

  // DOM Elements - Navigation & Modes
  const tabBtnManual = document.getElementById("tab-btn-manual");
  const tabBtnSmart = document.getElementById("tab-btn-smart");
  const panelManual = document.getElementById("panel-manual-scheduling");
  const panelSmart = document.getElementById("panel-smart-generate");

  // DOM Elements - Smart Generate
  const sgProgramSelect = document.getElementById("sg-program");
  const sgYearSelect = document.getElementById("sg-year-level");
  const sgSectionsContainer = document.getElementById("sg-sections-container");
  const sgRoomsContainer = document.getElementById("sg-rooms-container");
  const sgFacultySelect = document.getElementById("sg-faculty");
  const btnSecSelectAll = document.getElementById("btn-sec-select-all");
  const btnSecClearAll = document.getElementById("btn-sec-clear-all");
  const btnRoomSelectAll = document.getElementById("btn-room-select-all");
  const formSmartGenerate = document.getElementById("form-smart-generate");
  const btnSmartGenerate = document.getElementById("btn-smart-generate");

  // Summary Metrics DOM
  const summarySectionCount = document.getElementById("summary-section-count");
  const summarySubjectCount = document.getElementById("summary-subject-count");
  const summaryRoomCount = document.getElementById("summary-room-count");

  // Visualizer DOM
  const visIdleState = document.getElementById("vis-idle-state");
  const visRunningState = document.getElementById("vis-running-state");
  const visCompletedState = document.getElementById("vis-completed-state");
  const visProgressFill = document.getElementById("vis-progress-fill");
  const visProgressPercent = document.getElementById("vis-progress-percent");
  const visProgressStatus = document.getElementById("vis-progress-status");
  const resClassesScheduled = document.getElementById("res-classes-scheduled");
  const resQualityScore = document.getElementById("res-quality-score");
  const resUnplacedContainer = document.getElementById("res-unplaced-container");
  const resUnplacedList = document.getElementById("res-unplaced-list");
  const btnGenerateAgain = document.getElementById("btn-generate-again");

  // DOM Elements - Manual Scheduling
  const formManual = document.getElementById("form-manual-schedule");
  const manualProgram = document.getElementById("manual-program");
  const manualYearLevel = document.getElementById("manual-year-level");
  const manualSubject = document.getElementById("manual-subject");
  const manualSubjectMeta = document.getElementById("manual-subject-meta");
  const manualSection = document.getElementById("manual-section");
  const manualSectionMeta = document.getElementById("manual-section-meta");
  const manualFaculty = document.getElementById("manual-faculty");
  const manualRoom = document.getElementById("manual-room");
  const manualDay = document.getElementById("manual-day");
  const manualStartTime = document.getElementById("manual-start-time");
  const manualEndTime = document.getElementById("manual-end-time");
  const manualConflictBanner = document.getElementById("manual-conflict-banner");
  const btnSaveManualSlot = document.getElementById("btn-save-manual-slot");

  /* =========================================================================
     1. PROGRAM NORMALIZATION HELPER
     ========================================================================= */
  function normalizeProgram(prog) {
    if (!prog) return "";
    const p = String(prog).toUpperCase().trim();
    if (p === "BSCE" || p === "CIVIL" || p === "CE") return "CE";
    if (p === "BSEE" || p === "BSECE" || p === "ECE" || p === "ELECTRONICS") return "ECE";
    if (p === "BSME" || p === "BSMEE" || p === "MEE" || p === "MECHANICAL") return "MEE";
    if (p === "BSMFE" || p === "BSIE" || p === "MFE" || p === "MANUFACTURING") return "MFE";
    if (p === "BSCPE" || p === "CPE") return "ECE";
    return p;
  }

  /* =========================================================================
     2. TAB SWITCHING LOGIC
     ========================================================================= */
  function switchTab(mode) {
    masterState.activeTab = mode;
    if (mode === "smart") {
      tabBtnSmart.classList.add("active");
      tabBtnSmart.setAttribute("aria-selected", "true");
      tabBtnManual.classList.remove("active");
      tabBtnManual.setAttribute("aria-selected", "false");

      panelSmart.classList.add("active");
      panelSmart.style.display = "block";
      panelManual.classList.remove("active");
      panelManual.style.display = "none";
      updateLiveSummaryMetrics();
    } else {
      tabBtnManual.classList.add("active");
      tabBtnManual.setAttribute("aria-selected", "true");
      tabBtnSmart.classList.remove("active");
      tabBtnSmart.setAttribute("aria-selected", "false");

      panelManual.classList.add("active");
      panelManual.style.display = "block";
      panelSmart.classList.remove("active");
      panelSmart.style.display = "none";

      if (manualSubject?.value && manualSection?.value && manualFaculty?.value && manualRoom?.value) {
        triggerManualPreflight();
      }
    }
  }

  tabBtnManual?.addEventListener("click", () => switchTab("manual"));
  tabBtnSmart?.addEventListener("click", () => switchTab("smart"));

  /* =========================================================================
     3. MASTER DATA INITIALIZATION
     ========================================================================= */
  async function loadMasterData() {
    try {
      const [secRes, roomRes, facRes, subRes] = await Promise.all([
        fetch("/api/sections").then((r) => r.json()),
        fetch("/api/rooms").then((r) => r.json()),
        fetch("/api/faculty").then((r) => r.json()),
        fetch("/api/subjects").then((r) => r.json()),
      ]);

      masterState.allSections = secRes.data || secRes || [];
      masterState.allRooms = roomRes.data || roomRes || [];
      masterState.allFaculty = facRes.data || facRes || [];
      masterState.allSubjects = subRes.data || subRes || [];

      // Initialize Smart Generate Controls
      initSmartGenerateControls();

      // Initialize Manual Scheduling Controls
      initManualSchedulingControls();

      // Update initial summary numbers
      updateLiveSummaryMetrics();
    } catch (err) {
      console.error("Failed to load master data:", err);
      showToast("Error loading master scheduling data. Please refresh.", "error");
    }
  }

  /* =========================================================================
     4. SMART GENERATE CONTROLS & DYNAMIC CASCADING
     ========================================================================= */
  function initSmartGenerateControls() {
    // Populate Program Dropdown
    if (sgProgramSelect) {
      sgProgramSelect.innerHTML = `
        <option value="ALL">All Degree Programs</option>
        <option value="CE">Civil Engineering (CE)</option>
        <option value="ECE">Electronics Engineering (ECE)</option>
        <option value="MEE">Mechanical Engineering (MEE)</option>
        <option value="MFE">Manufacturing Engineering (MFE)</option>
      `;
    }

    renderSmartSectionPills();
    renderSmartRoomCheckboxes();
    populateSmartFacultyDropdown();

    sgProgramSelect?.addEventListener("change", () => {
      renderSmartSectionPills();
      populateSmartFacultyDropdown();
      updateLiveSummaryMetrics();
    });

    sgYearSelect?.addEventListener("change", () => {
      renderSmartSectionPills();
      updateLiveSummaryMetrics();
    });

    btnSecSelectAll?.addEventListener("click", () => {
      sgSectionsContainer?.querySelectorAll(".section-pill").forEach((pill) => {
        pill.classList.add("selected");
      });
      updateLiveSummaryMetrics();
    });

    btnSecClearAll?.addEventListener("click", () => {
      sgSectionsContainer?.querySelectorAll(".section-pill").forEach((pill) => {
        pill.classList.remove("selected");
      });
      updateLiveSummaryMetrics();
    });

    // Room Filter Pills
    document.querySelectorAll(".room-pill-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".room-pill-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        masterState.activeRoomFilter = btn.dataset.type || "ALL";
        renderSmartRoomCheckboxes();
        updateLiveSummaryMetrics();
      });
    });

    let allRoomsChecked = true;
    btnRoomSelectAll?.addEventListener("click", () => {
      allRoomsChecked = !allRoomsChecked;
      sgRoomsContainer?.querySelectorAll(".room-cb").forEach((cb) => {
        cb.checked = allRoomsChecked;
      });
      btnRoomSelectAll.textContent = allRoomsChecked ? "Deselect All Rooms" : "Select All Rooms";
      updateLiveSummaryMetrics();
    });
  }

  function renderSmartSectionPills() {
    if (!sgSectionsContainer) return;
    const selectedProgram = sgProgramSelect ? sgProgramSelect.value : "ALL";
    const selectedYear = sgYearSelect ? sgYearSelect.value : "ALL";

    const filtered = masterState.allSections.filter((sec) => {
      if (selectedProgram !== "ALL" && normalizeProgram(sec.program) !== normalizeProgram(selectedProgram)) {
        return false;
      }
      if (selectedYear !== "ALL" && String(sec.year_level) !== String(selectedYear)) {
        return false;
      }
      return true;
    });

    if (filtered.length === 0) {
      sgSectionsContainer.innerHTML = `<span class="empty-hint">No cohorts found matching ${selectedProgram !== 'ALL' ? selectedProgram : 'selected'} program and year.</span>`;
      return;
    }

    sgSectionsContainer.innerHTML = "";
    filtered.forEach((sec) => {
      const pill = document.createElement("div");
      pill.className = "section-pill selected";
      pill.dataset.id = sec.id;
      pill.dataset.program = sec.program || "";
      pill.dataset.year = sec.year_level || "";
      pill.innerHTML = `
        <span class="pill-name">${escapeHtml(sec.name)}</span>
        <span class="pill-prog">${escapeHtml(sec.program || "")}</span>
        <button type="button" class="pill-remove" title="Toggle selection">&times;</button>
      `;

      pill.addEventListener("click", () => {
        pill.classList.toggle("selected");
        updateLiveSummaryMetrics();
      });

      sgSectionsContainer.appendChild(pill);
    });
  }

  function renderSmartRoomCheckboxes() {
    if (!sgRoomsContainer) return;
    if (masterState.allRooms.length === 0) {
      sgRoomsContainer.innerHTML = `<span class="empty-hint">No physical rooms registered.</span>`;
      return;
    }

    const filterType = masterState.activeRoomFilter;
    const filteredRooms = masterState.allRooms.filter((r) => {
      const rType = String(r.room_type || r.type || "LECTURE").toUpperCase();
      if (filterType === "LECTURE") return rType === "LECTURE";
      if (filterType === "LAB") return rType.includes("LAB");
      return true;
    });

    sgRoomsContainer.innerHTML = "";
    filteredRooms.forEach((r) => {
      const roomName = r.room_code || r.name;
      const roomType = String(r.room_type || r.type || "LECTURE").toUpperCase();
      const isLab = roomType.includes("LAB");
      const card = document.createElement("label");
      card.className = "room-checkbox-card";
      card.innerHTML = `
        <input type="checkbox" class="room-cb" value="${r.id}" checked>
        <div class="room-info">
          <span class="room-name">${escapeHtml(roomName)}</span>
          <span class="room-meta">
            <span class="room-type-tag ${isLab ? 'laboratory' : 'lecture'}">${isLab ? 'LAB' : 'LECTURE'}</span>
            <span>Cap: ${r.capacity}</span>
          </span>
        </div>
      `;

      card.querySelector(".room-cb")?.addEventListener("change", updateLiveSummaryMetrics);
      sgRoomsContainer.appendChild(card);
    });
  }

  function populateSmartFacultyDropdown() {
    if (!sgFacultySelect) return;
    const selectedProgram = sgProgramSelect ? sgProgramSelect.value : "ALL";

    sgFacultySelect.innerHTML = `<option value="all" selected>All Department Faculty (Recommended for Global Load Balancing)</option>`;

    let facList = masterState.allFaculty;
    if (selectedProgram !== "ALL") {
      facList = facList.filter((f) => normalizeProgram(f.program) === normalizeProgram(selectedProgram));
    }

    facList.forEach((fac) => {
      const opt = document.createElement("option");
      opt.value = fac.id;
      opt.textContent = `${fac.name} (${fac.program || "COE"})`;
      sgFacultySelect.appendChild(opt);
    });
  }

  function updateLiveSummaryMetrics() {
    // 1. Target sections count
    const activePills = sgSectionsContainer?.querySelectorAll(".section-pill.selected") || [];
    const secCount = activePills.length;
    if (summarySectionCount) summarySectionCount.textContent = secCount;

    // 2. Total subjects to schedule
    const selectedSecIds = Array.from(activePills).map((p) => parseInt(p.dataset.id, 10));
    const selectedSecObjs = masterState.allSections.filter((s) => selectedSecIds.includes(s.id));

    // Calculate unique curriculum subjects corresponding to the selected sections
    let totalSubjects = 0;
    const countedKeys = new Set();
    selectedSecObjs.forEach((sec) => {
      const normProg = normalizeProgram(sec.program);
      const matchingSubs = masterState.allSubjects.filter((sub) => {
        const subProg = normalizeProgram(sub.program);
        const matchProg = !subProg || subProg === normProg;
        const matchYr = !sub.year_level || String(sub.year_level) === String(sec.year_level);
        return matchProg && matchYr;
      });

      matchingSubs.forEach((sub) => {
        const key = `${sec.id}-${sub.id}`;
        if (!countedKeys.has(key)) {
          countedKeys.add(key);
          totalSubjects++;
        }
      });
    });

    // Fallback if curriculum mapping is sparse: estimate 6 subjects per cohort
    if (totalSubjects === 0 && secCount > 0) {
      totalSubjects = secCount * 6;
    }
    if (summarySubjectCount) summarySubjectCount.textContent = totalSubjects;

    // 3. Eligible rooms count
    const checkedRooms = sgRoomsContainer?.querySelectorAll(".room-cb:checked") || [];
    if (summaryRoomCount) summaryRoomCount.textContent = checkedRooms.length;
  }

  /* =========================================================================
     5. MANUAL SCHEDULING MODE & DYNAMIC CASCADING FILTERS
     ========================================================================= */
  function initManualSchedulingControls() {
    // Populate Program Dropdown
    if (manualProgram) {
      manualProgram.innerHTML = `
        <option value="">-- All Programs --</option>
        <option value="CE">Civil Engineering (CE)</option>
        <option value="ECE">Electronics Engineering (ECE)</option>
        <option value="MEE">Mechanical Engineering (MEE)</option>
        <option value="MFE">Manufacturing Engineering (MFE)</option>
      `;
    }

    // Populate Year Level Dropdown
    if (manualYearLevel) {
      manualYearLevel.innerHTML = `
        <option value="">-- All Years --</option>
        <option value="1">1st Year</option>
        <option value="2">2nd Year</option>
        <option value="3">3rd Year</option>
        <option value="4">4th Year</option>
      `;
    }

    // Cascade on Program change
    manualProgram?.addEventListener("change", () => {
      cascadeManualFilters();
      triggerManualPreflight();
    });

    // Cascade on Year Level change
    manualYearLevel?.addEventListener("change", () => {
      cascadeManualFilters();
      triggerManualPreflight();
    });

    // Subject selection change -> Auto-detect LAB vs LECTURE & prioritize room types
    manualSubject?.addEventListener("change", () => {
      handleManualSubjectChange();
      triggerManualPreflight();
    });

    // Section selection change
    manualSection?.addEventListener("change", () => {
      handleManualSectionChange();
      triggerManualPreflight();
    });

    // Real-time conflict checks on parameters change
    [manualFaculty, manualRoom, manualDay, manualStartTime, manualEndTime].forEach((el) => {
      el?.addEventListener("change", triggerManualPreflight);
      el?.addEventListener("input", triggerManualPreflight);
    });

    // Initial cascade
    cascadeManualFilters();
    populateManualRooms(null);
  }

  function cascadeManualFilters() {
    const selectedProgram = manualProgram ? manualProgram.value : "";
    const selectedYear = manualYearLevel ? manualYearLevel.value : "";

    // 1. Filter Subjects
    if (manualSubject) {
      const prevSubVal = manualSubject.value;
      const filteredSubjects = masterState.allSubjects.filter((sub) => {
        if (selectedProgram && normalizeProgram(sub.program) !== normalizeProgram(selectedProgram)) {
          return false;
        }
        if (selectedYear && String(sub.year_level) !== String(selectedYear)) {
          return false;
        }
        return true;
      });

      manualSubject.innerHTML = `<option value="">-- Choose Subject (${filteredSubjects.length} Available) --</option>`;
      filteredSubjects.forEach((sub) => {
        const opt = document.createElement("option");
        opt.value = sub.id;
        const progTag = sub.program ? `[${sub.program}] ` : "";
        opt.textContent = `${progTag}${sub.code} — ${sub.title} (${sub.units}u)`;
        manualSubject.appendChild(opt);
      });

      if (filteredSubjects.some((s) => String(s.id) === String(prevSubVal))) {
        manualSubject.value = prevSubVal;
      } else {
        manualSubject.value = "";
        if (manualSubjectMeta) manualSubjectMeta.style.display = "none";
      }
    }

    // 2. Filter Sections
    if (manualSection) {
      const prevSecVal = manualSection.value;
      const filteredSections = masterState.allSections.filter((sec) => {
        if (selectedProgram && normalizeProgram(sec.program) !== normalizeProgram(selectedProgram)) {
          return false;
        }
        if (selectedYear && String(sec.year_level) !== String(selectedYear)) {
          return false;
        }
        return true;
      });

      manualSection.innerHTML = `<option value="">-- Choose Section (${filteredSections.length} Available) --</option>`;
      filteredSections.forEach((sec) => {
        const opt = document.createElement("option");
        opt.value = sec.id;
        opt.textContent = `${sec.name} (${sec.program} · Yr ${sec.year_level} · ${sec.student_count || 40} studs)`;
        manualSection.appendChild(opt);
      });

      if (filteredSections.some((s) => String(s.id) === String(prevSecVal))) {
        manualSection.value = prevSecVal;
      } else {
        manualSection.value = "";
        if (manualSectionMeta) manualSectionMeta.style.display = "none";
      }
    }

    // 3. Filter Faculty
    if (manualFaculty) {
      const prevFacVal = manualFaculty.value;
      let filteredFaculty = masterState.allFaculty;
      if (selectedProgram) {
        filteredFaculty = filteredFaculty.filter((f) => normalizeProgram(f.program) === normalizeProgram(selectedProgram));
      }

      manualFaculty.innerHTML = `<option value="">-- Choose Faculty Member (${filteredFaculty.length} Available) --</option>`;
      filteredFaculty.forEach((fac) => {
        const opt = document.createElement("option");
        opt.value = fac.id;
        opt.textContent = `${fac.name} (${fac.program || "Faculty"} · ${fac.current_units || 0}/${fac.max_units || 21}u)`;
        manualFaculty.appendChild(opt);
      });

      if (filteredFaculty.some((f) => String(f.id) === String(prevFacVal))) {
        manualFaculty.value = prevFacVal;
      } else {
        manualFaculty.value = "";
      }
    }
  }

  function handleManualSubjectChange() {
    const subId = parseInt(manualSubject.value, 10);
    const sub = masterState.allSubjects.find((s) => s.id === subId);

    if (sub) {
      const subType = String(sub.subject_type || sub.type || "LECTURE").toUpperCase();
      const code = String(sub.code || "").toUpperCase();
      const isLab = subType.includes("LAB") || code.endsWith("L") || code.endsWith("D") || code.endsWith("F");

      // Auto-update meta box
      if (manualSubjectMeta) {
        manualSubjectMeta.style.display = "block";
        manualSubjectMeta.innerHTML = `
          <span><strong>Course:</strong> ${escapeHtml(sub.code)} — ${escapeHtml(sub.title)}</span> •
          <span><strong>Type:</strong> <span class="badge-role" style="${isLab ? 'background:#0F766E; color:#FFF;' : ''}">${isLab ? 'LABORATORY' : 'LECTURE'}</span></span> •
          <span><strong>Units:</strong> ${sub.units}u</span> •
          <span><strong>Duration:</strong> ${isLab ? "3.0 hrs" : "1.5 hrs"}</span>
        `;
      }

      // Prioritize and recommend matching room types in classroom dropdown
      populateManualRooms(isLab ? "LAB" : "LECTURE");

      // Auto-set duration based on standard course type
      if (manualStartTime?.value) {
        const [h, m] = manualStartTime.value.split(":").map(Number);
        const addMinutes = isLab ? 180 : 90;
        const totalMin = h * 60 + m + addMinutes;
        const endH = String(Math.floor(totalMin / 60)).padStart(2, "0");
        const endM = String(totalMin % 60).padStart(2, "0");
        if (manualEndTime) manualEndTime.value = `${endH}:${endM}`;
      }
    } else {
      if (manualSubjectMeta) {
        manualSubjectMeta.style.display = "none";
        manualSubjectMeta.innerHTML = "";
      }
      populateManualRooms(null);
    }
  }

  function populateManualRooms(recommendedType = null) {
    if (!manualRoom) return;
    const prevVal = manualRoom.value;
    manualRoom.innerHTML = `<option value="">-- Choose Physical Room --</option>`;

    let rooms = [...masterState.allRooms];
    if (recommendedType) {
      // Sort matching room types to the top
      rooms.sort((a, b) => {
        const aType = String(a.room_type || a.type || "").toUpperCase();
        const bType = String(b.room_type || b.type || "").toUpperCase();
        const aMatch = recommendedType === "LAB" ? aType.includes("LAB") : !aType.includes("LAB");
        const bMatch = recommendedType === "LAB" ? bType.includes("LAB") : !bType.includes("LAB");
        if (aMatch && !bMatch) return -1;
        if (!aMatch && bMatch) return 1;
        return a.room_code.localeCompare(b.room_code);
      });
    }

    rooms.forEach((r) => {
      const roomType = String(r.room_type || r.type || "LECTURE").toUpperCase();
      const isLab = roomType.includes("LAB");
      const isMatch = recommendedType ? (recommendedType === "LAB" ? isLab : !isLab) : false;
      const opt = document.createElement("option");
      opt.value = r.id;
      const tag = isMatch ? " ★ Recommended" : "";
      opt.textContent = `${r.room_code} (${isLab ? 'Lab' : 'Lecture'} - Cap: ${r.capacity})${tag}`;
      manualRoom.appendChild(opt);
    });

    if (rooms.some((r) => String(r.id) === String(prevVal))) {
      manualRoom.value = prevVal;
    }
  }

  function handleManualSectionChange() {
    const secId = parseInt(manualSection?.value, 10);
    const sec = masterState.allSections.find((s) => s.id === secId);

    if (sec && manualSectionMeta) {
      manualSectionMeta.style.display = "block";
      manualSectionMeta.innerHTML = `
        <span><strong>Cohort:</strong> ${escapeHtml(sec.program)} Year ${sec.year_level} (${escapeHtml(sec.name)})</span> •
        <span><strong>Class Size:</strong> ${sec.student_count || 40} Students</span>
      `;
    } else if (manualSectionMeta) {
      manualSectionMeta.style.display = "none";
      manualSectionMeta.innerHTML = "";
    }
  }

  function triggerManualPreflight() {
    clearTimeout(masterState.checkDebounceTimer);
    masterState.checkDebounceTimer = setTimeout(runPreFlightConflictCheck, 250);
  }

  async function runPreFlightConflictCheck() {
    const subjectId = manualSubject?.value;
    const sectionId = manualSection?.value;
    const facultyId = manualFaculty?.value;
    const roomId = manualRoom?.value;
    const day = manualDay?.value;
    const startTime = manualStartTime?.value;
    const endTime = manualEndTime?.value;

    if (!subjectId || !sectionId || !facultyId || !roomId || !day || !startTime || !endTime) {
      if (manualConflictBanner) {
        manualConflictBanner.style.display = "none";
        manualConflictBanner.innerHTML = "";
      }
      return;
    }

    // Time Inversion check
    if (startTime >= endTime) {
      if (manualConflictBanner) {
        manualConflictBanner.style.display = "block";
        manualConflictBanner.className = "validation-banner banner-danger";
        manualConflictBanner.innerHTML = `
          <div class="banner-content">
            <span class="banner-icon">⚠</span>
            <div>
              <strong>Invalid Time Window</strong>
              <p>Start time must be strictly earlier than end time.</p>
            </div>
          </div>
        `;
      }
      if (btnSaveManualSlot) btnSaveManualSlot.disabled = true;
      return;
    }

    try {
      const payload = {
        subject_id: parseInt(subjectId, 10),
        section_id: parseInt(sectionId, 10),
        faculty_id: parseInt(facultyId, 10),
        room_id: parseInt(roomId, 10),
        day_of_week: day,
        start_time: startTime,
        end_time: endTime,
      };

      const res = await fetch("/api/conflicts/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!manualConflictBanner) return;

      manualConflictBanner.style.display = "block";

      if (data.valid) {
        manualConflictBanner.className = "validation-banner banner-success";
        manualConflictBanner.innerHTML = `
          <div class="banner-content">
            <span class="banner-icon">✔</span>
            <div>
              <strong>No Collisions Detected (Safe to Place)</strong>
              <p>Physical facility, instructor blackout windows, cohort availability, and seating capacity are all clear.</p>
            </div>
          </div>
        `;
        if (btnSaveManualSlot) btnSaveManualSlot.disabled = false;
      } else {
        manualConflictBanner.className = "validation-banner banner-danger";
        const conflictList = (data.conflicts || [])
          .map((c) => `<li>${escapeHtml(c)}</li>`)
          .join("");

        let suggestionsHtml = "";
        if (data.suggestions && data.suggestions.length > 0) {
          suggestionsHtml = `
            <div class="banner-suggestions">
              <strong>Recommended Alternative Slots:</strong>
              <ul>
                ${data.suggestions
                  .map(
                    (s) =>
                      `<li>${escapeHtml(s.day_of_week)} ${escapeHtml(s.start_time)}–${escapeHtml(
                        s.end_time
                      )} in <strong>${escapeHtml(s.room_name || `Room #${s.room_id}`)}</strong></li>`
                  )
                  .join("")}
              </ul>
            </div>
          `;
        }

        manualConflictBanner.innerHTML = `
          <div class="banner-content">
            <span class="banner-icon">⚠</span>
            <div>
              <strong>Schedule Collision Detected:</strong>
              <ul class="conflict-bullet-list">${conflictList}</ul>
              ${suggestionsHtml}
            </div>
          </div>
        `;
        if (btnSaveManualSlot) btnSaveManualSlot.disabled = false;
      }
    } catch (err) {
      console.warn("Pre-flight conflict check error:", err);
    }
  }

  // Manual Form Submission
  formManual?.addEventListener("submit", async (e) => {
    e.preventDefault();

    const payload = {
      subject_id: parseInt(manualSubject.value, 10),
      section_id: parseInt(manualSection.value, 10),
      faculty_id: parseInt(manualFaculty.value, 10),
      room_id: parseInt(manualRoom.value, 10),
      day_of_week: manualDay.value,
      start_time: manualStartTime.value,
      end_time: manualEndTime.value,
    };

    if (btnSaveManualSlot) {
      btnSaveManualSlot.disabled = true;
      btnSaveManualSlot.innerHTML = `<span class="btn-spinner"></span> Saving Slot...`;
    }

    try {
      const res = await fetch("/api/schedules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (btnSaveManualSlot) {
        btnSaveManualSlot.disabled = false;
        btnSaveManualSlot.innerHTML = `<span>Save Schedule Slot &rarr;</span>`;
      }

      if (res.ok) {
        showToast("Schedule slot successfully created!", "success");
        if (manualConflictBanner) manualConflictBanner.style.display = "none";
        setTimeout(() => {
          if (confirm("Slot created! Would you like to review the timetable grid now?")) {
            window.location.href = "/schedules";
          }
        }, 300);
      } else {
        const errorMsg = data.error || (data.conflicts ? data.conflicts.join("; ") : "Failed to create schedule slot.");
        showToast(`Conflict Error: ${errorMsg}`, "error");
        if (manualConflictBanner) {
          manualConflictBanner.style.display = "block";
          manualConflictBanner.className = "validation-banner banner-danger";
          manualConflictBanner.innerHTML = `
            <div class="banner-content">
              <span class="banner-icon">⚠</span>
              <div>
                <strong>Submission Blocked:</strong>
                <p>${escapeHtml(errorMsg)}</p>
              </div>
            </div>
          `;
        }
      }
    } catch (err) {
      if (btnSaveManualSlot) {
        btnSaveManualSlot.disabled = false;
        btnSaveManualSlot.innerHTML = `<span>Save Schedule Slot &rarr;</span>`;
      }
      showToast("Network error while creating schedule slot.", "error");
      console.error(err);
    }
  });

  /* =========================================================================
     6. SMART GENERATE SOLVER & VISUALIZER EXECUTION
     ========================================================================= */
  const steps = [
    { id: "step-analyze", label: "Analyzing classes & curricular requirements...", pct: 20 },
    { id: "step-rooms", label: "Checking room availability & capacity constraints...", pct: 40 },
    { id: "step-faculty", label: "Checking faculty availability & blackout windows...", pct: 60 },
    { id: "step-conflicts", label: "Resolving hard conflicts (HC1–HC6)...", pct: 80 },
    { id: "step-optimize", label: "Optimizing resources & workload balance...", pct: 100 },
  ];

  function setVisualizerState(stepIdx) {
    steps.forEach((step, idx) => {
      const el = document.getElementById(step.id);
      if (!el) return;
      if (idx < stepIdx) {
        el.className = "checklist-step completed";
        el.querySelector(".step-icon").innerHTML = "✔";
      } else if (idx === stepIdx) {
        el.className = "checklist-step active";
        el.querySelector(".step-icon").innerHTML = "●";
      } else {
        el.className = "checklist-step";
        el.querySelector(".step-icon").innerHTML = "○";
      }
    });

    const activeStep = steps[stepIdx] || steps[steps.length - 1];
    const pct = activeStep ? activeStep.pct : 100;
    if (visProgressFill) visProgressFill.style.width = `${pct}%`;
    if (visProgressPercent) visProgressPercent.textContent = `${pct}%`;
    if (visProgressStatus) visProgressStatus.textContent = activeStep ? activeStep.label : "Completing generation...";
  }

  formSmartGenerate?.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (masterState.isGenerating) return;

    // Collect Selected Sections
    const selectedSectionPills = sgSectionsContainer.querySelectorAll(".section-pill.selected");
    const sectionIds = Array.from(selectedSectionPills).map((p) => parseInt(p.dataset.id, 10));

    if (sectionIds.length === 0) {
      showToast("Please select at least one cohort section to generate schedules.", "warning");
      return;
    }

    // Collect Selected Rooms
    const selectedRoomCbs = sgRoomsContainer.querySelectorAll(".room-cb:checked");
    const roomIds = Array.from(selectedRoomCbs).map((cb) => parseInt(cb.value, 10));

    if (roomIds.length === 0) {
      showToast("Please select at least one physical room / laboratory.", "warning");
      return;
    }

    const payload = {
      program: sgProgramSelect.value,
      year_level: sgYearSelect.value === "ALL" ? "all" : parseInt(sgYearSelect.value, 10),
      section_ids: sectionIds,
      room_ids: roomIds,
      faculty_ids: sgFacultySelect.value === "all" ? "all" : [parseInt(sgFacultySelect.value, 10)],
      preferences: {
        minimize_gaps: document.getElementById("pref-minimize-gaps")?.checked ?? true,
        balance_workload: document.getElementById("pref-balance-workload")?.checked ?? true,
        optimize_utilization: document.getElementById("pref-optimize-utilization")?.checked ?? true,
      },
    };

    // Transition to Running Visualizer
    masterState.isGenerating = true;
    if (visIdleState) visIdleState.style.display = "none";
    if (visCompletedState) visCompletedState.style.display = "none";
    if (visRunningState) visRunningState.style.display = "block";
    if (btnSmartGenerate) {
      btnSmartGenerate.disabled = true;
      btnSmartGenerate.innerHTML = `<span class="btn-spinner"></span> Generating Schedule...`;
    }

    // Visualizer simulated sequence
    let currentStep = 0;
    setVisualizerState(0);

    const stepInterval = setInterval(() => {
      if (currentStep < steps.length - 1) {
        currentStep++;
        setVisualizerState(currentStep);
      }
    }, 450);

    try {
      const response = await fetch("/api/scheduler/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      clearInterval(stepInterval);
      setVisualizerState(steps.length - 1);

      setTimeout(() => {
        masterState.isGenerating = false;
        if (btnSmartGenerate) {
          btnSmartGenerate.disabled = false;
          btnSmartGenerate.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
            <span>⚡ Generate Smart Schedule</span>
          `;
        }

        if (!response.ok || data.status === "error") {
          showToast(data.message || "Failed to generate schedule.", "error");
          if (visRunningState) visRunningState.style.display = "none";
          if (visIdleState) visIdleState.style.display = "block";
          return;
        }

        // Show Completed State
        if (visRunningState) visRunningState.style.display = "none";
        if (visCompletedState) visCompletedState.style.display = "block";

        const placedCount = data.placed_count !== undefined ? data.placed_count : (data.classes_scheduled || (data.metrics ? data.metrics.classes_scheduled : 0));
        if (resClassesScheduled) resClassesScheduled.textContent = placedCount;

        const qScore = Math.round(data.quality_score || 95);
        if (resQualityScore) {
          resQualityScore.textContent = qScore;
          resQualityScore.style.color = qScore >= 90 ? "#059669" : qScore >= 75 ? "#D97706" : "#DC2626";
        }

        // Render Unplaced Offerings if any
        const unplacedList = data.unplaced_items || data.unplaced || [];
        if (unplacedList.length > 0 && resUnplacedContainer && resUnplacedList) {
          resUnplacedContainer.style.display = "block";
          resUnplacedList.innerHTML = unplacedList
            .map(
              (u) =>
                `<li><strong>${escapeHtml(u.subject || u.subject_code || "Subject")}</strong> (${escapeHtml(
                  u.section || u.section_name || ""
                )}): ${escapeHtml(u.reason || "No available collision-free slot")}</li>`
            )
            .join("");
        } else if (resUnplacedContainer) {
          resUnplacedContainer.style.display = "none";
        }

        showToast("Smart timetable generation finished successfully!", "success");
      }, 600);
    } catch (err) {
      clearInterval(stepInterval);
      masterState.isGenerating = false;
      if (btnSmartGenerate) {
        btnSmartGenerate.disabled = false;
        btnSmartGenerate.innerHTML = `
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
          <span>⚡ Generate Smart Schedule</span>
        `;
      }
      if (visRunningState) visRunningState.style.display = "none";
      if (visIdleState) visIdleState.style.display = "block";
      showToast("Network error during schedule generation.", "error");
      console.error(err);
    }
  });

  btnGenerateAgain?.addEventListener("click", () => {
    if (visCompletedState) visCompletedState.style.display = "none";
    if (visRunningState) visRunningState.style.display = "none";
    if (visIdleState) visIdleState.style.display = "block";
  });

  /* =========================================================================
     7. UTILITY HELPERS
     ========================================================================= */
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function showToast(message, type = "info") {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.style.cssText = `
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 99999;
        display: flex;
        flex-direction: column;
        gap: 8px;
        pointer-events: none;
      `;
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    const bgColor =
      type === "success" ? "#065F46" : type === "error" ? "#991B1B" : type === "warning" ? "#92400E" : "#1E293B";

    toast.style.cssText = `
      background: ${bgColor};
      color: #FFFFFF;
      padding: 12px 18px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 500;
      box-shadow: 0 4px 14px rgba(0,0,0,0.2);
      display: flex;
      align-items: center;
      gap: 10px;
      pointer-events: auto;
      transition: all 0.3s ease;
      animation: toastIn 0.25s ease-out;
    `;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(10px)";
      setTimeout(() => toast.remove(), 300);
    }, 3800);
  }

  // Initial Load
  loadMasterData();
});
