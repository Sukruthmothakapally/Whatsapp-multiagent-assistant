import sqlite3
from pathlib import Path
import os

MEMORY_DIR = Path(__file__).parent
DB_PATH = MEMORY_DIR / "memory.db"

os.makedirs(MEMORY_DIR, exist_ok=True) 

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                role TEXT,
                message TEXT
            )
        """)

def add_to_memory(conversation_id: str, role: str, message: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO memory (conversation_id, role, message) VALUES (?, ?, ?)",
            (conversation_id, role, message)
        )
        # Keep only last 10 messages per conversation
        conn.execute("""
            DELETE FROM memory WHERE id NOT IN (
                SELECT id FROM memory WHERE conversation_id = ?
                ORDER BY id DESC LIMIT 20
            ) AND conversation_id = ?
        """, (conversation_id, conversation_id))

def get_memory(conversation_id: str) -> list[tuple[str, str]]:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("""
            SELECT role, message FROM memory
            WHERE conversation_id = ?
            ORDER BY id ASC
        """, (conversation_id,))
        return [(row[0], row[1]) for row in cur.fetchall()]

def clear_memory(conversation_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM memory WHERE conversation_id = ?", (conversation_id,))

init_db()
