from flask import Flask, request, jsonify, render_template
import sqlite3, re, os
from datetime import datetime, date, timedelta

app = Flask(__name__)

# Always store DB next to app.py regardless of working directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "memories.db")

# ─── Emotion Keywords ─────────────────────────────────────────────────────────
EMOTIONS = {
    "happy":      ["happy", "joy", "excited", "great", "wonderful", "amazing", "fun", "celebrate", "love", "fantastic"],
    "stress":     ["stress", "stressed", "anxious", "worried", "overwhelmed", "pressure", "deadline", "rush", "panic", "tense"],
    "sad":        ["sad", "unhappy", "depressed", "cry", "miss", "lonely", "upset", "disappointed", "grief", "hurt"],
    "productive": ["completed", "finished", "done", "achieved", "built", "wrote", "deployed", "submitted", "delivered", "productive"],
}

# ─── Date Keywords ────────────────────────────────────────────────────────────
DATE_WORDS = {
    "today": 0, "yesterday": -1, "tomorrow": 1,
    "monday": None, "tuesday": None, "wednesday": None,
    "thursday": None, "friday": None, "saturday": None, "sunday": None,
}

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# ─── DB Setup ─────────────────────────────────────────────────────────────────
def get_db():
    """Open a DB connection with row factory enabled."""
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create table and seed sample data on first run."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            text    TEXT NOT NULL,
            date    TEXT NOT NULL,
            time    TEXT NOT NULL,
            person  TEXT,
            emotion TEXT DEFAULT 'neutral',
            created TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    # Seed sample data if table is empty
    if conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 0:
        samples = [
            ("Completed the project report and sent it to the manager.", "2025-01-10", "09:30", "Manager", "productive"),
            ("Feeling stressed about the upcoming deadline for the client.", "2025-01-11", "14:00", "Client", "stress"),
            ("Had a wonderful birthday celebration with friends!", "2025-01-12", "19:00", "Friends", "happy"),
            ("Feeling sad today, missed my family back home.", "2025-01-13", "20:00", None, "sad"),
            ("Meeting Arun tomorrow at 10am to discuss the new project.", "2025-01-14", "11:00", "Arun", "productive"),
            ("Finished building the new feature and deployed it successfully.", "2025-01-15", "16:30", None, "productive"),
            ("Ravi and I reviewed the quarterly results — great numbers!", "2025-01-16", "10:00", "Ravi", "happy"),
        ]
        conn.executemany(
            "INSERT INTO memories (text, date, time, person, emotion) VALUES (?,?,?,?,?)", samples
        )
        conn.commit()
    conn.close()

init_db()

# ─── NLP Helpers ──────────────────────────────────────────────────────────────
def detect_emotion(text):
    lower = text.lower()
    for emotion, keywords in EMOTIONS.items():
        if any(k in lower for k in keywords):
            return emotion
    return "neutral"

def extract_names(text):
    """Extract capitalized words that look like names (not at sentence start)."""
    words = text.split()
    names = []
    for i, word in enumerate(words):
        clean = re.sub(r'[^a-zA-Z]', '', word)
        if i > 0 and clean and clean[0].isupper() and len(clean) > 2:
            names.append(clean)
    return names

def extract_date_from_query(query):
    """Return a date string YYYY-MM-DD or None from natural language."""
    lower = query.lower()
    today = date.today()

    for word, delta in DATE_WORDS.items():
        if word in lower and delta is not None:
            return str(today + timedelta(days=delta))

    for month_name, month_num in MONTH_NAMES.items():
        pattern = rf'(?:{month_name}\s+(\d{{1,2}})|(\d{{1,2}})\s+{month_name})'
        m = re.search(pattern, lower)
        if m:
            day = int(m.group(1) or m.group(2))
            year = today.year
            try:
                return str(date(year, month_num, day))
            except ValueError:
                pass

    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', query)
    if m:
        return m.group(0)
    m = re.search(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})', query)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        if len(y) == 2:
            y = "20" + y
        return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"

    return None

def detect_future_plans(text, mem_date):
    """Return reminder dict if text mentions a future plan."""
    lower = text.lower()
    future_words = ["tomorrow", "next week", "next monday", "next tuesday",
                    "next wednesday", "next thursday", "next friday",
                    "scheduled", "planning to", "will meet"]
    if not any(w in lower for w in future_words):
        return None

    names = extract_names(text)
    person = names[0] if names else "someone"

    try:
        base = datetime.strptime(mem_date, "%Y-%m-%d").date()
    except Exception:
        base = date.today()

    if "tomorrow" in lower:
        remind_date = base + timedelta(days=1)
    elif "next week" in lower:
        remind_date = base + timedelta(weeks=1)
    else:
        remind_date = base + timedelta(days=1)

    return {"person": person, "text": text, "remind_date": str(remind_date)}

# ─── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

