/* ── SmartMind AI – Frontend Logic ── */

const EMOTION_META = {
  happy:      { icon: "😊", label: "Happy" },
  stress:     { icon: "😓", label: "Stress" },
  sad:        { icon: "😢", label: "Sad" },
  productive: { icon: "🚀", label: "Productive" },
  neutral:    { icon: "😐", label: "Neutral" },
};

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  setDefaultDates();
  setupNav();
  setupDarkMode();
  setupAddMemory();
  setupVoice();
  setupSearch();
  setupSummary();
  loadReminders();
  loadAllMemories();
});

function setDefaultDates() {
  const today = new Date().toISOString().split("T")[0];
  const now   = new Date().toTimeString().slice(0, 5);
  document.getElementById("memDate").value    = today;
  document.getElementById("memTime").value    = now;
  document.getElementById("summaryDate").value = today;
}

// ── Navigation ────────────────────────────────────────────────────────────────
function setupNav() {
  document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".section").forEach(s => s.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`sec-${btn.dataset.section}`).classList.add("active");

      if (btn.dataset.section === "reminders") loadReminders();
      if (btn.dataset.section === "all")       loadAllMemories();
    });
  });
}

// ── Dark Mode ─────────────────────────────────────────────────────────────────
function setupDarkMode() {
  const btn = document.getElementById("darkToggle");
  if (localStorage.getItem("dark") === "1") {
    document.body.classList.add("dark");
    btn.textContent = "☀️";
  }
  btn.addEventListener("click", () => {
    document.body.classList.toggle("dark");
    const isDark = document.body.classList.contains("dark");
    btn.textContent = isDark ? "☀️" : "🌙";
    localStorage.setItem("dark", isDark ? "1" : "0");
  });
}

// ── Add Memory ────────────────────────────────────────────────────────────────
function setupAddMemory() {
  document.getElementById("btnSave").addEventListener("click", saveMemory);
  document.getElementById("memText").addEventListener("keydown", e => {
    if (e.ctrlKey && e.key === "Enter") saveMemory();
  });
}

