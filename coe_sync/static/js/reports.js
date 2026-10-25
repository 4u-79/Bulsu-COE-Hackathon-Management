/**
 * COE SYNC 2026 - Institutional Analytics & Reports (reports.js)
 * Zero CDN dependencies: Pure HTML5/CSS visual charts, dynamic filtering, CSV export, and print formatting.
 */

document.addEventListener("DOMContentLoaded", () => {
  const ReportsManager = {
    summaryData: null,
    roomsData: [],
    facultyData: [],
    sectionsData: [],

    // DOM Elements
    kpiRoomUtil: document.getElementById("kpi-room-utilization"),
    kpiOverloadCount: document.getElementById("kpi-overload-count"),
    kpiQualityScore: document.getElementById("kpi-quality-score"),
    kpiTotalClasses: document.getElementById("kpi-total-classes"),

    filterTerm: document.getElementById("filter-term"),
    filterProgram: document.getElementById("filter-program"),
    filterSectionScope: document.getElementById("filter-section-scope"),
    filterRoomType: document.getElementById("filter-room-type"),
    filterUtilThreshold: document.getElementById("filter-util-threshold"),

    roomUtilSearch: document.getElementById("room-util-search"),
    facultyWorkloadSearch: document.getElementById("faculty-workload-search"),

    roomMetersContainer: document.getElementById("room-meters-container"),
    facultyMetersContainer: document.getElementById("faculty-meters-container"),
    roomsReportTbody: document.getElementById("rooms-report-tbody"),
    facultyReportTbody: document.getElementById("faculty-report-tbody"),

    btnExportReports: document.getElementById("btn-export-reports"),
    btnPrintReports: document.getElementById("btn-print-reports"),

    async init() {
      this.bindEvents();
      await this.loadData();
    },

    bindEvents() {
      if (this.filterTerm) {
        this.filterTerm.value = localStorage.getItem("coe_sync_active_term") || "1";
        this.filterTerm.addEventListener("change", (e) => {
          localStorage.setItem("coe_sync_active_term", e.target.value);
          window.dispatchEvent(new CustomEvent("academicTermChanged", { detail: { term: e.target.value } }));
          this.applyFilters();
        });
      }
      if (this.filterProgram) {
        this.filterProgram.addEventListener("change", () => this.loadData());
      }
      if (this.filterSectionScope) {
        this.filterSectionScope.addEventListener("change", () => this.applyFilters());
      }
      if (this.filterRoomType) {
        this.filterRoomType.addEventListener("change", () => this.applyFilters());
      }
      if (this.filterUtilThreshold) {
        this.filterUtilThreshold.addEventListener("change", () => this.applyFilters());
      }

      // Room Utilization Live Filter
      if (this.roomUtilSearch) {
        this.roomUtilSearch.addEventListener("input", (e) => {
          const term = e.target.value.toLowerCase().trim();
          const roomItems = document.querySelectorAll(".room-util-item");
          roomItems.forEach((item) => {
            const text = item.textContent.toLowerCase();
            item.style.display = text.includes(term) ? "" : "none";
          });
        });
      }

      // Faculty Workload Live Filter
      if (this.facultyWorkloadSearch) {
        this.facultyWorkloadSearch.addEventListener("input", (e) => {
          const term = e.target.value.toLowerCase().trim();
          const facultyItems = document.querySelectorAll(".faculty-workload-item");
          facultyItems.forEach((item) => {
            const text = item.textContent.toLowerCase();
            item.style.display = text.includes(term) ? "" : "none";
          });
        });
      }

      if (this.btnExportReports) {
        this.btnExportReports.addEventListener("click", () => this.exportCSV());
      }

      if (this.btnPrintReports) {
        this.btnPrintReports.addEventListener("click", () => window.print());
      }
    },

    async loadData() {
      try {
        const params = {};
        if (this.filterProgram && this.filterProgram.value && this.filterProgram.value !== "ALL") {
          params.program = this.filterProgram.value;
        }

        const [res, reportsRes] = await Promise.all([
          API.getAnalyticsSummary(params),
          API.getAnalyticsReports(params).catch(() => null),
        ]);

        if (res.status === "success" && res.data) {
          this.summaryData = res.data;
          this.roomsData = res.data.room_breakdown || [];
          this.facultyData = res.data.faculty_workloads || [];
          this.sectionsData = res.data.section_breakdown || [];

          if (reportsRes?.status === "success" && reportsRes.data?.quality_score) {
            this.qualityReport = reportsRes.data.quality_score;
          }

          // Dynamically reflect Department Specific Analytics vs Institutional
          const mainTitle = document.getElementById("reports-main-title");
          const mainSubtitle = document.getElementById("reports-main-subtitle");
          const kpiClassesSubtext = document.getElementById("kpi-total-classes-subtext");
          const kpiOverloadSubtext = document.getElementById("kpi-overload-subtext");

          if (res.data.is_department_scoped && res.data.program_scope) {
            if (mainTitle) mainTitle.textContent = "Department Specific Analytics";
            if (mainSubtitle) mainSubtitle.textContent = `BulSU College of Engineering • ${res.data.program_scope} Department Capacity & Faculty Allocation Intelligence`;
            if (kpiClassesSubtext) kpiClassesSubtext.textContent = `Active course offerings in ${res.data.program_scope} department`;
            if (kpiOverloadSubtext) kpiOverloadSubtext.textContent = `${res.data.program_scope} instructors exceeding 21-unit policy threshold`;
          } else {
            if (mainTitle) mainTitle.textContent = "Institutional Analytics & Reports";
            if (mainSubtitle) mainSubtitle.textContent = "BulSU College of Engineering • Academic Term Capacity & Faculty Allocation Intelligence";
            if (kpiClassesSubtext) kpiClassesSubtext.textContent = "Active course offerings across all degree programs";
            if (kpiOverloadSubtext) kpiOverloadSubtext.textContent = "Instructors exceeding 21-unit policy threshold";
          }

          this.populateKPIs();
          this.populateSectionFilter();
          this.renderQualityDeductions();
          await this.applyFilters();
        }
      } catch (err) {
        console.error("Failed to load analytics reports data:", err);
        if (window.showToast) {
          window.showToast("Failed to load analytics data", true);
        }
      }
    },

    renderQualityDeductions() {
      const card = document.getElementById("quality-score-deductions-card");
      const tbody = document.getElementById("quality-deductions-tbody");
      const badge = document.getElementById("quality-penalty-badge");

      if (!card || !tbody) return;
      card.style.display = "block";

      const deductions = this.qualityReport?.deductions || [];
      if (badge) {
        const penalty = this.qualityReport?.total_penalty || 0;
        badge.textContent = `${penalty} Points Deducted`;
        badge.className = `status-badge ${penalty > 0 ? "amber" : "mint"}`;
      }

      if (deductions.length === 0) {
        tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted); padding: 18px;">Zero soft constraint violations! High quality schedule (100/100).</td></tr>`;
        return;
      }

      tbody.innerHTML = deductions.map((d) => `
        <tr>
          <td><span class="status-badge crimson">${d.points} pts</span></td>
          <td><strong>${d.type === 'SECTION_IDLE_GAP' ? 'Section Idle Gap (&gt;2h)' : 'Faculty Overload (&gt;21 units)'}</strong></td>
          <td style="font-size: 13px; color: var(--text-secondary);">${this.escapeHtml(d.reason)}</td>
        </tr>
      `).join("");
    },

    populateKPIs() {
      if (!this.summaryData) return;

      if (this.kpiRoomUtil) {
        const utilPct = this.summaryData.overall_room_utilization_pct !== undefined
          ? this.summaryData.overall_room_utilization_pct
          : (this.summaryData.room_utilization || 0);
        this.kpiRoomUtil.textContent = `${Number(utilPct).toFixed(2)}%`;
      }

      const overloadedCount = this.facultyData.filter(f => f.is_overloaded).length;
      if (this.kpiOverloadCount) {
        this.kpiOverloadCount.textContent = overloadedCount;
        const card = document.getElementById("kpi-card-overload");
        if (card) {
          if (overloadedCount > 0) {
            card.style.borderColor = "#F59E0B";
            card.style.background = "#FEF3C7";
          } else {
            card.style.borderColor = "";
            card.style.background = "";
          }
        }
      }

      if (this.kpiQualityScore) {
        const score = this.qualityReport?.score ?? (this.summaryData.schedule_quality_score ?? 100);
        this.kpiQualityScore.textContent = `${score}/100`;
      }

      if (this.kpiTotalClasses) {
        this.kpiTotalClasses.textContent = this.summaryData.total_classes || 0;
      }
    },

    populateSectionFilter() {
      if (!this.filterSectionScope) return;
      // Preserve first "ALL" option
      this.filterSectionScope.innerHTML = '<option value="ALL">All Sections</option>';
      this.sectionsData.forEach(sec => {
        const opt = document.createElement("option");
        opt.value = sec.id;
        opt.textContent = `${sec.name} (${sec.program} Y${sec.year_level})`;
        this.filterSectionScope.appendChild(opt);
      });
    },

    async applyFilters() {
      const typeFilter = this.filterRoomType ? this.filterRoomType.value : "ALL";
      const thresholdFilter = this.filterUtilThreshold ? this.filterUtilThreshold.value : "ALL";
      const sectionFilter = this.filterSectionScope ? this.filterSectionScope.value : "ALL";

      let sectionRoomIds = null;
      let sectionFacultyIds = null;

      if (sectionFilter !== "ALL") {
        try {
          const res = await API.getSchedules({ section_id: sectionFilter });
          if (res.status === "success" && Array.isArray(res.data)) {
            sectionRoomIds = new Set(res.data.map(s => s.room_id).filter(Boolean));
            sectionFacultyIds = new Set(res.data.map(s => s.faculty_id).filter(Boolean));
          }
        } catch (e) {
          console.warn("Could not filter by section:", e);
        }
      }

      // Filter Rooms
      let filteredRooms = [...this.roomsData];
      if (typeFilter !== "ALL") {
        filteredRooms = filteredRooms.filter(r => r.room_type === typeFilter || (typeFilter === "LECTURE" && r.room_type === "LEC"));
      }

      if (thresholdFilter === "HIGH") {
        filteredRooms = filteredRooms.filter(r => r.utilization_rate > 75);
      } else if (thresholdFilter === "MODERATE") {
        filteredRooms = filteredRooms.filter(r => r.utilization_rate >= 50 && r.utilization_rate <= 75);
      } else if (thresholdFilter === "LOW") {
        filteredRooms = filteredRooms.filter(r => r.utilization_rate >= 25 && r.utilization_rate < 50);
      } else if (thresholdFilter === "UNDER") {
        filteredRooms = filteredRooms.filter(r => r.utilization_rate < 25);
      }

      if (sectionRoomIds) {
        filteredRooms = filteredRooms.filter(r => sectionRoomIds.has(r.id));
      }

      this.renderRoomMeters(filteredRooms);
      this.renderRoomsTable(filteredRooms);

      // Filter Faculty
      let filteredFaculty = [...this.facultyData];
      if (sectionFacultyIds) {
        filteredFaculty = filteredFaculty.filter(f => sectionFacultyIds.has(f.id));
      }

      this.renderFacultyMeters(filteredFaculty);
      this.renderFacultyTable(filteredFaculty);
    },

    renderRoomMeters(rooms) {
      if (!this.roomMetersContainer) return;
      if (rooms.length === 0) {
        this.roomMetersContainer.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 24px;">No rooms match the selected filter criteria.</div>';
        return;
      }

      this.roomMetersContainer.innerHTML = rooms.map(r => {
        let fillClass = "room-safe";
        if (r.utilization_rate > 75) {
          fillClass = "room-max";
        } else if (r.utilization_rate >= 50) {
          fillClass = "room-dense";
        }

        const widthPct = Math.min(100, Math.max(0, r.utilization_rate));

        return `
          <div class="meter-row room-util-item" title="${r.name} scheduled for ${r.scheduled_hours} hrs of 72.0 available weekly hours">
            <div class="meter-header">
              <span class="meter-name">
                <span>${this.escapeHtml(r.name)}</span>
                <span class="badge ${r.room_type === 'LAB' ? 'badge-lab' : 'badge-lecture'}">${r.room_type}</span>
              </span>
              <span class="meter-detail">
                <strong>${r.scheduled_hours}h</strong> / ${r.available_hours}h (${r.utilization_rate}%)
              </span>
            </div>
            <div class="meter-track">
              <div class="meter-fill ${fillClass}" style="width: ${widthPct}%;"></div>
            </div>
          </div>
        `;
      }).join("");

      // Preserve active search filter
      if (this.roomUtilSearch && this.roomUtilSearch.value.trim()) {
        const term = this.roomUtilSearch.value.toLowerCase().trim();
        this.roomMetersContainer.querySelectorAll(".room-util-item").forEach(item => {
          const text = item.textContent.toLowerCase();
          item.style.display = text.includes(term) ? "" : "none";
        });
      }
    },

    renderFacultyMeters(faculty) {
      if (!this.facultyMetersContainer) return;
      if (faculty.length === 0) {
        this.facultyMetersContainer.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 24px;">No faculty records found.</div>';
        return;
      }

      this.facultyMetersContainer.innerHTML = faculty.map(f => {
        const pct = f.max_units > 0 ? Math.round((f.assigned_units / f.max_units) * 100) : 0;
        let fillClass = "normal";
        let statusBadge = '<span class="status-badge mint">NORMAL</span>';

        if (f.is_overloaded) {
          fillClass = "overload";
          statusBadge = '<span class="status-badge crimson">OVERLOADED</span>';
        } else if (f.assigned_units >= 19) {
          fillClass = "warning";
          statusBadge = '<span class="status-badge amber">NEAR MAX</span>';
        }

        const widthPct = Math.min(100, Math.max(0, pct));

        return `
          <div class="meter-row faculty-workload-item" title="${f.name} teaching ${f.teaching_hours || 0} hrs (${f.assigned_units} of ${f.max_units} max units)">
            <div class="meter-header">
              <span class="meter-name">
                <span>${this.escapeHtml(f.name)}</span>
                ${statusBadge}
              </span>
              <span class="meter-detail">
                <strong>${f.assigned_units}</strong> / ${f.max_units} units (${pct}%)
              </span>
            </div>
            <div class="meter-track">
              <div class="meter-fill ${fillClass}" style="width: ${widthPct}%;"></div>
            </div>
          </div>
        `;
      }).join("");

      // Preserve active search filter
      if (this.facultyWorkloadSearch && this.facultyWorkloadSearch.value.trim()) {
        const term = this.facultyWorkloadSearch.value.toLowerCase().trim();
        this.facultyMetersContainer.querySelectorAll(".faculty-workload-item").forEach(item => {
          const text = item.textContent.toLowerCase();
          item.style.display = text.includes(term) ? "" : "none";
        });
      }
    },

    renderRoomsTable(rooms) {
      if (!this.roomsReportTbody) return;
      if (rooms.length === 0) {
        this.roomsReportTbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 18px;">No rooms match criteria.</td></tr>';
        return;
      }

      this.roomsReportTbody.innerHTML = rooms.map(r => {
        let badge = '<span class="status-badge blue">Underutilized</span>';
        if (r.utilization_rate > 75) {
          badge = '<span class="status-badge amber">High Demand</span>';
        } else if (r.utilization_rate >= 50) {
          badge = '<span class="status-badge mint">Optimal</span>';
        }

        return `
          <tr>
            <td><strong>${this.escapeHtml(r.name)}</strong></td>
            <td><span class="badge ${r.room_type === 'LAB' ? 'badge-lab' : 'badge-lecture'}">${r.room_type}</span></td>
            <td>${r.scheduled_hours} hrs</td>
            <td>${r.available_hours} hrs</td>
            <td><strong>${r.utilization_rate}%</strong></td>
            <td>${badge}</td>
          </tr>
        `;
      }).join("");
    },

    renderFacultyTable(faculty) {
      if (!this.facultyReportTbody) return;
      if (faculty.length === 0) {
        this.facultyReportTbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 18px;">No faculty records found.</td></tr>';
        return;
      }

      this.facultyReportTbody.innerHTML = faculty.map(f => {
        const pct = f.max_units > 0 ? Math.round((f.assigned_units / f.max_units) * 100) : 0;
        let badge = '<span class="status-badge mint">Normal Load</span>';
        if (f.is_overloaded) {
          badge = '<span class="status-badge crimson">Overloaded (>21u)</span>';
        } else if (f.assigned_units >= 19) {
          badge = '<span class="status-badge amber">Near Capacity</span>';
        }

        return `
          <tr>
            <td><strong>${this.escapeHtml(f.name)}</strong></td>
            <td>${this.escapeHtml(f.email || 'N/A')}</td>
            <td>${f.teaching_hours || 0} hrs/wk</td>
            <td><strong>${f.assigned_units}</strong> units</td>
            <td>${f.max_units} units</td>
            <td>${pct}%</td>
            <td>${badge}</td>
          </tr>
        `;
      }).join("");
    },

    exportCSV() {
      if (!this.roomsData.length && !this.facultyData.length) {
        alert("No report data available to export.");
        return;
      }

      let csvContent = "data:text/csv;charset=utf-8,";

      // 1. Header
      const isDept = this.summaryData?.is_department_scoped && this.summaryData?.program_scope;
      const reportTitle = isDept
        ? `BULSU COLLEGE OF ENGINEERING - ${this.summaryData.program_scope} DEPARTMENT UTILIZATION & WORKLOAD REPORT`
        : "BULSU COLLEGE OF ENGINEERING - INSTITUTIONAL UTILIZATION & WORKLOAD REPORT";
      csvContent += `${reportTitle}\n`;
      csvContent += `Generated On,${new Date().toLocaleString()}\n`;
      csvContent += `Term,1st Semester AY 2026-2027\n\n`;

      // 2. Room Utilization Section
      csvContent += "ROOM UTILIZATION MATRIX (Operating Hours: Mon-Sat 7:00 AM - 7:00 PM = 72.0 Hours Max)\n";
      csvContent += "Room Code,Type,Scheduled Hours,Weekly Max Hours,Utilization Rate (%),Classes Count\n";
      this.roomsData.forEach(r => {
        csvContent += `"${r.name}","${r.room_type}",${r.scheduled_hours},${r.available_hours},${r.utilization_rate}%,${r.schedule_count}\n`;
      });

      csvContent += "\n";

      // 3. Faculty Workload Section
      csvContent += "FACULTY WORKLOAD DISTRIBUTION (Max Policy Threshold: 21 Units)\n";
      csvContent += "Faculty Member,Email,Teaching Hours,Assigned Units,Max Limit,Load (%),Status\n";
      this.facultyData.forEach(f => {
        const pct = f.max_units > 0 ? Math.round((f.assigned_units / f.max_units) * 100) : 0;
        const status = f.is_overloaded ? "OVERLOADED" : (f.assigned_units >= 19 ? "NEAR MAX" : "NORMAL");
        csvContent += `"${f.name}","${f.email || ''}",${f.teaching_hours || 0},${f.assigned_units},${f.max_units},${pct}%,"${status}"\n`;
      });

      // Trigger download
      const encodedUri = encodeURI(csvContent);
      const link = document.createElement("a");
      link.setAttribute("href", encodedUri);
      const filePrefix = isDept ? `BulSU_COE_${this.summaryData.program_scope}_Report_` : "BulSU_COE_Utilization_Report_";
      link.setAttribute("download", `${filePrefix}${new Date().toISOString().slice(0, 10)}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    },

    escapeHtml(str) {
      if (!str) return "";
      const div = document.createElement("div");
      div.textContent = str;
      return div.innerHTML;
    }
  };

  ReportsManager.init();
});