# ── POST /api/memories — Add a new memory ────────────────────────────────────
@app.route("/api/memories", methods=["POST"])
def add_memory():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    text     = data.get("text", "").strip()
    person   = data.get("person", "").strip() or None
    mem_date = data.get("date") or str(date.today())
    mem_time = data.get("time") or datetime.now().strftime("%H:%M")

    if not text:
        return jsonify({"error": "Text is required"}), 400

    if not person:
        names = extract_names(text)
        person = names[0] if names else None

    emotion = detect_emotion(text)

    conn = get_db()
    cur = conn.execute(
        "INSERT INTO memories (text, date, time, person, emotion) VALUES (?,?,?,?,?)",
        (text, mem_date, mem_time, person, emotion)
    )
    mem_id = cur.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"id": mem_id, "emotion": emotion, "person": person}), 201

# ── GET /api/memories — Fetch recent memories ─────────────────────────────────
@app.route("/api/memories", methods=["GET"])
def get_memories():
    limit = request.args.get("limit", 20, type=int)
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM memories ORDER BY date DESC, time DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

# ── GET /api/search — Natural language search ─────────────────────────────────
@app.route("/api/search", methods=["GET"])
def search_memories():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    lower = query.lower()
    conditions, params = [], []

    extracted_date = extract_date_from_query(query)
    if extracted_date:
        conditions.append("date = ?")
        params.append(extracted_date)

    for emotion in EMOTIONS:
        if emotion in lower or (emotion == "stress" and "stressful" in lower):
            conditions.append("emotion = ?")
            params.append(emotion)
            break

    names = extract_names(query)
    if names:
        conditions.append("(person LIKE ? OR text LIKE ?)")
        params += [f"%{names[0]}%", f"%{names[0]}%"]

    stop_words = {"show", "me", "what", "did", "on", "the", "a", "an", "i", "my",
                  "find", "get", "all", "days", "day", "when", "who", "how", "about"}
    keywords = [w for w in re.findall(r'\b[a-z]{3,}\b', lower) if w not in stop_words]

    if not conditions and keywords:
        kw_conditions = ["text LIKE ?" for _ in keywords]
        conditions.append(f"({' OR '.join(kw_conditions)})")
        params += [f"%{k}%" for k in keywords]
    elif keywords and not extracted_date:
        kw_conditions = ["text LIKE ?" for _ in keywords]
        conditions.append(f"({' OR '.join(kw_conditions)})")
        params += [f"%{k}%" for k in keywords]

    sql = "SELECT * FROM memories"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY date DESC, time DESC"

    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

# ── GET /api/summary — Daily summary ─────────────────────────────────────────
@app.route("/api/summary", methods=["GET"])
def daily_summary():
    target_date = request.args.get("date") or str(date.today())
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM memories WHERE date = ? ORDER BY time", (target_date,)
    ).fetchall()
    conn.close()

    memories = [dict(r) for r in rows]
    if not memories:
        return jsonify({"date": target_date, "summary": "No memories recorded for this day.", "memories": []})

    total = len(memories)
    people = list({m["person"] for m in memories if m["person"]})
    emotions = {}
    for m in memories:
        emotions[m["emotion"]] = emotions.get(m["emotion"], 0) + 1

    dominant = max(emotions, key=emotions.get) if emotions else "neutral"
    emotion_icons = {"happy": "😊", "stress": "😓", "sad": "😢", "productive": "🚀", "neutral": "😐"}

    summary_parts = [f"You recorded {total} memor{'y' if total == 1 else 'ies'}."]
    if people:
        summary_parts.append(f"You interacted with: {', '.join(people)}.")
    summary_parts.append(f"Overall mood: {dominant} {emotion_icons.get(dominant, '')}")

    return jsonify({
        "date": target_date,
        "summary": " ".join(summary_parts),
        "total": total,
        "people": people,
        "emotions": emotions,
        "memories": memories,
    })

# ── GET /api/reminders — Smart reminders from future-plan mentions ────────────
@app.route("/api/reminders", methods=["GET"])
def get_reminders():
    today    = str(date.today())
    tomorrow = str(date.today() + timedelta(days=1))

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM memories WHERE date >= ? ORDER BY date DESC",
        (str(date.today() - timedelta(days=7)),)
    ).fetchall()
    conn.close()

    reminders = []
    seen = set()
    for row in rows:
        r = detect_future_plans(row["text"], row["date"])
        if r and r["remind_date"] in (today, tomorrow):
            key = (r["person"], r["remind_date"])
            if key not in seen:
                seen.add(key)
                r["original_date"] = row["date"]
                reminders.append(r)

    return jsonify(reminders)

# ── DELETE /api/memories/<id> — Delete a memory ───────────────────────────────
@app.route("/api/memories/<int:mem_id>", methods=["DELETE"])
def delete_memory(mem_id):
    conn = get_db()
    conn.execute("DELETE FROM memories WHERE id = ?", (mem_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": mem_id})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)