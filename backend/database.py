# backend/database.py
import sqlite3
import os
from pathlib import Path
from typing import Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "study_sessions.db"


def init_db() -> None:
    """初始化数据库，创建 sessions 表"""
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    focus_score REAL,
                    avg_stress REAL
                )
            """)
            conn.commit()
        logger.info(f"Database initialized at {DB_PATH}")
    except sqlite3.Error as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def create_session(session_id: str, start_time: str) -> bool:
    """保存新会话"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sessions (id, start_time) VALUES (?, ?)",
                (session_id, start_time),
            )
            conn.commit()
        logger.info(f"Session created: {session_id}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Failed to create session {session_id}: {e}")
        return False


def update_session(
    session_id: str, end_time: str, focus_score: float, avg_stress: float
) -> bool:
    """结束会话并更新数据"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sessions SET end_time = ?, focus_score = ?, avg_stress = ? WHERE id = ?",
                (end_time, focus_score, avg_stress, session_id),
            )
            conn.commit()
        logger.info(f"Session updated: {session_id}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Failed to update session {session_id}: {e}")
        return False


def get_session(session_id: str) -> Optional[Tuple[str, str, str, float, float]]:
    """获取单次会话报告"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
        return row
    except sqlite3.Error as e:
        logger.error(f"Failed to get session {session_id}: {e}")
        return None


def get_all_sessions() -> List[Tuple[str, str, str, float, float]]:
    """获取所有会话记录"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions ORDER BY start_time DESC")
            rows = cursor.fetchall()
        return rows
    except sqlite3.Error as e:
        logger.error(f"Failed to get all sessions: {e}")
        return []
