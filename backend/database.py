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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_ai_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    memory_text TEXT NOT NULL,
                    source_text TEXT,
                    importance INTEGER DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, memory_type, memory_text)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_ai_preferences (
                    user_id TEXT PRIMARY KEY,
                    preference_text TEXT,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_daily_tasks (
                    user_id TEXT NOT NULL,
                    task_date TEXT NOT NULL,
                    task_text TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, task_date)
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


def get_user_ai_preference(user_id: str) -> Optional[Tuple[str, str, str]]:
    """获取某个用户的 AI 偏好记忆。"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, preference_text, updated_at FROM user_ai_preferences WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
        return row
    except sqlite3.Error as e:
        logger.error(f"Failed to get AI preference for {user_id}: {e}")
        return None


def upsert_user_ai_preference(user_id: str, preference_text: str, updated_at: str) -> bool:
    """保存或更新某个用户的 AI 偏好记忆。"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO user_ai_preferences (user_id, preference_text, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    preference_text = excluded.preference_text,
                    updated_at = excluded.updated_at
                """,
                (user_id, preference_text, updated_at),
            )
            conn.commit()
        logger.info(f"AI preference saved for user: {user_id}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Failed to save AI preference for {user_id}: {e}")
        return False


def get_user_daily_task(user_id: str, task_date: str) -> Optional[Tuple[str, str, str, str]]:
    """读取某个用户在某一天填写的任务描述。"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT user_id, task_date, task_text, updated_at
                FROM user_daily_tasks
                WHERE user_id = ? AND task_date = ?
                """,
                (user_id, task_date),
            )
            row = cursor.fetchone()
        return row
    except sqlite3.Error as e:
        logger.error(f"Failed to get daily task for {user_id} {task_date}: {e}")
        return None


def upsert_user_daily_task(user_id: str, task_date: str, task_text: str, updated_at: str) -> bool:
    """保存或更新某个用户某一天的任务描述。"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO user_daily_tasks (user_id, task_date, task_text, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, task_date) DO UPDATE SET
                    task_text = excluded.task_text,
                    updated_at = excluded.updated_at
                """,
                (user_id, task_date, task_text, updated_at),
            )
            conn.commit()
        logger.info(f"Daily task saved for user {user_id} on {task_date}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Failed to save daily task for {user_id} {task_date}: {e}")
        return False
