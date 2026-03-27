const API_BASE = 
window.location.origin;

/* ================= STATE ================= */

let hrecPerfChartInstance = null;
let hrecFunnelChartInstance = null;
let hrecPerfSeriesChartInstance = null;
let hrecEmpPerfChartInstance = null;
let selectedCandidateApplication = null;
let currentInterview = null;
window._hrApps = [];

/* ================= UTIL ================= */

function qs(sel) {
  return document.querySelector(sel);
}

function qsa(sel) {
  return Array.from(document.querySelectorAll(sel));
}

function token() {
  return localStorage.getItem("hrec_token") || "";
}

function setSession(t, u) {
  localStorage.setItem("hrec_token", t);
  localStorage.setItem("hrec_user", JSON.stringify(u));
}

function user() {
  try {
    return JSON.parse(localStorage.getItem("hrec_user") || "null");
  } catch {
    return null;
  }
}

function clearSession() {
  localStorage.removeItem("hrec_token");
  localStorage.removeItem("hrec_user");
}

function normalizeRole(role) {
  const r = String(role || "").trim().toLowerCase();
  if (r === "hr") return "HR";
  if (r === "employee") return "Employee";
  return "Candidate";
}

function withLoading(btn, text = "Loading...") {
  if (!btn) return () => {};
  const original = btn.dataset.originalText || btn.textContent;
  btn.dataset.originalText = original;
  btn.disabled = true;
  btn.textContent = text;

  return () => {
    btn.disabled = false;
    btn.textContent = btn.dataset.originalText || original;
  };
}

let hrecAlertTimer = null;

function setAlert(msg, kind = "error") {
  const el = qs("#alert");
  if (!el) {
    alert(msg);
    return;
  }

  if (hrecAlertTimer) {
    clearTimeout(hrecAlertTimer);
    hrecAlertTimer = null;
  }

  el.textContent = msg || "";
  el.classList.remove("hidden", "ok", "error");
  el.classList.add(kind === "ok" ? "ok" : "error");

  hrecAlertTimer = setTimeout(() => {
    clearAlert();
  }, 2500);
}

function clearAlert() {
  const el = qs("#alert");
  if (!el) return;
  el.textContent = "";
  el.classList.add("hidden");
  el.classList.remove("ok", "error");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function recommendationBadge(text) {
  const t = String(text || "").toLowerCase();
  if (!t) return "<span class='muted'>—</span>";

  let cls = "badge";
  if (["shortlist", "accepted", "success", "completed"].includes(t)) cls += " ok";
  else if (["review", "pending", "info"].includes(t)) cls += " warn";
  else cls += " danger";

  return `<span class="${cls}">${escapeHtml(text)}</span>`;
}

function renderBadgeList(items = [], type = "default") {
  if (!items || !items.length) return "<span class='muted'>—</span>";

  let extra = "";
  if (type === "ok") extra = " ok";
  if (type === "danger") extra = " danger";
  if (type === "warn") extra = " warn";

  return items
    .map((item) => `<span class="badge${extra}">${escapeHtml(item)}</span>`)
    .join(" ");
}

function parseAuthFromUrl() {
  const params = new URLSearchParams(window.location.search);

  const t = params.get("token");
  const name = params.get("name");
  const email = params.get("email");
  const role = params.get("role");

  if (t && email) {
    console.log("Saving session from URL");

    setSession(t, {
      name: name || "",
      email,
      role: normalizeRole(role),
    });

    // clean URL after saving
    window.history.replaceState({}, document.title, window.location.pathname);
  }
}

/* ================= THEME ================= */

function getTheme() {
  return localStorage.getItem("hrec_theme") || "dark";
}

function applyTheme(theme) {
  document.body.classList.remove("theme-dark", "theme-light");
  document.body.classList.add(theme === "light" ? "theme-light" : "theme-dark");
}

function setTheme(theme) {
  localStorage.setItem("hrec_theme", theme);
  applyTheme(theme);
}

function initThemeToggle() {
  applyTheme(getTheme());

  const btn = qs("#themeToggle");
  if (btn && !btn.dataset.bound) {
    btn.dataset.bound = "1";
    btn.addEventListener("click", () => {
      const next = getTheme() === "light" ? "dark" : "light";
      setTheme(next);
    });
  }
}

/* ================= API ================= */

async function api(path, { method = "GET", body } = {}) {
  const headers = {};

  if (token()) headers["Authorization"] = `Bearer ${token()}`;
  if (body && !(body instanceof FormData)) headers["Content-Type"] = "application/json";

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? (body instanceof FormData ? body : JSON.stringify(body)) : undefined,
  });

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    if (res.status === 401 || res.status === 403) {
      clearSession();
    }
    throw new Error(data.error || data.message || `Request failed (${res.status})`);
  }

  return data;
}

/* ================= AUTH PAGE ================= */

function initAuthPage() {
  initThemeToggle();
  clearAlert();

  if (token()) {
    location.href = "dashboard.html";
    return;
  }

  const loginForm = qs("#loginForm");
  const registerForm = qs("#registerForm");
  const tabs = qsa(".tab");

  tabs.forEach((tab) => {
    if (tab.dataset.bound === "1") return;
    tab.dataset.bound = "1";

    tab.addEventListener("click", () => {
      tabs.forEach((x) => x.classList.remove("active"));
      tab.classList.add("active");

      const mode = tab.dataset.tab;
      if (loginForm) loginForm.classList.toggle("hidden", mode !== "login");
      if (registerForm) registerForm.classList.toggle("hidden", mode !== "register");
      clearAlert();
    });
  });

  if (loginForm && !loginForm.dataset.bound) {
    loginForm.dataset.bound = "1";

    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearAlert();

      const btn = loginForm.querySelector("button[type='submit']");
      const stop = withLoading(btn, "Logging in...");
      const fd = new FormData(loginForm);

      try {
        const data = await api("/api/auth/login", {
          method: "POST",
          body: {
            email: fd.get("email"),
            password: fd.get("password"),
          },
        });

        setSession(data.token, {
          name: data.user?.name || "",
          email: data.user?.email || "",
          role: normalizeRole(data.user?.role || "Candidate"),
        });
        location.href = "dashboard.html";
      } catch (err) {
        setAlert(err.message || "Login failed");
      } finally {
        stop();
      }
    });
  }

  if (registerForm && !registerForm.dataset.bound) {
    registerForm.dataset.bound = "1";

    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearAlert();

      const btn = registerForm.querySelector("button[type='submit']");
      const stop = withLoading(btn, "Creating...");
      const fd = new FormData(registerForm);

      try {
        const data = await api("/api/auth/register", {
          method: "POST",
          body: {
            name: fd.get("name"),
            email: fd.get("email"),
            password: fd.get("password"),
            role: fd.get("role"),
          },
        });

        setSession(data.token, {
          name: data.user?.name || "",
          email: data.user?.email || "",
          role: normalizeRole(data.user?.role || "Candidate"),
        });
        location.href = "dashboard.html";
      } catch (err) {
        setAlert(err.message || "Registration failed");
      } finally {
        stop();
      }
    });
  }

  const googleBtn = qs("#googleBtn");
  if (googleBtn && !googleBtn.dataset.bound) {
    googleBtn.dataset.bound = "1";
    googleBtn.addEventListener("click", () => {
      clearAlert();
      const role = qs("#googleRole")?.value || "Candidate";
      window.location.href = `${API_BASE}/google-login-start?role=${encodeURIComponent(role)}`;
    });
  }
}

