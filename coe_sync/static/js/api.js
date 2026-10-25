/**
 * COE SYNC 2026 - Reusable REST API Client Wrapper (api.js)
 * Clean, centralized fetch wrapper with automatic JSON handling and error parsing.
 */

const API = {
  /**
   * Core request executor
   */
  async request(endpoint, options = {}) {
    const config = {
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      credentials: "same-origin",
      ...options,
    };

    if (config.body && typeof config.body === "object" && !(config.body instanceof FormData)) {
      config.body = JSON.stringify(config.body);
    }

    try {
      const response = await fetch(endpoint, config);
      let data = null;

      const contentType = response.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        data = await response.json();
      } else {
        const text = await response.text();
        data = { message: text };
      }

      if (!response.ok) {
        const err = new Error(data.error || data.message || `HTTP ${response.status} Error`);
        err.status = response.status;
        err.data = data;
        throw err;
      }

      return data;
    } catch (err) {
      console.error(`[API Error] ${options.method || "GET"} ${endpoint}:`, err);
      throw err;
    }
  },

  get(endpoint, params = null) {
    let url = endpoint;
    if (params) {
      const query = new URLSearchParams(params).toString();
      url += (url.includes("?") ? "&" : "?") + query;
    }
    return this.request(url, { method: "GET" });
  },

  post(endpoint, body = {}) {
    return this.request(endpoint, { method: "POST", body });
  },

  put(endpoint, body = {}) {
    return this.request(endpoint, { method: "PUT", body });
  },

  patch(endpoint, body = {}) {
    return this.request(endpoint, { method: "PATCH", body });
  },

  delete(endpoint) {
    return this.request(endpoint, { method: "DELETE" });
  },

  // -------------------------------------------------------------
  // Common Application Convenience Methods
  // -------------------------------------------------------------
  async impersonate(role, referenceId = null) {
    return this.post("/api/auth/impersonate", { role, reference_id: referenceId });
  },

  async getCurrentSession() {
    return this.get("/api/auth/me");
  },

  async getHealth() {
    return this.get("/api/health");
  },

  async getAnalyticsSummary(params = null) {
    return this.get("/api/analytics/summary", params);
  },

  async getSections(params = null) {
    return this.get("/api/sections", params);
  },

  async getSubjects(params = null) {
    return this.get("/api/subjects", params);
  },

  async getFaculty(params = null) {
    return this.get("/api/faculty", params);
  },

  async getRooms(params = null) {
    return this.get("/api/rooms", params);
  },

  async getMasterData() {
    const [sec, sub, fac, rm] = await Promise.all([
      this.get("/api/sections"),
      this.get("/api/subjects"),
      this.get("/api/faculty"),
      this.get("/api/rooms"),
    ]);
    return {
      sections: sec.data || [],
      subjects: sub.data || [],
      faculty: fac.data || [],
      rooms: rm.data || [],
    };
  },

  async getSchedules(filters = null) {
    return this.get("/api/schedules", filters);
  },

  async checkConflicts(payload) {
    return this.post("/api/conflicts/check", payload);
  },

  async createSchedule(payload) {
    return this.post("/api/schedules", payload);
  },

  async generateDraftSchedules() {
    return this.post("/api/schedules/generate-draft");
  },

  async publishAllSchedules(payload = {}) {
    return this.post("/api/schedules/publish-all", payload);
  },

  async unpublishAllSchedules(payload = {}) {
    return this.post("/api/schedules/unpublish-all", payload);
  },

  async getFacultyAvailability(facultyId) {
    return this.get(`/api/faculty/${facultyId}/availability`);
  },

  async createFacultyAvailability(facultyId, payload) {
    return this.post(`/api/faculty/${facultyId}/availability`, payload);
  },

  async deleteFacultyAvailability(availId) {
    return this.delete(`/api/availabilities/${availId}`);
  },

  async getChairStatus() {
    return this.get("/api/chair/status");
  },

  async updateChairStatus(isActive) {
    return this.post("/api/chair/status", { is_active: Boolean(isActive) });
  },

  async getRescheduleRequests(status = null) {
    const params = status ? { status } : null;
    return this.get("/api/reschedule/requests", params);
  },

  async submitRescheduleRequest(payload) {
    return this.post("/api/reschedule/request", payload);
  },

  async reviewRescheduleByFaculty(requestId, approved, feedback = "") {
    return this.post(`/api/reschedule/${requestId}/faculty-review`, {
      approved: Boolean(approved),
      feedback,
    });
  },

  async decideRescheduleByChair(requestId, approved, feedback = "") {
    return this.post(`/api/reschedule/${requestId}/chair-decision`, {
      approved: Boolean(approved),
      feedback,
    });
  },

  async login(username, password) {
    return this.post("/api/auth/login", { username, password });
  },

  async changeCredentials(payload) {
    return this.post("/api/auth/update-credentials", payload);
  },

  async updateCredentials(payload) {
    return this.post("/api/auth/update-credentials", payload);
  },

  async getDemoCredentials() {
    return this.get("/api/auth/demo-credentials");
  },

  async getAnalyticsReports(params = null) {
    return this.get("/api/analytics/reports", params);
  },

  async seedDatabase() {
    return this.post("/api/seed");
  },
};

// Global export for vanilla scripts
window.API = API;
