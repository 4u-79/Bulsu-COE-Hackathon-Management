/**
 * COE SYNC 2026 - Create Schedule Module (static/js/create_schedule.js)
 *
 * Implements dual-mode scheduling for Program Chairs & Administrators:
 * 1. Smart Generate: Intelligent AI multi-criteria timetable synthesis
 * 2. Manual Scheduling: Fine-grained single-slot placement with real-time pre-flight collision checks
 */

document.addEventListener("DOMContentLoaded", () => {
  // Global Data Cache
  const state = {
    sections: [],
    rooms: [],
    faculty: [],
    subjects: [],
    activeTab: "smart",
    isGenerating: false,
    checkDebounceTimer: null,
  };

  // DOM Elements
  const tabBtnManual = document.getElementById("tab-btn-manual");
  const tabBtnSmart = document.getElementById("tab-btn-smart");
  const panelManual = document.getElementById("panel-manual-scheduling");
  const panelSmart = document.getElementById("panel-smart-generate");

  // Smart Generate DOM
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

  // Manual Scheduling DOM
  const formManual = document.getElementById("form-manual-schedule");
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
     1. TAB SWITCHING LOGIC
     ========================================================================= */
  function switchTab(mode) {
    state.activeTab = mode;
    if (mode === "smart") {
      tabBtnSmart.classList.add("active");
      tabBtnSmart.setAttribute("aria-selected", "true");
      tabBtnManual.classList.remove("active");
      tabBtnManual.setAttribute("aria-selected", "false");

      panelSmart.classList.add("active");
      panelSmart.style.display = "block";
      panelManual.classList.remove("active");
      panelManual.style.display = "none";
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

  tabBtnManual.addEventListener("click", () => switchTab("manual"));
  tabBtnSmart.addEventListener("click", () => switchTab("smart"));

  /* =========================================================================
     2. MASTER DATA INITIALIZATION
     ========================================================================= */
  async function loadMasterData() {
    try {
      const [secRes, roomRes, facRes, subRes] = await Promise.all([
        fetch("/api/sections").then((r) => r.json()),
        fetch("/api/rooms").then((r) => r.json()),
        fetch("/api/faculty").then((r) => r.json()),
        fetch("/api/subjects").then((r) => r.json()),
      ]);

      state.sections = secRes.data || secRes || [];
      state.rooms = roomRes.data || roomRes || [];
      state.faculty = facRes.data || facRes || [];
      state.subjects = subRes.data || subRes || [];

      // Populate Smart Generate Options
      populateProgramDropdown();
      renderSectionPills();
      renderRoomCheckboxes();
      populateFacultyDropdown();

      // Populate Manual Form Options
      populateManualFormOptions();
    } catch (err) {
      console.error("Failed to load master data:", err);
      showToast("Error loading master scheduling data. Please refresh.", "error");
    }
  }

  /* =========================================================================
     3. SMART GENERATE CONFIGURATION CONTROLS
     ========================================================================= */
  function populateProgramDropdown() {
    const programs = new Set();
    state.sections.forEach((sec) => {
      if (sec.program) programs.add(sec.program);
    });

    sgProgramSelect.innerHTML = `<option value="ALL">All Degree Programs</option>`;
    Array.from(programs).sort().forEach((prog) => {
      const opt = document.createElement("option");
      opt.value = prog;
      opt.textContent = prog;
      sgProgramSelect.appendChild(opt);
    });
  }

  function renderSectionPills() {
    const selectedProgram = sgProgramSelect.value;
    const selectedYear = sgYearSelect.value;

    const filtered = state.sections.filter((sec) => {
      if (selectedProgram !== "ALL" && sec.program !== selectedProgram) return false;
      if (selectedYear !== "ALL" && String(sec.year_level) !== String(selectedYear)) return false;
      return true;
    });

    if (filtered.length === 0) {
      sgSectionsContainer.innerHTML = `<span class="empty-hint">No sections found matching current program/year filters.</span>`;
      return;
    }

    sgSectionsContainer.innerHTML = "";
    filtered.forEach((sec) => {
      const pill = document.createElement("div");
      pill.className = "section-pill selected";
      pill.dataset.id = sec.id;
      pill.innerHTML = `
        <span class="pill-name">${escapeHtml(sec.name)}</span>
        <span class="pill-prog">${escapeHtml(sec.program || "")}</span>
        <button type="button" class="pill-remove" title="Toggle section">&times;</button>
      `;

      pill.addEventListener("click", () => {
        pill.classList.toggle("selected");
      });

      sgSectionsContainer.appendChild(pill);
    });
  }

  sgProgramSelect.addEventListener("change", renderSectionPills);
  sgYearSelect.addEventListener("change", renderSectionPills);

  btnSecSelectAll.addEventListener("click", () => {
    sgSectionsContainer.querySelectorAll(".section-pill").forEach((pill) => {
      pill.classList.add("selected");
    });
  });

  btnSecClearAll.addEventListener("click", () => {
    sgSectionsContainer.querySelectorAll(".section-pill").forEach((pill) => {
      pill.classList.remove("selected");
    });
  });

  function renderRoomCheckboxes() {
    if (state.rooms.length === 0) {
      sgRoomsContainer.innerHTML = `<span class="empty-hint">No physical rooms registered.</span>`;
      return;
    }

    sgRoomsContainer.innerHTML = "";
    state.rooms.forEach((r) => {
      const roomName = r.room_code || r.name;
      const roomType = r.room_type || r.type || "LECTURE";
      const card = document.createElement("label");
      card.className = "room-checkbox-card";
      card.innerHTML = `
        <input type="checkbox" class="room-cb" value="${r.id}" checked>
        <div class="room-info">
          <span class="room-name">${escapeHtml(roomName)}</span>
          <span class="room-meta">
            <span class="room-type-tag ${roomType.toLowerCase()}">${escapeHtml(roomType)}</span>
            <span>Cap: ${r.capacity}</span>
          </span>
        </div>
      `;
      sgRoomsContainer.appendChild(card);
    });
  }

  let allRoomsChecked = true;
  btnRoomSelectAll.addEventListener("click", () => {
    allRoomsChecked = !allRoomsChecked;
    sgRoomsContainer.querySelectorAll(".room-cb").forEach((cb) => {
      cb.checked = allRoomsChecked;
    });
    btnRoomSelectAll.textContent = allRoomsChecked ? "Deselect All Rooms" : "Select All Rooms";
  });

  function populateFacultyDropdown() {
    sgFacultySelect.innerHTML = `<option value="all" selected>All Department Faculty (Recommended for Global Load Balancing)</option>`;
    state.faculty.forEach((fac) => {
      const opt = document.createElement("option");
      opt.value = fac.id;
      opt.textContent = `${fac.name} (${fac.department || "COE"})`;
      sgFacultySelect.appendChild(opt);
    });
  }

  /* =========================================================================
     4. SMART GENERATE SOLVER & LIVE VISUALIZER
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
    visProgressFill.style.width = `${pct}%`;
    visProgressPercent.textContent = `${pct}%`;
    visProgressStatus.textContent = activeStep ? activeStep.label : "Completing generation...";
  }

  formSmartGenerate.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (state.isGenerating) return;

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
        minimize_gaps: document.getElementById("pref-minimize-gaps").checked,
        balance_workload: document.getElementById("pref-balance-workload").checked,
        optimize_utilization: document.getElementById("pref-optimize-utilization").checked,
      },
    };

    // Transition to Running Visualizer
    state.isGenerating = true;
    visIdleState.style.display = "none";
    visCompletedState.style.display = "none";
    visRunningState.style.display = "block";
    btnSmartGenerate.disabled = true;
    btnSmartGenerate.innerHTML = `<span class="btn-spinner"></span> Generating Schedule...`;

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

      // Brief delay to give user satisfying completion animation
      setTimeout(() => {
        state.isGenerating = false;
        btnSmartGenerate.disabled = false;
        btnSmartGenerate.innerHTML = `
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
          <span>⚡ Generate Smart Schedule</span>
        `;

        if (!response.ok || data.status === "error") {
          showToast(data.message || "Failed to generate schedule.", "error");
          visRunningState.style.display = "none";
          visIdleState.style.display = "block";
          return;
        }

        // Show Completed State
        visRunningState.style.display = "none";
        visCompletedState.style.display = "block";

        const placedCount = data.placed_count !== undefined ? data.placed_count : (data.classes_scheduled || (data.metrics ? data.metrics.classes_scheduled : 0));
        resClassesScheduled.textContent = placedCount;
        const qScore = Math.round(data.quality_score || 95);
        resQualityScore.textContent = qScore;
        if (qScore >= 90) {
          resQualityScore.style.color = "#059669";
        } else if (qScore >= 75) {
          resQualityScore.style.color = "#D97706";
        } else {
          resQualityScore.style.color = "#DC2626";
        }

        // Render Unplaced Offerings if any
        const unplacedList = data.unplaced_items || data.unplaced || [];
        if (unplacedList.length > 0) {
          resUnplacedContainer.style.display = "block";
          resUnplacedList.innerHTML = unplacedList
            .map(
              (u) =>
                `<li><strong>${escapeHtml(u.subject || u.subject_code || "Subject")}</strong> (${escapeHtml(
                  u.section || u.section_name || ""
                )}): ${escapeHtml(u.reason || "No available collision-free slot")}</li>`
            )
            .join("");
        } else {
          resUnplacedContainer.style.display = "none";
          resUnplacedList.innerHTML = "";
        }

        showToast("Smart timetable generation finished successfully!", "success");
      }, 600);
    } catch (err) {
      clearInterval(stepInterval);
      state.isGenerating = false;
      btnSmartGenerate.disabled = false;
      btnSmartGenerate.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
        <span>⚡ Generate Smart Schedule</span>
      `;
      visRunningState.style.display = "none";
      visIdleState.style.display = "block";
      showToast("Network error during schedule generation.", "error");
      console.error(err);
    }
  });

  btnGenerateAgain.addEventListener("click", () => {
    visCompletedState.style.display = "none";
    visRunningState.style.display = "none";
    visIdleState.style.display = "block";
  });

  /* =========================================================================
     5. MANUAL SCHEDULING MODE & REAL-TIME PRE-FLIGHT VALIDATION
     ========================================================================= */
  function populateManualFormOptions() {
    // Subjects
    manualSubject.innerHTML = `<option value="">-- Choose Subject --</option>`;
    state.subjects.forEach((sub) => {
      const opt = document.createElement("option");
      opt.value = sub.id;
      opt.textContent = `${sub.code} - ${sub.title}`;
      manualSubject.appendChild(opt);
    });

    // Sections
    manualSection.innerHTML = `<option value="">-- Choose Section --</option>`;
    state.sections.forEach((sec) => {
      const opt = document.createElement("option");
      opt.value = sec.id;
      opt.textContent = `${sec.name} (${sec.program} Yr ${sec.year_level})`;
      manualSection.appendChild(opt);
    });

    // Faculty
    manualFaculty.innerHTML = `<option value="">-- Choose Faculty Member --</option>`;
    state.faculty.forEach((fac) => {
      const opt = document.createElement("option");
      opt.value = fac.id;
      opt.textContent = `${fac.name} (${fac.department || "Faculty"})`;
      manualFaculty.appendChild(opt);
    });

    // Rooms
    manualRoom.innerHTML = `<option value="">-- Choose Physical Room --</option>`;
    state.rooms.forEach((r) => {
      const roomName = r.room_code || r.name;
      const roomType = r.room_type || r.type || "LECTURE";
      const opt = document.createElement("option");
      opt.value = r.id;
      opt.textContent = `${roomName} (${roomType}, Cap: ${r.capacity})`;
      manualRoom.appendChild(opt);
    });
  }

  // Meta update on Subject select
  manualSubject.addEventListener("change", () => {
    const subId = parseInt(manualSubject.value, 10);
    const sub = state.subjects.find((s) => s.id === subId);
    if (sub) {
      const subType = sub.subject_type || sub.type || "LECTURE";
      const isLab = String(subType).toUpperCase().includes("LAB");
      manualSubjectMeta.style.display = "block";
      manualSubjectMeta.innerHTML = `
        <span><strong>Units:</strong> ${sub.units}</span> •
        <span><strong>Type:</strong> <span class="badge-role">${escapeHtml(subType)}</span></span> •
        <span><strong>Standard Duration:</strong> ${isLab ? "3.0 hrs" : "1.5 hrs"}</span>
      `;

      // Auto-set standard duration end-time if start-time exists
      if (manualStartTime.value) {
        const [h, m] = manualStartTime.value.split(":").map(Number);
        const addMinutes = isLab ? 180 : 90;
        const totalMin = h * 60 + m + addMinutes;
        const endH = String(Math.floor(totalMin / 60)).padStart(2, "0");
        const endM = String(totalMin % 60).padStart(2, "0");
        manualEndTime.value = `${endH}:${endM}`;
      }
    } else {
      manualSubjectMeta.style.display = "none";
      manualSubjectMeta.innerHTML = "";
    }
    triggerManualPreflight();
  });

  // Meta update on Section select
  manualSection.addEventListener("change", () => {
    const secId = parseInt(manualSection.value, 10);
    const sec = state.sections.find((s) => s.id === secId);
    if (sec) {
      manualSectionMeta.style.display = "block";
      manualSectionMeta.innerHTML = `
        <span><strong>Cohort:</strong> ${escapeHtml(sec.program)} Year ${sec.year_level}</span> •
        <span><strong>Enrolled:</strong> ${sec.student_count || 40} students</span>
      `;
    } else {
      manualSectionMeta.style.display = "none";
      manualSectionMeta.innerHTML = "";
    }
    triggerManualPreflight();
  });

  // Attach event listeners for real-time conflict checking
  [
    manualFaculty,
    manualRoom,
    manualDay,
    manualStartTime,
    manualEndTime,
  ].forEach((el) => {
    el.addEventListener("change", triggerManualPreflight);
    el.addEventListener("input", triggerManualPreflight);
  });

  function triggerManualPreflight() {
    clearTimeout(state.checkDebounceTimer);
    state.checkDebounceTimer = setTimeout(runPreFlightConflictCheck, 280);
  }

  async function runPreFlightConflictCheck() {
    const subjectId = manualSubject.value;
    const sectionId = manualSection.value;
    const facultyId = manualFaculty.value;
    const roomId = manualRoom.value;
    const day = manualDay.value;
    const startTime = manualStartTime.value;
    const endTime = manualEndTime.value;

    // Check if sufficient parameters are selected
    if (!subjectId || !sectionId || !facultyId || !roomId || !day || !startTime || !endTime) {
      manualConflictBanner.style.display = "none";
      manualConflictBanner.innerHTML = "";
      return;
    }

    // Temporal inversion guard
    if (startTime >= endTime) {
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
      btnSaveManualSlot.disabled = true;
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
      manualConflictBanner.style.display = "block";

      if (data.valid) {
        manualConflictBanner.className = "validation-banner banner-success";
        manualConflictBanner.innerHTML = `
          <div class="banner-content">
            <span class="banner-icon">✔</span>
            <div>
              <strong>Slot Available (No Conflicts Detected)</strong>
              <p>Hard constraints verified. Physical room, instructor load, and cohort availability are clear.</p>
            </div>
          </div>
        `;
        btnSaveManualSlot.disabled = false;
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
                      )} ${s.room_name ? `in <strong>${escapeHtml(s.room_name)}</strong>` : ""}</li>`
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
              <strong>Schedule Collision Detected</strong>
              <ul class="conflict-bullet-list">${conflictList}</ul>
              ${suggestionsHtml}
            </div>
          </div>
        `;
        btnSaveManualSlot.disabled = false; // Chair can still submit if they intend to trigger formal 409 or resolve
      }
    } catch (err) {
      console.error("Pre-flight conflict check error:", err);
    }
  }

  // Manual Form Submission
  formManual.addEventListener("submit", async (e) => {
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

    btnSaveManualSlot.disabled = true;
    btnSaveManualSlot.innerHTML = `<span class="btn-spinner"></span> Saving Slot...`;

    try {
      const res = await fetch("/api/schedules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      btnSaveManualSlot.disabled = false;
      btnSaveManualSlot.innerHTML = `<span>Save Schedule Slot &rarr;</span>`;

      if (res.ok) {
        showToast("Schedule slot successfully saved!", "success");
        // Reset or clear fields
        manualConflictBanner.style.display = "none";
        // Optionally redirect to /schedules or let user configure next slot
        setTimeout(() => {
          if (confirm("Slot created! Would you like to review the timetable grid now?")) {
            window.location.href = "/schedules";
          }
        }, 300);
      } else {
        const errorMsg = data.error || (data.conflicts ? data.conflicts.join("; ") : "Failed to create schedule slot.");
        showToast(`Conflict Error: ${errorMsg}`, "error");
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
    } catch (err) {
      btnSaveManualSlot.disabled = false;
      btnSaveManualSlot.innerHTML = `<span>Save Schedule Slot &rarr;</span>`;
      showToast("Network error while creating schedule slot.", "error");
      console.error(err);
    }
  });

  /* =========================================================================
     6. UTILITY HELPERS
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