/* ================= NAV ================= */

const NAV_BY_ROLE = {
  HR: [
    { key: "hr_jobs", label: "Jobs" },
    { key: "hr_candidates", label: "Candidate Reviews" },
    { key: "hr_tasks", label: "Task Management" },
    { key: "hr_performance", label: "Performance Insights" },
    { key: "hr_analytics", label: "Analytics" },
    { key: "notifications", label: "Notifications" },
  ],
  Candidate: [
    { key: "cand_jobs", label: "Opportunities" },
    { key: "cand_apps", label: "My Applications" },
    { key: "cand_resume", label: "Resume Analysis" },
    { key: "cand_interview", label: "AI Interview Assistant" },
    { key: "notifications", label: "Notifications" },
  ],
  Employee: [
    { key: "emp_tasks", label: "My Tasks" },
    { key: "emp_performance", label: "Performance Insights" },
    { key: "notifications", label: "Notifications" },
  ],
};

function showPanel(key) {
  qsa(".panel").forEach((p) => {
    p.classList.toggle("hidden", p.dataset.panel !== key);
  });

  qsa("#nav a").forEach((a) => {
    a.classList.toggle("active", a.dataset.key === key);
  });
}

async function bootPanel(key) {
  const u = user();
  if (!u) return;
  const role = normalizeRole(u.role);

  if (role === "HR") {
    if (key === "hr_jobs") return hrJobs();
    if (key === "hr_candidates") return renderHrCandidates();
    if (key === "hr_tasks") return renderHrTasks();
    if (key === "hr_performance") return renderHrPerformance();
    if (key === "hr_analytics") return renderHrAnalytics();
    if (key === "notifications") return renderNotifications();
    return;
  }

  if (role === "Candidate") {
    if (key === "cand_jobs") return renderCandidateJobs();
    if (key === "cand_apps") return renderCandidateApps();
    if (key === "cand_resume") return candResume();
    if (key === "cand_interview") return candInterview();
    if (key === "notifications") return renderNotifications();
    return;
  }

  if (role === "Employee") {
    if (key === "emp_tasks") return renderEmployeeTasks();
    if (key === "emp_performance") return renderEmployeePerformance();
    if (key === "notifications") return renderNotifications();
  }
}

/* ================= HR JOBS ================= */

async function hrJobs() {
  const list = qs("#jobsList");
  if (!list) return;

  const searchInput = qs("#jobSearch");
  const q = (searchInput?.value || "").trim();
  const query = q ? `?q=${encodeURIComponent(q)}` : "";

  try {
    const data = await api(`/api/jobs${query}`);
    const jobs = data.jobs || [];

    list.innerHTML = jobs.length
      ? jobs.map((j) => `
        <div class="list-item">
          <div class="h">${escapeHtml(j.title)}</div>
          <div class="muted">${escapeHtml(j.description || "")}</div>
          <div class="meta">
            ${(j.skills || []).map((s) => `<span class="badge">${escapeHtml(s)}</span>`).join(" ")}
          </div>
        </div>
      `).join("")
      : `<div class="muted">No jobs found.</div>`;
  } catch (err) {
    list.innerHTML = `<div class="muted">${escapeHtml(err.message || "Failed to load jobs")}</div>`;
  }

  const refreshBtn = qs("#refreshJobs");
  if (refreshBtn && !refreshBtn.dataset.bound) {
    refreshBtn.dataset.bound = "1";
    refreshBtn.addEventListener("click", hrJobs);
  }

  if (searchInput && !searchInput.dataset.bound) {
    searchInput.dataset.bound = "1";
    searchInput.addEventListener("input", hrJobs);
  }

  const jobForm = qs("#jobForm");
  if (jobForm && !jobForm.dataset.bound) {
    jobForm.dataset.bound = "1";
    jobForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearAlert();

      const btn = jobForm.querySelector("button[type='submit']");
      const stop = withLoading(btn, "Publishing...");
      const fd = new FormData(jobForm);

      try {
        await api("/api/jobs", {
          method: "POST",
          body: {
            title: fd.get("title"),
            description: fd.get("description"),
            skills: fd.get("skills"),
          },
        });

        jobForm.reset();
        setAlert("Job published successfully", "ok");
        await hrJobs();
      } catch (err) {
        setAlert(err.message || "Failed to publish job");
      } finally {
        stop();
      }
    });
  }
}

/* ================= CANDIDATE JOBS ================= */

async function renderCandidateJobs() {
  const list = qs("#candJobsList");
  if (!list) return;

  const q = (qs("#candJobSearch")?.value || "").trim();
  const query = q ? `?q=${encodeURIComponent(q)}` : "";

  try {
    const data = await api(`/api/jobs${query}`);
    const jobs = data.jobs || [];

    list.innerHTML = jobs.length
      ? jobs.map((j) => `
        <div class="list-item">
          <div class="h">${escapeHtml(j.title)}</div>
          <div class="muted">${escapeHtml(j.description || "")}</div>
          <div class="meta">
            ${(j.skills || []).map((s) => `<span class="badge">${escapeHtml(s)}</span>`).join(" ")}
          </div>
          <div class="row wrap" style="margin-top:10px;">
            <button class="btn btn-primary" data-apply="${j.id}" type="button">Apply</button>
            <button class="btn btn-ghost" data-copy-job="${j.id}" type="button">Copy Job ID</button>
          </div>
        </div>
      `).join("")
      : `<div class="muted">No jobs found.</div>`;

    list.querySelectorAll("[data-apply]").forEach((btn) => {
      if (btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", async () => {
        try {
          await api("/api/applications", {
            method: "POST",
            body: { job_id: btn.dataset.apply },
          });
          setAlert("Applied successfully", "ok");
        } catch (err) {
          setAlert(err.message || "Failed to apply");
        }
      });
    });

    list.querySelectorAll("[data-copy-job]").forEach((btn) => {
      if (btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(btn.dataset.copyJob);
          setAlert("Job ID copied", "ok");
        } catch {
          setAlert("Could not copy Job ID");
        }
      });
    });
  } catch (err) {
    list.innerHTML = `<div class="muted">${escapeHtml(err.message || "Failed to load jobs")}</div>`;
  }

  const refreshBtn = qs("#candRefreshJobs");
  if (refreshBtn && refreshBtn.dataset.bound !== "1") {
    refreshBtn.dataset.bound = "1";
    refreshBtn.addEventListener("click", renderCandidateJobs);
  }

  const searchInput = qs("#candJobSearch");
  if (searchInput && searchInput.dataset.bound !== "1") {
    searchInput.dataset.bound = "1";
    searchInput.addEventListener("input", renderCandidateJobs);
  }
}

/* ================= CANDIDATE APPLICATIONS ================= */

