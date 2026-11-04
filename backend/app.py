import os
import sqlite3
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import make_asgi_app, Counter
from contextlib import asynccontextmanager

DB_PATH = os.getenv("DB_PATH", "/data/guestbook.db")

MESSAGES_CREATED = Counter("messages_created_total", "Total messages created")

def get_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

db = get_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    db.close()

app = FastAPI(lifespan=lifespan)
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

class MessageCreate(BaseModel):
    author: str
    content: str

@app.get("/api/messages")
def list_messages():
    rows = db.execute("SELECT * FROM messages ORDER BY id DESC LIMIT 50").fetchall()
    return [dict(row) for row in rows]

@app.post("/api/messages")
def create_message(payload: MessageCreate):
    if not payload.author.strip() or not payload.content.strip():
        raise HTTPException(status_code=400, detail="昵称和内容不能为空")
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = db.execute(
        "INSERT INTO messages (author, content, created_at) VALUES (?, ?, ?)",
        (payload.author.strip(), payload.content.strip(), now)
    )
    db.commit()
    MESSAGES_CREATED.inc()
    
    row = db.execute("SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)

@app.get("/health")
def health(): return {"status": "ok"}

@app.get("/ready")
def ready():
    try:
        db.execute("SELECT 1").fetchone()
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))