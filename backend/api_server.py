# backend/api_server.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
import uuid
import logging

from .database import init_db, create_session, update_session, get_session

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Focus Backend",
    description="专注度与压力监测学习助手后端API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


class StartSessionResponse(BaseModel):
    session_id: str
    start_time: str
    message: str


class EndSessionResponse(BaseModel):
    status: str
    session_id: str
    message: str


class SessionReport(BaseModel):
    session_id: str
    start_time: str
    end_time: Optional[str] = None
    focus_score: float
    avg_stress: float
    duration_seconds: Optional[float] = None


@app.post(
    "/start_session", summary="F1: 启动学习会话", response_model=StartSessionResponse
)
def start_session():
    """
    开始新的学习会话，返回会话ID和开始时间
    """
    session_id = str(uuid.uuid4())[:8]
    start_time = datetime.now().isoformat()
    success = create_session(session_id, start_time)

    if not success:
        logger.error(f"Failed to create session: {session_id}")
        raise HTTPException(status_code=500, detail="Failed to create session")

    logger.info(f"Session started: {session_id}")
    return StartSessionResponse(
        session_id=session_id,
        start_time=start_time,
        message="Session started successfully",
    )


@app.post(
    "/end_session/{session_id}",
    summary="F2: 结束学习会话",
    response_model=EndSessionResponse,
)
def end_session(
    session_id: str,
    focus_score: float = Query(..., ge=0, le=100, description="专注度分数 0-100"),
    avg_stress: float = Query(..., ge=0, le=100, description="平均压力值 0-100"),
):
    """
    结束会话，记录专注度和压力值
    """
    existing_session = get_session(session_id)
    if not existing_session:
        logger.warning(f"Session not found: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")

    if existing_session[2] is not None:
        logger.warning(f"Session already ended: {session_id}")
        raise HTTPException(status_code=400, detail="Session already ended")

    end_time = datetime.now().isoformat()
    success = update_session(session_id, end_time, focus_score, avg_stress)

    if not success:
        logger.error(f"Failed to update session: {session_id}")
        raise HTTPException(status_code=500, detail="Failed to update session")

    logger.info(
        f"Session ended: {session_id}, focus={focus_score}, stress={avg_stress}"
    )
    return EndSessionResponse(
        status="ended", session_id=session_id, message="Session ended successfully"
    )


@app.get(
    "/get_report/{session_id}", summary="F3: 获取学习报告", response_model=SessionReport
)
def get_report(session_id: str):
    """
    获取指定会话的完整报告
    """
    row = get_session(session_id)
    if not row:
        logger.warning(f"Session not found for report: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")

    session_id_val, start_time, end_time, focus_score, avg_stress = row

    return SessionReport(
        session_id=session_id_val,
        start_time=start_time,
        end_time=end_time,
        focus_score=focus_score if focus_score is not None else 0.0,
        avg_stress=avg_stress if avg_stress is not None else 0.0,
        duration_seconds=calculate_duration(start_time, end_time) if end_time else None,
    )


def calculate_duration(start_time: str, end_time: Optional[str]) -> Optional[float]:
    """计算会话持续时间（秒）"""
    if not end_time:
        return None
    try:
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        return (end - start).total_seconds()
    except (ValueError, TypeError) as e:
        logger.error(f"Failed to calculate duration: {e}")
        return None