async function renderCandidateApps() {
  const wrap = qs("#candAppsTable");
  if (!wrap) return;

  const status = qs("#candStatusFilter")?.value || "";
  const query = status ? `?status=${encodeURIComponent(status)}` : "";

  try {
    const data = await api(`/api/applications${query}`);
    const apps = data.applications || [];

    wrap.innerHTML = apps.length
      ? `
      <table>
        <thead>
          <tr>
            <th>Job</th>
            <th>Job ID</th>
            <th>Application ID</th>
            <th>Status</th>
            <th>Resume Score</th>
          </tr>
        </thead>
        <tbody>
          ${apps.map((a) => `
            <tr>
              <td>${escapeHtml(a.job?.title || "—")}</td>
              <td class="muted">${escapeHtml(a.job?.id || a.job_id || "—")}</td>
              <td class="muted">${escapeHtml(a.id || "—")}</td>
              <td>${recommendationBadge(a.status || "Pending")}</td>
              <td>${escapeHtml(a.resume_score ?? 0)}%</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
      `
      : `<div class="muted">No applications yet.</div>`;
  } catch (err) {
    wrap.innerHTML = `<div class="muted">${escapeHtml(err.message || "Failed to load applications")}</div>`;
  }

  const refreshBtn = qs("#candRefreshApps");
  if (refreshBtn && !refreshBtn.dataset.bound) {
    refreshBtn.dataset.bound = "1";
    refreshBtn.addEventListener("click", renderCandidateApps);
  }

  const statusFilter = qs("#candStatusFilter");
  if (statusFilter && !statusFilter.dataset.bound) {
    statusFilter.dataset.bound = "1";
    statusFilter.addEventListener("change", renderCandidateApps);
  }
}

/* ================= RESUME ================= */

async function candResume() {
  const form = qs("#resumeForm");
  if (!form || form.dataset.bound === "1") return;
  form.dataset.bound = "1";

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAlert();

    const btn = form.querySelector("button[type='submit']");
    const stopLoading = withLoading(btn, "Uploading...");
    const fd = new FormData(form);

    try {
      const data = await api("/api/resumes/upload", {
        method: "POST",
        body: fd,
      });

      const resume = data.resume || {};
      const strengths = resume.ai_strengths || [];
      const weaknesses = resume.ai_weaknesses || [];
      const skills = (resume.ai_extracted_skills || resume.extracted?.skills || []).slice(0, 10);
      const reco = resume.recommendation || data.recommendation || "";

      const resultEl = qs("#resumeResult");
      if (resultEl) {
        resultEl.innerHTML = `
          Score: <b>${escapeHtml(resume.score)}</b>% 
          • Skills: ${skills.map((s) => `<span class="badge">${escapeHtml(s)}</span>`).join(" ")} 
          • AI: ${recommendationBadge(reco)}
        `;
      }

      const aiCard = qs("#resumeAiCard");
      if (aiCard) {
        const strengthsHtml = strengths.length
          ? strengths.slice(0, 4).map((s) => `<span class="badge ok">${escapeHtml(s)}</span>`).join(" ")
          : "<span class='muted'>—</span>";

        const weaknessesHtml = weaknesses.length
          ? weaknesses.slice(0, 4).map((s) => `<span class="badge danger">${escapeHtml(s)}</span>`).join(" ")
          : "<span class='muted'>—</span>";

        const summary = resume.ai_summary || data.ai_summary || "";

        aiCard.classList.toggle("hidden", !summary && strengths.length === 0 && weaknesses.length === 0);
        aiCard.innerHTML = `
          <div class="ai-title">AI Resume Analysis</div>
          <div class="ai-muted">${summary ? escapeHtml(summary) : "No AI summary available."}</div>
          <div class="ai-muted" style="margin-top:10px;"><b>Strength Highlights:</b> ${strengthsHtml}</div>
          <div class="ai-muted"><b>Improvement Areas:</b> ${weaknessesHtml}</div>
        `;
      }

      setAlert("Resume uploaded successfully.", "ok");
    } catch (err) {
      setAlert(err.message || "Resume upload failed.", "error");
    } finally {
      stopLoading();
    }
  });
}

/* ================= INTERVIEW ================= */

function addMsg(who, text, me = false) {
  const chat = qs("#chat");
  if (!chat) return;

  const div = document.createElement("div");
  div.className = `msg ${me ? "me" : ""}`;
  div.innerHTML = `
    <div class="who">${escapeHtml(who)}</div>
    <div class="bubble">${escapeHtml(text)}</div>
  `;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function renderInterview() {
  const chat = qs("#chat");
  const meta = qs("#chatMeta");
  const finalCard = qs("#finalInterviewCard");

  if (!chat) return;

  chat.innerHTML = "";

  if (!currentInterview) {
    if (meta) meta.textContent = "";
    if (finalCard) {
      finalCard.classList.add("hidden");
      finalCard.innerHTML = "";
    }
    return;
  }

  const questions = currentInterview.questions || [];

  questions.forEach((q, i) => {
    addMsg(`Q${i + 1}`, q.q || "", false);

    if ((q.a || "").trim()) {
      addMsg("You", q.a, true);

      const feedbackBits = [];
      if (q.score != null) feedbackBits.push(`Score: ${q.score}%`);
      if (q.feedback) feedbackBits.push(q.feedback);

      if (feedbackBits.length) {
        addMsg("Interviewer", feedbackBits.join(" • "), false);
      }
    }
  });

  if (meta) {
    const bits = [];
    if (currentInterview.total_score != null) bits.push(`Current total score: ${currentInterview.total_score}%`);
    if (currentInterview.status === "Completed" && currentInterview.final_recommendation) {
      bits.push(`AI: ${currentInterview.final_recommendation}`);
    }
    meta.textContent = bits.join(" • ");
  }

  if (finalCard) {
    const finalSummary = currentInterview.final_summary || "";
    const finalReco = currentInterview.final_recommendation || "";

    if (finalSummary) {
      finalCard.classList.remove("hidden");
      finalCard.innerHTML = `
        <div class="ai-title">Final AI Interview Summary</div>
        <div class="ai-muted">Recommendation: ${recommendationBadge(finalReco)}</div>
        <div class="ai-muted" style="margin-top:8px;">${escapeHtml(finalSummary)}</div>
      `;
    } else {
      finalCard.classList.add("hidden");
      finalCard.innerHTML = "";
    }
  }
}

function candInterview() {
  const startForm = qs("#startInterviewForm");
  const chatForm = qs("#chatForm");
  const finishBtn = qs("#finishInterviewBtn");

  if (startForm && !startForm.dataset.bound) {
    startForm.dataset.bound = "1";

    startForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearAlert();

      const btn = startForm.querySelector("button[type='submit']");
      const stop = withLoading(btn, "Starting...");
      const fd = new FormData(startForm);

      try {
        const data = await api("/api/interviews/start", {
          method: "POST",
          body: { application_id: fd.get("application_id") },
        });

        currentInterview = data.interview;
        renderInterview();
        setAlert("Interview started successfully", "ok");
      } catch (err) {
        setAlert(err.message || "Failed to start interview");
      } finally {
        stop();
      }
    });
  }

  if (chatForm && !chatForm.dataset.bound) {
    chatForm.dataset.bound = "1";

    chatForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearAlert();

      if (!currentInterview) {
        setAlert("Start interview first");
        return;
      }

      const input = qs("#chatInput");
      if (!input) return;

      const answer = input.value.trim();
      if (!answer) return;

      const unansweredIdx = (currentInterview.questions || []).findIndex((q) => !(q.a || "").trim());
      if (unansweredIdx < 0) {
        setAlert("All questions answered. Click Finish interview.", "ok");
        return;
      }

      const btn = chatForm.querySelector("button[type='submit']");
      const stop = withLoading(btn, "Sending...");

      try {
        const data = await api("/api/interviews/answer", {
          method: "POST",
          body: {
            interview_id: currentInterview.id,
            index: unansweredIdx,
            answer,
          },
        });

        input.value = "";
        currentInterview = data.interview;
        renderInterview();
        setAlert("Answer submitted successfully", "ok");
      } catch (err) {
        setAlert(err.message || "Failed to submit answer");
      } finally {
        stop();
      }
    });
  }

  if (finishBtn && !finishBtn.dataset.bound) {
    finishBtn.dataset.bound = "1";

    finishBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      clearAlert();

      if (!currentInterview) {
        setAlert("Start interview first");
        return;
      }

      const hasUnanswered = (currentInterview.questions || []).some((q) => !(q.a || "").trim());
      if (hasUnanswered) {
        setAlert("Please answer all questions before finishing");
        return;
      }

      const stop = withLoading(finishBtn, "Finishing...");

      try {
        const data = await api("/api/interviews/finish", {
          method: "POST",
          body: { interview_id: currentInterview.id },
        });

        currentInterview = data.interview;
        renderInterview();
        setAlert("Interview completed successfully", "ok");
      } catch (err) {
        setAlert(err.message || "Failed to finish interview");
      } finally {
        stop();
      }
    });
  }
}

/* ================= NOTIFICATIONS ================= */

async function renderNotifications() {
  const list = qs("#notifList");
  if (!list) return;

  try {
    const data = await api("/api/notifications");
    const items = data.notifications || [];

    list.innerHTML = items.length
      ? items.map((n) => `
          <div class="list-item">
            <div class="h">${escapeHtml(n.title || "Notification")}</div>
            <div class="muted">${escapeHtml(n.message || "")}</div>
          </div>
        `).join("")
      : `<div class="muted">No notifications yet.</div>`;
  } catch (err) {
    list.innerHTML = `<div class="muted">${escapeHtml(err.message || "Failed to load notifications")}</div>`;
  }

  const refreshBtn = qs("#refreshNotifs");
  if (refreshBtn && !refreshBtn.dataset.bound) {
    refreshBtn.dataset.bound = "1";
    refreshBtn.addEventListener("click", renderNotifications);
  }
}

/* ================= HR CANDIDATES ================= */
/* ================= HR TASKS ================= */

async function renderHrTasks() {
  const wrap = qs("#tasksTable");
  if (!wrap) return;

  const status = qs("#taskStatusFilter")?.value || "";
  const params = new URLSearchParams();
  if (status) params.set("status", status);

  try {
    const [taskData, employeeData] = await Promise.all([
      api(`/api/tasks${params.toString() ? `?${params.toString()}` : ""}`),
      api("/api/users?role=Employee"),
    ]);

    const tasks = taskData.tasks || [];
    const employees = employeeData.users || [];

    const employeeSelect = qs("#employeeSelect");
    if (employeeSelect) {
      employeeSelect.innerHTML = employees.length
        ? employees.map((u) =>
            `<option value="${escapeHtml(u.id)}">${escapeHtml(u.name || u.email)} (${escapeHtml(u.email || "")})</option>`
          ).join("")
        : `<option value="">No employees found</option>`;
    }

    const perfEmployeeSelect = qs("#perfEmployeeSelect");
    if (perfEmployeeSelect) {
      perfEmployeeSelect.innerHTML = employees.length
        ? employees.map((u) =>
            `<option value="${escapeHtml(u.id)}">${escapeHtml(u.name || u.email)} (${escapeHtml(u.email || "")})</option>`
          ).join("")
        : `<option value="">No employees found</option>`;
    }

    wrap.innerHTML = tasks.length
      ? `
      <table>
        <thead>
          <tr>
            <th>Employee</th>
            <th>Title</th>
            <th>Status</th>
            <th>Feedback</th>
          </tr>
        </thead>
        <tbody>
          ${tasks.map((t) => `
            <tr>
              <td>
                <div><b>${escapeHtml(t.employee?.name || "—")}</b></div>
                <div class="muted">${escapeHtml(t.employee?.email || "")}</div>
              </td>
              <td>${escapeHtml(t.title || "—")}</td>
              <td>${recommendationBadge(t.status || "Pending")}</td>
              <td>${escapeHtml(t.hr_feedback || "—")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
      `
      : `<div class="muted">No tasks found.</div>`;
  } catch (err) {
    wrap.innerHTML = `<div class="muted">${escapeHtml(err.message || "Failed to load tasks")}</div>`;
  }

  const refreshBtn = qs("#refreshTasks");
  if (refreshBtn && refreshBtn.dataset.bound !== "1") {
    refreshBtn.dataset.bound = "1";
    refreshBtn.addEventListener("click", renderHrTasks);
  }

  const filter = qs("#taskStatusFilter");
  if (filter && filter.dataset.bound !== "1") {
    filter.dataset.bound = "1";
    filter.addEventListener("change", renderHrTasks);
  }

  const taskForm = qs("#taskForm");
  if (taskForm && taskForm.dataset.bound !== "1") {
    taskForm.dataset.bound = "1";
    taskForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearAlert();

      const btn = taskForm.querySelector("button[type='submit']");
      const stop = withLoading(btn, "Assigning...");
      const fd = new FormData(taskForm);

      try {
        await api("/api/tasks", {
          method: "POST",
          body: {
            employee_id: fd.get("employee_id"),
            title: fd.get("title"),
            description: fd.get("description"),
          },
        });

        taskForm.reset();
        setAlert("Task assigned successfully.", "ok");
        await renderHrTasks();
      } catch (err) {
        setAlert(err.message || "Failed to assign task");
      } finally {
        stop();
      }
    });
  }

  const perfForm = qs("#perfForm");
  if (perfForm && perfForm.dataset.bound !== "1") {
    perfForm.dataset.bound = "1";
    perfForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearAlert();

      const btn = perfForm.querySelector("button[type='submit']");
      const stop = withLoading(btn, "Updating...");
      const fd = new FormData(perfForm);

      try {
        await api("/api/performance/update", {
          method: "POST",
          body: {
            employee_id: fd.get("employee_id"),
            hr_rating: Number(fd.get("hr_rating")),
            feedback: fd.get("feedback"),
          },
        });

        setAlert("Performance updated successfully.", "ok");
        await renderHrPerformance();
        await renderHrAnalytics();
      } catch (err) {
        setAlert(err.message || "Failed to update performance");
      } finally {
        stop();
      }
    });
  }
}

