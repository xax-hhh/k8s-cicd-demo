import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from logging import StreamHandler
from flask import Flask, jsonify, render_template, request, g
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

APP_NAME = os.getenv("APP_NAME", "ops-task-demo")
DB_PATH = os.getenv("DB_PATH", "/data/tasks.db")
PORT = int(os.getenv("PORT", "8080"))

app = Flask(__name__)

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "service": APP_NAME,
        }
        if hasattr(record, "extra_fields"):
            payload.update(record.extra_fields)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

handler = StreamHandler()
handler.setFormatter(JsonFormatter())
app.logger.handlers = [handler]
app.logger.setLevel(logging.INFO)
app.logger.propagate = False

HTTP_REQUESTS = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
TASKS_CREATED = Counter("tasks_created_total", "Total tasks created")
TASKS_COMPLETED = Counter("tasks_completed_total", "Total tasks marked completed")
TASKS_CURRENT = Gauge("tasks_current", "Current number of tasks")

def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        g.db = sqlite3.connect(DB_PATH, timeout=5)
        g.db.row_factory = sqlite3.Row
        g.db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'todo',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        g.db.commit()
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

@app.before_request
def before_request():
    g.request_started_at = time.time()

@app.after_request
def after_request(response):
    endpoint = request.endpoint or "unknown"
    HTTP_REQUESTS.labels(request.method, endpoint, str(response.status_code)).inc()
    elapsed_ms = round((time.time() - getattr(g, "request_started_at", time.time())) * 1000, 2)
    app.logger.info(
        "http_request",
        extra={"extra_fields": {
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "duration_ms": elapsed_ms,
        }},
    )
    return response

def refresh_task_gauge():
    count = get_db().execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    TASKS_CURRENT.set(count)

@app.get("/")
def index():
    return render_template("index.html", app_name=APP_NAME)

@app.get("/api/tasks")
def list_tasks():
    rows = get_db().execute(
        "SELECT * FROM tasks ORDER BY id DESC"
    ).fetchall()
    return jsonify([dict(row) for row in rows])

@app.post("/api/tasks")
def create_task():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    now = datetime.now(timezone.utc).isoformat()
    cur = get_db().execute(
        "INSERT INTO tasks(title, description, status, created_at, updated_at) VALUES (?, ?, 'todo', ?, ?)",
        (title, description, now, now),
    )
    get_db().commit()
    TASKS_CREATED.inc()
    refresh_task_gauge()
    task = get_db().execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    app.logger.info("task_created", extra={"extra_fields": {"task_id": cur.lastrowid}})
    return jsonify(dict(task)), 201

@app.patch("/api/tasks/<int:task_id>")
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    allowed = {"todo", "doing", "done"}
    status = data.get("status")
    if status not in allowed:
        return jsonify({"error": "status must be todo, doing or done"}), 400
    db = get_db()
    old = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if old is None:
        return jsonify({"error": "task not found"}), 404
    now = datetime.now(timezone.utc).isoformat()
    db.execute("UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?", (status, now, task_id))
    db.commit()
    if status == "done" and old["status"] != "done":
        TASKS_COMPLETED.inc()
    refresh_task_gauge()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    app.logger.info("task_updated", extra={"extra_fields": {"task_id": task_id, "status": status}})
    return jsonify(dict(row))

@app.delete("/api/tasks/<int:task_id>")
def delete_task(task_id):
    db = get_db()
    cur = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    if cur.rowcount == 0:
        return jsonify({"error": "task not found"}), 404
    refresh_task_gauge()
    app.logger.info("task_deleted", extra={"extra_fields": {"task_id": task_id}})
    return "", 204

@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": APP_NAME})

@app.get("/ready")
def ready():
    try:
        get_db().execute("SELECT 1").fetchone()
        return jsonify({"status": "ready"})
    except Exception as exc:
        app.logger.exception("readiness_check_failed")
        return jsonify({"status": "not_ready", "error": str(exc)}), 503

@app.get("/metrics")
def metrics():
    refresh_task_gauge()
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

@app.errorhandler(500)
def internal_error(error):
    app.logger.exception("internal_server_error")
    return jsonify({"error": "internal server error"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