async function saveMemory() {
  const text   = document.getElementById("memText").value.trim();
  const date   = document.getElementById("memDate").value;
  const time   = document.getElementById("memTime").value;
  const person = document.getElementById("memPerson").value.trim();
  const result = document.getElementById("addResult");

  if (!text) { showResult(result, "error", "Please enter some text."); return; }

  try {
    const res = await fetch("/api/memories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, date, time, person }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error);

    const em = EMOTION_META[data.emotion] || EMOTION_META.neutral;
    showResult(result, "success",
      `✅ Memory saved! Detected emotion: ${em.icon} ${em.label}` +
      (data.person ? ` · Person: ${data.person}` : "")
    );
    document.getElementById("memText").value   = "";
    document.getElementById("memPerson").value = "";
    setDefaultDates();
  } catch (err) {
    showResult(result, "error", "❌ Failed to save: " + err.message);
  }
}

// ── Voice Input ───────────────────────────────────────────────────────────────
function setupVoice() {
  const btn    = document.getElementById("btnVoice");
  const status = document.getElementById("voiceStatus");

  if (!("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) {
    btn.title = "Voice input not supported in this browser";
    btn.disabled = true;
    return;
  }

  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognition = new SR();
  recognition.lang = "en-US";
  recognition.interimResults = false;

  let recording = false;

  btn.addEventListener("click", () => {
    if (recording) { recognition.stop(); return; }
    recognition.start();
  });

  recognition.onstart = () => {
    recording = true;
    btn.classList.add("recording");
    btn.textContent = "⏹ Stop";
    status.classList.remove("hidden");
  };

  recognition.onresult = e => {
    const transcript = e.results[0][0].transcript;
    document.getElementById("memText").value = transcript;
  };

  recognition.onend = () => {
    recording = false;
    btn.classList.remove("recording");
    btn.textContent = "🎤 Voice Input";
    status.classList.add("hidden");
  };

  recognition.onerror = e => {
    status.textContent = "⚠️ Voice error: " + e.error;
    setTimeout(() => status.classList.add("hidden"), 3000);
  };
}

// ── Search ────────────────────────────────────────────────────────────────────
function setupSearch() {
  document.getElementById("btnSearch").addEventListener("click", doSearch);
  document.getElementById("searchInput").addEventListener("keydown", e => {
    if (e.key === "Enter") doSearch();
  });
  document.getElementById("btnClearFilters").addEventListener("click", () => {
    document.getElementById("filterEmotion").value = "";
    document.getElementById("filterDate").value    = "";
    document.getElementById("searchInput").value   = "";
    document.getElementById("searchResults").innerHTML = "";
  });
}

async function doSearch() {
  const q       = document.getElementById("searchInput").value.trim();
  const emotion = document.getElementById("filterEmotion").value;
  const date    = document.getElementById("filterDate").value;
  const container = document.getElementById("searchResults");

  // Build query string
  let query = q;
  if (emotion && !query.includes(emotion)) query += " " + emotion;
  if (date)    query += " " + date;

  if (!query.trim()) { container.innerHTML = emptyState("🔍", "Enter a search query above."); return; }

  try {
    const res  = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    const data = await res.json();
    renderMemories(container, data, "No memories matched your search.");
  } catch {
    container.innerHTML = emptyState("⚠️", "Search failed. Please try again.");
  }
}

// ── Summary ───────────────────────────────────────────────────────────────────
function setupSummary() {
  document.getElementById("btnSummary").addEventListener("click", loadSummary);
}

async function loadSummary() {
  const date = document.getElementById("summaryDate").value;
  const container = document.getElementById("summaryResult");
  container.innerHTML = "<p style='color:var(--text-muted)'>Loading…</p>";

  try {
    const res  = await fetch(`/api/summary?date=${date}`);
    const data = await res.json();

    let html = `<div class="summary-box">
      <p>📅 <strong>${formatDate(data.date)}</strong></p>
      <p style="margin-top:.5rem">${data.summary}</p>`;

    if (data.emotions && Object.keys(data.emotions).length) {
      html += `<div class="emotion-stats">`;
      for (const [em, count] of Object.entries(data.emotions)) {
        const meta = EMOTION_META[em] || EMOTION_META.neutral;
        html += `<span class="emotion-stat">${meta.icon} ${meta.label}: ${count}</span>`;
      }
      html += `</div>`;
    }
    html += `</div>`;

    if (data.memories && data.memories.length) {
      html += `<h3 style="margin-bottom:.75rem;font-size:1rem">Memories of the day</h3>`;
      const tempDiv = document.createElement("div");
      tempDiv.className = "memory-list";
      container.innerHTML = html;
      renderMemories(tempDiv, data.memories);
      container.appendChild(tempDiv);
      return;
    }

    container.innerHTML = html;
  } catch {
    container.innerHTML = emptyState("⚠️", "Failed to load summary.");
  }
}

// ── Reminders ─────────────────────────────────────────────────────────────────
async function loadReminders() {
  const container = document.getElementById("reminderList");
  container.innerHTML = "<p style='color:var(--text-muted)'>Loading…</p>";

  try {
    const res  = await fetch("/api/reminders");
    const data = await res.json();

    if (!data.length) {
      container.innerHTML = emptyState("🔔", "No reminders for today or tomorrow.");
      return;
    }

    container.innerHTML = data.map(r => `
      <div class="reminder-card">
        <div class="reminder-icon">🔔</div>
        <div>
          <h4>You planned to meet <strong>${r.person}</strong></h4>
          <p>${r.text}</p>
          <p style="margin-top:.3rem;font-size:.78rem">Reminder date: ${formatDate(r.remind_date)}</p>
        </div>
      </div>
    `).join("");
  } catch {
    container.innerHTML = emptyState("⚠️", "Failed to load reminders.");
  }
}

// ── All Memories ──────────────────────────────────────────────────────────────
async function loadAllMemories() {
  const container = document.getElementById("allMemories");
  container.innerHTML = "<p style='color:var(--text-muted)'>Loading…</p>";

  try {
    const res  = await fetch("/api/memories?limit=50");
    const data = await res.json();
    renderMemories(container, data, "No memories stored yet. Add your first memory!");
  } catch {
    container.innerHTML = emptyState("⚠️", "Failed to load memories.");
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function renderMemories(container, memories, emptyMsg = "No memories found.") {
  if (!memories.length) {
    container.innerHTML = emptyState("🧠", emptyMsg);
    return;
  }
  container.innerHTML = memories.map(m => memoryCard(m)).join("");

  // Bind delete buttons
  container.querySelectorAll(".delete-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      if (!confirm("Delete this memory?")) return;
      await fetch(`/api/memories/${btn.dataset.id}`, { method: "DELETE" });
      btn.closest(".memory-card").remove();
      if (!container.querySelector(".memory-card"))
        container.innerHTML = emptyState("🧠", emptyMsg);
    });
  });
}

function memoryCard(m) {
  const em   = EMOTION_META[m.emotion] || EMOTION_META.neutral;
  const time = m.time ? m.time.slice(0, 5) : "";
  return `
    <div class="memory-card">
      <button class="delete-btn" data-id="${m.id}" title="Delete">🗑</button>
      <div class="meta">
        <span class="date-time">📅 ${formatDate(m.date)} ${time ? "· ⏰ " + time : ""}</span>
        ${m.person ? `<span class="person-tag">👤 ${m.person}</span>` : ""}
        <span class="emotion-badge emotion-${m.emotion}">${em.icon} ${em.label}</span>
      </div>
      <p class="text">${escapeHtml(m.text)}</p>
    </div>`;
}

function showResult(el, type, msg) {
  el.className = `result-box ${type}`;
  el.textContent = msg;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 5000);
}

function emptyState(icon, msg) {
  return `<div class="empty-state"><div class="icon">${icon}</div><p>${msg}</p></div>`;
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { weekday: "short", year: "numeric", month: "short", day: "numeric" });
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}