/* ================= CHART HELPERS ================= */

function destroyChartInstance(instance) {
  try {
    if (instance && typeof instance.destroy === "function") {
      instance.destroy();
    }
  } catch {}
}

function resetCanvas(containerSelector, canvasId, height = 140) {
  const oldCanvas = qs(`#${canvasId}`);
  if (!oldCanvas) return null;

  const parent = oldCanvas.parentElement;
  if (!parent) return oldCanvas;

  const newCanvas = document.createElement("canvas");
  newCanvas.id = canvasId;
  newCanvas.height = height;
  parent.replaceChild(newCanvas, oldCanvas);
  return newCanvas;
}

/* ================= HR PERFORMANCE ================= */

async function renderHrPerformance() {
  if (!window.Chart) return;

  try {
    if (hrecPerfChartInstance) {
      hrecPerfChartInstance.destroy();
      hrecPerfChartInstance = null;
    }

    const canvas = document.getElementById("perfChart");
    if (!canvas) return;

    const data = await api("/api/performance");
    const rows = data.performance || [];

    const labels = rows.map((r, i) => {
      if (r.employee && r.employee.name) return r.employee.name;
      return `Employee ${i + 1}`;
    });

    const scores = rows.map((r) => Number(r.score || 0));

    const ctx = canvas.getContext("2d");

    const gradients = scores.map((_, i) => {
      const g = ctx.createLinearGradient(0, 0, 0, 320);

      const palette = [
        ["#8b5cf6", "#6366f1"],
        ["#22c55e", "#16a34a"],
        ["#f59e0b", "#ef4444"],
        ["#38bdf8", "#2563eb"],
        ["#ec4899", "#db2777"],
        ["#14b8a6", "#0f766e"],
        ["#f97316", "#ea580c"],
        ["#a855f7", "#7e22ce"]
      ];

      const pair = palette[i % palette.length];
      g.addColorStop(0, pair[0]);
      g.addColorStop(1, pair[1]);
      return g;
    });

    const depthColors = scores.map((_, i) => {
      const palette = [
        "rgba(76, 29, 149, 0.65)",
        "rgba(21, 128, 61, 0.65)",
        "rgba(180, 83, 9, 0.65)",
        "rgba(30, 64, 175, 0.65)",
        "rgba(157, 23, 77, 0.65)",
        "rgba(15, 118, 110, 0.65)",
        "rgba(154, 52, 18, 0.65)",
        "rgba(107, 33, 168, 0.65)"
      ];
      return palette[i % palette.length];
    });

    hrecPerfChartInstance = new Chart(canvas, {
      type: "doughnut",
      data: {
        labels,
        datasets: [
          {
            label: "Performance Score",
            data: scores,
            backgroundColor: gradients,
            borderColor: "rgba(255,255,255,0.18)",
            borderWidth: 2,
            hoverOffset: 18,
            spacing: 4
          },
          {
            // fake depth / 3D shadow ring
            label: "Depth",
            data: scores,
            backgroundColor: depthColors,
            borderWidth: 0,
            hoverOffset: 0,
            spacing: 4,
            weight: 0.35
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "50%",
        rotation: -90,
        animation: {
          animateRotate: true,
          animateScale: true,
          duration: 1600,
          easing: "easeOutQuart"
        },
        plugins: {
          legend: {
            display: true,
            position: "right",
            labels: {
              color: "#cbd5e1",
              padding: 18,
              usePointStyle: true,
              pointStyle: "circle",
              font: {
                size: 12,
                weight: "600"
              }
            }
          },
          tooltip: {
            backgroundColor: "#0f172a",
            titleColor: "#ffffff",
            bodyColor: "#e2e8f0",
            borderColor: "#334155",
            borderWidth: 1,
            padding: 12,
            callbacks: {
              label: function(context) {
                return `${context.label}: ${context.raw}%`;
              }
            }
          }
        }
      },
      plugins: [
        {
          id: "hrecCenterText",
          afterDraw(chart) {
            const meta = chart.getDatasetMeta(0);
            if (!meta?.data?.length) return;

            const total = scores.length
              ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
              : 0;

            const x = meta.data[0].x;
            const y = meta.data[0].y;
            const c = chart.ctx;

            c.save();
            c.textAlign = "center";
            c.textBaseline = "middle";

            c.font = "700 28px Inter, sans-serif";
            c.fillStyle = "#ffffff";
            c.fillText(`${total}%`, x, y - 8);

            c.font = "500 13px Inter, sans-serif";
            c.fillStyle = "#94a3b8";
            c.fillText("Avg Performance", x, y + 18);

            c.restore();
          }
        }
      ]
    });
  } catch (err) {
    console.error("Failed to load HR performance:", err);
  }

  const refreshPerfBtn = qs("#refreshPerf");
  if (refreshPerfBtn && refreshPerfBtn.dataset.bound !== "1") {
    refreshPerfBtn.dataset.bound = "1";
    refreshPerfBtn.addEventListener("click", renderHrPerformance);
  }
}

/* ================= HR ANALYTICS ================= */

async function renderHrAnalytics() {
  if (!window.Chart) return;

  try {
    if (hrecFunnelChartInstance) {
      hrecFunnelChartInstance.destroy();
      hrecFunnelChartInstance = null;
    }

    if (hrecPerfSeriesChartInstance) {
      hrecPerfSeriesChartInstance.destroy();
      hrecPerfSeriesChartInstance = null;
    }

    const funnelCanvas = document.getElementById("funnelChart");
    const perfCanvas = document.getElementById("perfSeriesChart");

    if (!funnelCanvas || !perfCanvas) return;

    const funnel = await api("/api/analytics/hiring-funnel");
    const perf = await api("/api/performance");

    const funnelData = funnel.funnel || {};
    const perfRows = perf.performance || [];

    /* ================= FUNNEL 3D DOUGHNUT ================= */
    const funnelCtx = funnelCanvas.getContext("2d");

    const funnelGradients = [
      funnelCtx.createLinearGradient(0, 0, 0, 300),
      funnelCtx.createLinearGradient(0, 0, 0, 300),
      funnelCtx.createLinearGradient(0, 0, 0, 300)
    ];

    funnelGradients[0].addColorStop(0, "#8b5cf6");
    funnelGradients[0].addColorStop(1, "#6366f1");

    funnelGradients[1].addColorStop(0, "#22c55e");
    funnelGradients[1].addColorStop(1, "#16a34a");

    funnelGradients[2].addColorStop(0, "#f59e0b");
    funnelGradients[2].addColorStop(1, "#ef4444");

    const funnelDepthColors = [
      "rgba(76,29,149,0.60)",
      "rgba(21,128,61,0.60)",
      "rgba(180,83,9,0.60)"
    ];

    const funnelLabels = Object.keys(funnelData);
    const funnelValues = Object.values(funnelData).map((v) => Number(v || 0));

    hrecFunnelChartInstance = new Chart(funnelCanvas, {
      type: "doughnut",
      data: {
        labels: funnelLabels,
        datasets: [
          {
            label: "Applications",
            data: funnelValues,
            backgroundColor: funnelGradients,
            borderColor: "rgba(255,255,255,0.18)",
            borderWidth: 2,
            hoverOffset: 16,
            spacing: 4
          },
          {
            label: "Depth",
            data: funnelValues,
            backgroundColor: funnelDepthColors,
            borderWidth: 0,
            hoverOffset: 0,
            spacing: 4,
            weight: 0.35
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "54%",
        rotation: -90,
        animation: {
          animateRotate: true,
          animateScale: true,
          duration: 1600,
          easing: "easeOutQuart"
        },
        plugins: {
          legend: {
            display: true,
            position: "bottom",
            labels: {
              color: "#cbd5e1",
              padding: 18,
              usePointStyle: true,
              pointStyle: "circle",
              font: {
                size: 12,
                weight: "600"
              }
            }
          },
          tooltip: {
            backgroundColor: "#0f172a",
            titleColor: "#ffffff",
            bodyColor: "#e2e8f0",
            borderColor: "#334155",
            borderWidth: 1,
            padding: 12
          }
        }
      },
      plugins: [
        {
          id: "funnelCenterText",
          afterDraw(chart) {
            const meta = chart.getDatasetMeta(0);
            if (!meta?.data?.length) return;

            const total = funnelValues.reduce((a, b) => a + b, 0);
            const x = meta.data[0].x;
            const y = meta.data[0].y;
            const c = chart.ctx;

            c.save();
            c.textAlign = "center";
            c.textBaseline = "middle";

            c.font = "700 26px Inter, sans-serif";
            c.fillStyle = "#ffffff";
            c.fillText(`${total}`, x, y - 8);

            c.font = "500 13px Inter, sans-serif";
            c.fillStyle = "#94a3b8";
            c.fillText("Total Applications", x, y + 18);

            c.restore();
          }
        }
      ]
    });

    /* ================= PREMIUM BAR CHART ================= */
    const perfCtx = perfCanvas.getContext("2d");

    const perfGradient = perfCtx.createLinearGradient(0, 0, 0, 320);
    perfGradient.addColorStop(0, "rgba(139,92,246,0.95)");
    perfGradient.addColorStop(1, "rgba(59,130,246,0.75)");

    const perfBorderGradient = perfCtx.createLinearGradient(0, 0, 0, 320);
    perfBorderGradient.addColorStop(0, "#c4b5fd");
    perfBorderGradient.addColorStop(1, "#60a5fa");

    hrecPerfSeriesChartInstance = new Chart(perfCanvas, {
      type: "bar",
      data: {
        labels: perfRows.map((r, i) => {
          if (r.employee && r.employee.name) return r.employee.name;
          return `Employee ${i + 1}`;
        }),
        datasets: [
          {
            label: "Performance Score",
            data: perfRows.map((r) => Number(r.score || 0)),
            backgroundColor: perfGradient,
            borderColor: perfBorderGradient,
            borderWidth: 2,
            borderRadius: 14,
            borderSkipped: false,
            hoverBackgroundColor: "rgba(99,102,241,0.95)",
            maxBarThickness: 48
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: 1500,
          easing: "easeOutQuart"
        },
        plugins: {
          legend: {
            display: true,
            labels: {
              color: "#cbd5e1",
              font: {
                size: 12,
                weight: "600"
              }
            }
          },
          tooltip: {
            backgroundColor: "#0f172a",
            titleColor: "#ffffff",
            bodyColor: "#e2e8f0",
            borderColor: "#334155",
            borderWidth: 1,
            padding: 12,
            callbacks: {
              label: function(context) {
                return `${context.raw}%`;
              }
            }
          }
        },
        scales: {
          x: {
            ticks: {
              color: "#cbd5e1",
              font: {
                size: 11,
                weight: "600"
              }
            },
            grid: {
              display: false
            }
          },
          y: {
            beginAtZero: true,
            max: 100,
            ticks: {
              color: "#94a3b8",
              callback: (value) => `${value}%`
            },
            grid: {
              color: "rgba(148,163,184,0.12)"
            }
          }
        }
      },
      plugins: [
        {
          id: "barShadow",
          beforeDatasetsDraw(chart) {
            const { ctx } = chart;
            ctx.save();
            ctx.shadowColor = "rgba(99,102,241,0.35)";
            ctx.shadowBlur = 18;
            ctx.shadowOffsetY = 10;
          },
          afterDatasetsDraw(chart) {
            chart.ctx.restore();
          }
        }
      ]
    });
  } catch (err) {
    console.error("Analytics load failed:", err);
  }

  const refreshAnalyticsBtn = qs("#refreshAnalytics");
  if (refreshAnalyticsBtn && refreshAnalyticsBtn.dataset.bound !== "1") {
    refreshAnalyticsBtn.dataset.bound = "1";
    refreshAnalyticsBtn.addEventListener("click", renderHrAnalytics);
  }
}

/* ================= EMPLOYEE PERFORMANCE ================= */

async function renderEmployeePerformance() {
  const wrap = qs("#empPerfCard");
  const chartCanvas = qs("#empPerfChart");
  if (!wrap) return;

  try {
    const data = await api("/api/performance");
    const rows = data.performance || [];

    if (!rows.length) {
      wrap.innerHTML = `<div class="muted">No performance data found.</div>`;
      if (hrecEmpPerfChartInstance) {
        hrecEmpPerfChartInstance.destroy();
        hrecEmpPerfChartInstance = null;
      }
      return;
    }

    const r = rows[0];

    const score = Number(r.score ?? 0);
    const hrRating = Number(r.hr_rating ?? 0);
    const completed = Number(r.tasks_completed ?? 0);
    const pending = Number(r.tasks_pending ?? 0);
    const feedback = r.feedback || "No feedback given yet.";

    wrap.innerHTML = `
      <div class="kpi">
        <div class="k">Score</div>
        <div class="v">${escapeHtml(score)}</div>
      </div>

      <div class="kpi">
        <div class="k">HR Rating</div>
        <div class="v">${escapeHtml(hrRating)}</div>
      </div>

      <div class="kpi">
        <div class="k">Tasks Completed</div>
        <div class="v">${escapeHtml(completed)}</div>
      </div>

      <div class="kpi">
        <div class="k">Tasks Pending</div>
        <div class="v">${escapeHtml(pending)}</div>
      </div>

      <div class="kpi" style="grid-column: 1 / -1;">
        <div class="k">HR Feedback</div>
        <div class="v" style="font-size:16px; font-weight:600; margin-top:8px;">
          ${escapeHtml(feedback)}
        </div>
      </div>
    `;

    if (chartCanvas && window.Chart) {
      if (hrecEmpPerfChartInstance) {
        hrecEmpPerfChartInstance.destroy();
        hrecEmpPerfChartInstance = null;
      }

      const ctx = chartCanvas.getContext("2d");

      const barGradient = ctx.createLinearGradient(0, 0, 0, 320);
      barGradient.addColorStop(0, "rgba(56, 189, 248, 0.95)");
      barGradient.addColorStop(1, "rgba(37, 99, 235, 0.75)");

      hrecEmpPerfChartInstance = new Chart(chartCanvas, {
        type: "bar",
        data: {
          labels: ["Score", "HR Rating", "Tasks Completed", "Tasks Pending"],
          datasets: [
            {
              label: "My Performance",
              data: [score, hrRating, completed, pending],
              backgroundColor: [
                "rgba(139,92,246,0.85)",
                "rgba(59,130,246,0.85)",
                "rgba(34,197,94,0.85)",
                "rgba(245,158,11,0.85)"
              ],
              borderColor: [
                "#8b5cf6",
                "#3b82f6",
                "#22c55e",
                "#f59e0b"
              ],
              borderWidth: 2,
              borderRadius: 14,
              borderSkipped: false,
              maxBarThickness: 58
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: {
            duration: 1400,
            easing: "easeOutQuart"
          },
          plugins: {
            legend: {
              display: false
            },
            tooltip: {
              backgroundColor: "#0f172a",
              titleColor: "#ffffff",
              bodyColor: "#e2e8f0",
              borderColor: "#334155",
              borderWidth: 1,
              padding: 12
            }
          },
          scales: {
            x: {
              ticks: {
                color: "#cbd5e1",
                font: {
                  size: 12,
                  weight: "600"
                }
              },
              grid: {
                display: false
              }
            },
            y: {
              beginAtZero: true,
              max: 100,
              ticks: {
                color: "#94a3b8"
              },
              grid: {
                color: "rgba(148,163,184,0.12)"
              }
            }
          }
        },
        plugins: [
          {
            id: "empBarShadow",
            beforeDatasetsDraw(chart) {
              const { ctx } = chart;
              ctx.save();
              ctx.shadowColor = "rgba(59,130,246,0.25)";
              ctx.shadowBlur = 16;
              ctx.shadowOffsetY = 8;
            },
            afterDatasetsDraw(chart) {
              chart.ctx.restore();
            }
          }
        ]
      });
    }
  } catch (err) {
    wrap.innerHTML = `<div class="muted">${escapeHtml(err.message || "Failed to load employee performance")}</div>`;
  }

  const refreshBtn = qs("#refreshEmpPerf");
  if (refreshBtn && refreshBtn.dataset.bound !== "1") {
    refreshBtn.dataset.bound = "1";
    refreshBtn.addEventListener("click", renderEmployeePerformance);
  }
}

/* ================= DASHBOARD INIT ================= */

async function initDashboard() {
  initThemeToggle();
  parseAuthFromUrl();

  if (!token()) {
    console.error("No token found → redirecting to login");
    location.href = "index.html";
    return;
  }

  const u = user();
  if (!u) {
    clearSession();
    location.href = "index.html";
    return;
  }

  u.role = normalizeRole(u.role || "Candidate");
  localStorage.setItem("hrec_user", JSON.stringify(u));

  const rolePill = qs("#rolePill");
  if (rolePill) rolePill.textContent = u.role;

  const userChip = qs("#userChip");
  if (userChip) userChip.textContent = u.email || "";

  const greetingText = qs("#greetingText");
  if (greetingText) {
    const firstName = (u.name || "User").split(" ")[0];
    const hour = new Date().getHours();
    let greet = "Hello";
    if (hour < 12) greet = "Good Morning";
    else if (hour < 18) greet = "Good Afternoon";
    else greet = "Good Evening";
    greetingText.textContent = `${greet}, ${firstName} 👋`;
  }

  const profileName = qs("#profileName");
  if (profileName) profileName.textContent = u.name || u.email || "User";

  const profileRole = qs("#profileRole");
  if (profileRole) profileRole.textContent = u.role;

  const profileDropdownName = qs("#profileDropdownName");
  if (profileDropdownName) profileDropdownName.textContent = u.name || u.email || "User";

  const profileDropdownEmail = qs("#profileDropdownEmail");
  if (profileDropdownEmail) profileDropdownEmail.textContent = u.email || "";

  const profileAvatar = qs("#profileAvatar");
  if (profileAvatar) {
    const initials = (u.name || u.email || "U")
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((x) => x[0].toUpperCase())
      .join("") || "U";
    profileAvatar.textContent = initials;
  }

  const nav = qs("#nav");
  if (nav) {
    const role = normalizeRole(u.role);
    nav.innerHTML = (NAV_BY_ROLE[role] || NAV_BY_ROLE["Candidate"])
      .map((item) => `<a href="#" data-key="${item.key}">${escapeHtml(item.label)}</a>`)
      .join("");

    if (!nav.dataset.bound) {
      nav.dataset.bound = "1";
      nav.addEventListener("click", async (e) => {
        const a = e.target.closest("a");
        if (!a) return;
        e.preventDefault();

        const key = a.dataset.key;
        showPanel(key);
        await bootPanel(key);
      });
    }

    const firstKey = (NAV_BY_ROLE[role] || NAV_BY_ROLE["Candidate"])[0]?.key;
    if (firstKey) {
      showPanel(firstKey);
      await bootPanel(firstKey);
    }
  }

  const logoutBtn = qs("#logoutBtn");
  if (logoutBtn && !logoutBtn.dataset.bound) {
    logoutBtn.dataset.bound = "1";
    logoutBtn.addEventListener("click", () => {
      clearSession();
      location.href = "index.html";
    });
  }

  const profileLogoutBtn = qs("#profileLogoutBtn");
  if (profileLogoutBtn && !profileLogoutBtn.dataset.bound) {
    profileLogoutBtn.dataset.bound = "1";
    profileLogoutBtn.addEventListener("click", () => {
      clearSession();
      location.href = "index.html";
    });
  }

  const profileMini = qs("#profileMini");
  const profileDropdown = qs("#profileDropdown");
  if (profileMini && profileDropdown && !profileMini.dataset.bound) {
    profileMini.dataset.bound = "1";

    profileMini.addEventListener("click", (e) => {
      e.stopPropagation();
      profileDropdown.classList.toggle("hidden");
    });

    document.addEventListener("click", () => {
      profileDropdown.classList.add("hidden");
    });

    profileDropdown.addEventListener("click", (e) => {
      e.stopPropagation();
    });
  }
}

/* ================= HR CANDIDATE MODAL ================= */

/* ================= HR CANDIDATES ================= */

async function renderHrCandidates() {
  const wrap = qs("#appsTable");
  if (!wrap) return;

  const status = qs("#statusFilter")?.value || "";
  const skill = (qs("#skillFilter")?.value || "").trim();
  const minScore = (qs("#minScore")?.value || "").trim();
  const jobId = (qs("#candSearch")?.value || "").trim();

  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (skill) params.set("skill", skill);
  if (minScore) params.set("min_score", minScore);
  if (jobId) params.set("job_id", jobId);

  try {
    const data = await api(`/api/applications${params.toString() ? `?${params.toString()}` : ""}`);
    const apps = data.applications || [];
    window._hrApps = apps;

    wrap.innerHTML = apps.length
      ? `
      <table>
        <thead>
          <tr>
            <th>Candidate</th>
            <th>Job</th>
            <th>Status</th>
            <th>Resume</th>
            <th>Interview</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          ${apps.map((a, i) => `
            <tr>
              <td>
                <b>${escapeHtml(a.candidate?.name || "—")}</b><br/>
                <span class="muted">${escapeHtml(a.candidate?.email || "")}</span>
              </td>
              <td>${escapeHtml(a.job?.title || "—")}</td>
              <td>${recommendationBadge(a.status || "Pending")}</td>
              <td>${escapeHtml(a.resume_score ?? 0)}%</td>
              <td>${escapeHtml(a.interview?.score ?? "—")}</td>
              <td>
                <button class="btn btn-primary hr-view-details-btn" type="button" data-index="${i}">
                  View Details
                </button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
      `
      : `<div class="muted">No data</div>`;
  } catch (err) {
    wrap.innerHTML = `<div class="muted">${escapeHtml(err.message || "Failed to load applications")}</div>`;
  }

  ["#refreshApps", "#statusFilter", "#skillFilter", "#minScore", "#candSearch"].forEach((sel) => {
    const el = qs(sel);
    if (!el || el.dataset.bound === "1") return;
    el.dataset.bound = "1";
    const ev = sel === "#refreshApps" ? "click" : "change";
    el.addEventListener(ev, renderHrCandidates);
    if (sel === "#skillFilter" || sel === "#candSearch") {
      el.addEventListener("input", renderHrCandidates);
    }
  });
}

function openCandidateDetailModal(app) {
  if (!app) return;

  selectedCandidateApplication = app;

  const modal = document.getElementById("candidateDetailModal");
  if (!modal) return;

  const cand = app.candidate || {};
  const job = app.job || {};
  const interview = app.interview || {};

  const setText = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value ?? "—";
  };

  const setHtml = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = value ?? "—";
  };

  setText("candidateDetailTitle", "Candidate Details");
  setText("candidateDetailSubtitle", "Review application, AI analysis, and interview results.");
  setText("detailCandidateName", cand.name || "—");
  setText("detailCandidateEmail", cand.email || "—");
  setText("detailJobTitle", job.title || "—");
  setHtml("detailStatus", recommendationBadge(app.status || "Pending"));
  setText("detailResumeScore", `${app.resume_score ?? 0}%`);
  setText("detailInterviewScore", interview.score != null ? `${interview.score}%` : "—");

  setHtml("detailResumeRecommendation", recommendationBadge(app.resume_recommendation || ""));
  setText("detailResumeSummary", app.resume_ai_summary || "No AI resume summary available.");
  setHtml("detailResumeStrengths", renderBadgeList(app.resume_ai_strengths || [], "ok"));
  setHtml("detailResumeWeaknesses", renderBadgeList(app.resume_ai_weaknesses || [], "danger"));

  setHtml("detailInterviewRecommendation", recommendationBadge(interview.final_recommendation || ""));
  setText("detailInterviewSummary", interview.final_summary || "No AI interview summary available.");

  const finalScore = Math.round(((app.resume_score || 0) + (interview.score || 0)) / 2);
  let decision = "Review";
  if (finalScore >= 75) decision = "Accept";
  else if (finalScore < 50) decision = "Reject";

  setText("detailFinalScore", `${finalScore}%`);
  setText("detailFinalDecision", decision);

  modal.classList.remove("hidden");
  modal.style.display = "block";
  modal.style.pointerEvents = "auto";
  modal.style.opacity = "1";
  modal.style.visibility = "visible";
  const shell = modal.querySelector(".candidate-detail-shell");
if (shell) {
  shell.style.opacity = "1";
  shell.style.filter = "none";
  shell.style.backdropFilter = "none";
  shell.style.transform = "none";
  shell.style.visibility = "visible";
}
  document.body.style.overflow = "hidden";
}

function closeCandidateDetailModal() {
  const modal = document.getElementById("candidateDetailModal");
  if (!modal) return;
  modal.classList.add("hidden");
  modal.style.display = "none";
  modal.style.pointerEvents = "none";
  modal.style.opacity = "0";
  modal.style.visibility = "hidden";
  document.body.style.overflow = "";
}

function openScheduleModal() {
  const modal = document.getElementById("scheduleModal");
  if (!modal) return;

  modal.classList.remove("hidden");
  modal.style.display = "block";
  document.body.style.overflow = "hidden";
}

function closeScheduleModal() {
  const modal = document.getElementById("scheduleModal");
  if (!modal) return;

  modal.classList.add("hidden");
  modal.style.display = "none";
  document.body.style.overflow = "";

  const input = qs("#scheduleInterviewDateTime");
  const note = qs("#scheduleInterviewNote");

  if (input) input.value = "";
  if (note) note.value = "";
}
/* ================= BOOT ================= */

document.addEventListener("DOMContentLoaded", () => {
  const page = location.pathname.split("/").pop();

  if (page === "" || page === "index.html") {
    initAuthPage();
  } else if (page === "dashboard.html") {
    initDashboard();
  }

  const modal = document.getElementById("candidateDetailModal");
  const shell = modal?.querySelector(".candidate-detail-shell");
  const appsTable = document.getElementById("appsTable");

  qs("#candidateDetailClose")?.addEventListener("click", closeCandidateDetailModal);

  appsTable?.addEventListener("click", (e) => {
    const btn = e.target.closest(".hr-view-details-btn");
    if (!btn) return;

    const index = Number(btn.dataset.index);
    const app = (window._hrApps || [])[index];
    if (!app) {
      console.error("No application found for clicked row index:", index);
      return;
    }

    openCandidateDetailModal(app);
  });

  qs("#detailAcceptBtn")?.addEventListener("click", async () => {
    if (!selectedCandidateApplication) return;
    try {
      await api(`/api/applications/${selectedCandidateApplication.id}/status`, {
        method: "PATCH",
        body: { status: "Accepted" },
      });
      setAlert("Candidate accepted.", "ok");
      closeCandidateDetailModal();
      await renderHrCandidates();
    } catch (err) {
      setAlert(err.message || "Failed to accept candidate");
    }
  });

  qs("#detailRejectBtn")?.addEventListener("click", async () => {
    if (!selectedCandidateApplication) return;
    try {
      await api(`/api/applications/${selectedCandidateApplication.id}/status`, {
        method: "PATCH",
        body: { status: "Rejected" },
      });
      setAlert("Candidate rejected.", "ok");
      closeCandidateDetailModal();
      await renderHrCandidates();
    } catch (err) {
      setAlert(err.message || "Failed to reject candidate");
    }
  });

  qs("#detailPendingBtn")?.addEventListener("click", async () => {
    if (!selectedCandidateApplication) return;
    try {
      await api(`/api/applications/${selectedCandidateApplication.id}/status`, {
        method: "PATCH",
        body: { status: "Pending" },
      });
      setAlert("Candidate set to pending.", "ok");
      closeCandidateDetailModal();
      await renderHrCandidates();
    } catch (err) {
      setAlert(err.message || "Failed to update candidate");
    }
  });

  qs("#detailScheduleBtn")?.addEventListener("click", () => {
    if (!selectedCandidateApplication) return;
    openScheduleModal();
  });
  
  qs("#scheduleModalClose")?.addEventListener("click", closeScheduleModal);
  qs("#scheduleModalCancel")?.addEventListener("click", closeScheduleModal);
  
  qs("#scheduleModalSave")?.addEventListener("click", async () => {
    if (!selectedCandidateApplication) return;
  
    const scheduledAt = qs("#scheduleInterviewDateTime")?.value || "";
    const note = qs("#scheduleInterviewNote")?.value || "";
  
    if (!scheduledAt) {
      setAlert("Please select interview date and time");
      return;
    }
  
    try {
      await api(`/api/applications/${selectedCandidateApplication.id}/schedule`, {
        method: "POST",
        body: {
          scheduled_at: scheduledAt,
          note: note
        },
      });
  
      setAlert("Interview scheduled.", "ok");
      closeScheduleModal();
      closeCandidateDetailModal();
      await renderHrCandidates();
    } catch (err) {
      setAlert(err.message || "Failed to schedule interview");
    }
  
  });

  modal?.addEventListener("click", (e) => {
    if (e.target === modal) closeCandidateDetailModal();
  });

  shell?.addEventListener("click", (e) => {
    e.stopPropagation();
  });

  const scheduleModal = document.getElementById("scheduleModal");
const scheduleShell = scheduleModal?.querySelector(".candidate-detail-shell");

scheduleModal?.addEventListener("click", (e) => {
  if (e.target === scheduleModal) closeScheduleModal();
});

scheduleShell?.addEventListener("click", (e) => {
  e.stopPropagation();
});
});