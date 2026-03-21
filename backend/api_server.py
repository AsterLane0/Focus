# backend/api_server.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import Optional, List
import uuid
import logging
from pathlib import Path
from statistics import mean, median

from .database import init_db, create_session, update_session, get_session, get_all_sessions
from src.data_loader import load_and_process_hrv_data
from analysis.focus_model import FocusModel
from analysis.learning_analysis import LearningAnalysis
from analysis.recommendation_engine import RecommendationEngine
from analysis.report_generator import ReportGenerator

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

EXTENDED_RAW_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "virtual_hrv_extended.csv"
RAW_DATA_PATH = (
    EXTENDED_RAW_DATA_PATH
    if EXTENDED_RAW_DATA_PATH.exists()
    else Path(__file__).resolve().parent.parent / "data" / "raw" / "senor_hrv_filtered.csv"
)


class TrendPoint(BaseModel):
    time: str
    stress: float
    focus: float
    value: Optional[float] = None
    label: Optional[str] = None


class FocusPeriod(BaseModel):
    start_time: str
    end_time: str
    stress: float
    focus: float
    duration_minutes: int
    state: str = "正常"
    hrv_points: List[TrendPoint] = Field(default_factory=list)


class RecentSession(BaseModel):
    session_id: str
    start_time: str
    end_time: Optional[str] = None
    focus_score: float
    avg_stress: float
    duration_seconds: Optional[float] = None


class DailyDashboard(BaseModel):
    period: str
    user_id: str
    date: str
    range_label: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    focus_score: float
    study_count: int
    stress_average: float
    focus_average: float
    stress_trend: str
    focus_trend: str
    state: str
    advice: str
    total_minutes: int
    focus_minutes: int
    avg_heart_rate: float
    recommendation: dict
    trend_points: List[TrendPoint]
    focus_periods: List[FocusPeriod]
    recent_sessions: List[RecentSession]


@app.get("/users", summary="获取可用用户列表", response_model=List[str])
def list_users():
    """
    返回当前 HRV 数据里存在的所有用户 ID。
    """
    daily_data = load_and_process_hrv_data(str(RAW_DATA_PATH))
    if not daily_data:
        raise HTTPException(status_code=404, detail="No HRV data available")
    return sorted(daily_data.keys())


def format_cn_date(date_str: str) -> str:
    """把 YYYY-MM-DD 转成中文日期展示。"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.year}年{dt.month}月{dt.day}日"


def format_short_cn_date(date_str: str) -> str:
    """把 YYYY-MM-DD 转成更短的中文日期展示。"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.month}月{dt.day}日"


def add_clock_minutes(time_str: str, minutes: int) -> str:
    """给 HH:MM 字符串增加分钟数。"""
    try:
        dt = datetime.strptime(time_str, "%H:%M")
        return (dt + timedelta(minutes=minutes)).strftime("%H:%M")
    except ValueError:
        return time_str


def evaluate_pomodoro_state(stress_avg: float, focus_avg: float) -> str:
    """按单个番茄钟的压力/专注度给出简单状态。"""
    if stress_avg > 60 and focus_avg < 40:
        return "压力过大"
    return "正常"


def build_hrv_trend_points(history_dict: dict, date_key: Optional[str] = None) -> List[TrendPoint]:
    """把单日 HR 数据转成 HRV 曲线点（RMSSD）。"""
    model = FocusModel()
    history_list = model.sort_data_by_time(history_dict)
    window_list = model.split_5mins_window_list(history_list)
    window_list = model.filter_time_intervals(window_list)

    points: List[TrendPoint] = []
    for window in window_list:
        rr_list = model.hr_to_rr(window)
        if len(rr_list) < 2:
            continue
        rmssd = model.rr_to_rmssd(rr_list)
        label = window[0][0]
        points.append(
            TrendPoint(
                time=window[0][0],
                stress=0.0,
                focus=0.0,
                value=float(rmssd),
                label=label,
            )
        )

    return points


def build_hourly_trend_points(history_dict: dict) -> List[TrendPoint]:
    """把单日 HR 数据聚合成 24 小时的 HRV 分布图。"""
    raw_points = build_hrv_trend_points(history_dict)
    hourly_values: dict[int, list[float]] = {hour: [] for hour in range(24)}

    for point in raw_points:
        try:
            hour = int(point.time.split(":")[0])
        except (ValueError, IndexError):
            continue
        if point.value is not None:
            hourly_values[hour].append(float(point.value))

    trend_points: List[TrendPoint] = []
    for hour in range(24):
        values = hourly_values[hour]
        trend_points.append(
            TrendPoint(
                time=f"{hour:02d}:00",
                stress=0.0,
                focus=0.0,
                value=round(mean(values), 2) if values else None,
                label=f"{hour:02d}:00",
            )
        )

    return trend_points


def build_pomodoro_periods(
    history_dict: dict,
) -> tuple[List[FocusPeriod], List[dict], List[TrendPoint]]:
    """把单日数据拆成番茄钟，并附上每次番茄钟的 HRV 曲线。"""
    model = FocusModel()
    history_list = model.sort_data_by_time(history_dict)
    window_list = model.split_5mins_window_list(history_list)
    window_list = model.filter_time_intervals(window_list)
    if not window_list:
        return [], [], []

    first_window_time = parse_clock_time(window_list[0][0][0])
    interval_minutes = sample_interval_minutes(history_dict["time"])
    grouped_windows: dict[int, list[dict]] = {}

    for window in window_list:
        rr_list = model.hr_to_rr(window)
        if len(rr_list) < 2:
            continue
        rmssd = model.rr_to_rmssd(rr_list)
        stress = model.rmssd_to_stress(rmssd)
        focus = model.stress_to_focus(stress)
        window_time = window[0][0]
        window_dt = parse_clock_time(window_time)
        diff_minutes = int((window_dt - first_window_time).total_seconds() // 60)
        pomodoro_index = max(0, diff_minutes // 25)

        grouped_windows.setdefault(pomodoro_index, []).append(
            {
                "time": window_time,
                "rmssd": float(rmssd),
                "stress": float(stress),
                "focus": float(focus),
            }
        )

    focus_periods: List[FocusPeriod] = []
    score_list_per_pomodoro: List[dict] = []
    selected_trend_points: List[TrendPoint] = []

    for index in sorted(grouped_windows.keys()):
        pomodoro_points = grouped_windows[index]
        if not pomodoro_points:
            continue

        stress_avg = sum(point["stress"] for point in pomodoro_points) / len(pomodoro_points)
        focus_avg = sum(point["focus"] for point in pomodoro_points) / len(pomodoro_points)
        start_time = pomodoro_points[0]["time"]
        end_time = add_clock_minutes(pomodoro_points[-1]["time"], interval_minutes)
        state = evaluate_pomodoro_state(stress_avg, focus_avg)
        hrv_points = [
            TrendPoint(
                time=point["time"],
                stress=float(point["stress"]),
                focus=float(point["focus"]),
                value=float(point["rmssd"]),
                label=point["time"],
            )
            for point in pomodoro_points
        ]

        focus_periods.append(
            FocusPeriod(
                start_time=start_time,
                end_time=end_time,
                stress=float(stress_avg),
                focus=float(focus_avg),
                duration_minutes=estimate_duration_minutes(
                    start_time,
                    end_time,
                    sample_interval_minutes=interval_minutes,
                ),
                state=state,
                hrv_points=hrv_points,
            )
        )
        score_list_per_pomodoro.append(
            {
                "start_time": start_time,
                "end_time": end_time,
                "stress": float(stress_avg),
                "focus": float(focus_avg),
                "state": state,
            }
        )
        if not selected_trend_points:
            selected_trend_points = hrv_points

    return focus_periods, score_list_per_pomodoro, selected_trend_points


def build_weekday_trend_points(week_start: str, week_end: str, user_data: dict) -> List[TrendPoint]:
    """按周一到周日输出 7 个日级 HRV 点。"""
    start_dt = datetime.strptime(week_start, "%Y-%m-%d")
    end_dt = datetime.strptime(week_end, "%Y-%m-%d")
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    trend_points: List[TrendPoint] = []

    current_dt = start_dt
    while current_dt <= end_dt:
        date_key = current_dt.strftime("%Y-%m-%d")
        weekday_label = weekday_names[current_dt.weekday()]
        history_dict = user_data.get(date_key)

        if history_dict and history_dict.get("time") and history_dict.get("hr"):
            day_hrv_points = build_hrv_trend_points(history_dict, date_key)
            day_values = [point.value for point in day_hrv_points if point.value is not None]
            day_value = round(mean(day_values), 2) if day_values else None
        else:
            day_value = None

        trend_points.append(
            TrendPoint(
                time=weekday_label,
                stress=0.0,
                focus=0.0,
                value=day_value,
                label=date_key,
            )
        )
        current_dt += timedelta(days=1)

    return trend_points


def week_bounds(date_str: str) -> tuple[str, str]:
    """根据某一天计算所在周的起止日期（周一到周日）。"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    week_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = week_start - timedelta(days=week_start.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")


def build_daily_dashboard(
    user_id: Optional[str] = None,
    date: Optional[str] = None,
    period: str = "day",
) -> DailyDashboard:
    """
    根据原始 HRV 数据生成前端统计页所需的数据。
    """
    daily_data = load_and_process_hrv_data(str(RAW_DATA_PATH))
    if not daily_data:
        raise HTTPException(status_code=404, detail="No HRV data available")

    selected_user_id = str(user_id) if user_id is not None else sorted(daily_data.keys())[-1]
    if selected_user_id not in daily_data:
        raise HTTPException(status_code=404, detail=f"User not found: {selected_user_id}")

    user_data = daily_data[selected_user_id]
    if date is None or date not in user_data:
        raise HTTPException(status_code=404, detail=f"Date not found for user {selected_user_id}: {date}")
    target_date = date
    if period == "week":
        week_start, week_end = week_bounds(target_date)
        selected_dates = [
            date_key
            for date_key in sorted(user_data.keys())
            if week_start <= date_key <= week_end
        ]
        if not selected_dates:
            selected_dates = [target_date]
        return build_weekly_dashboard(
            selected_user_id,
            target_date,
            week_start,
            week_end,
            selected_dates,
            user_data,
        )

    history_dict = user_data[target_date]
    focus_periods, score_list_per_pomodoro, pomodoro_trend_points = build_pomodoro_periods(history_dict)
    interval_minutes = sample_interval_minutes(history_dict["time"])
    trend_points = pomodoro_trend_points or build_hourly_trend_points(history_dict)

    analysis = LearningAnalysis()
    analysis_result = analysis.analyze_daily_learning(score_list_per_pomodoro)
    recommendation = RecommendationEngine().generate(analysis_result)
    report = ReportGenerator().generate(analysis_result, recommendation)
    recent_sessions = [
        RecentSession(
            session_id=row[0],
            start_time=row[1],
            end_time=row[2],
            focus_score=float(row[3] or 0.0),
            avg_stress=float(row[4] or 0.0),
            duration_seconds=calculate_duration(row[1], row[2]) if row[2] else None,
        )
        for row in get_all_sessions()[:5]
    ]

    total_minutes = estimate_duration_minutes(
        history_dict["time"][0],
        history_dict["time"][-1],
        sample_interval_minutes=interval_minutes,
    )
    avg_heart_rate = round(mean(history_dict["hr"]), 2) if history_dict["hr"] else 0.0
    focus_minutes = min(
        sum(period.duration_minutes for period in focus_periods if period.focus >= 70),
        total_minutes,
    )

    return DailyDashboard(
        period="day",
        user_id=selected_user_id,
        date=target_date,
        range_label=format_cn_date(target_date),
        start_date=target_date,
        end_date=target_date,
        focus_score=float(report.get("focus_average") or 0.0),
        study_count=int(analysis_result.get("study_count") or 0),
        stress_average=float(analysis_result.get("stress_average") or 0.0),
        focus_average=float(analysis_result.get("focus_average") or 0.0),
        stress_trend=str(analysis_result.get("stress_trend") or ""),
        focus_trend=str(analysis_result.get("focus_trend") or ""),
        state=str(recommendation.get("state") or ""),
        advice=str(recommendation.get("advice") or ""),
        total_minutes=total_minutes,
        focus_minutes=focus_minutes,
        avg_heart_rate=avg_heart_rate,
        recommendation=recommendation,
        trend_points=trend_points,
        focus_periods=focus_periods,
        recent_sessions=recent_sessions,
    )


def build_weekly_dashboard(
    user_id: str,
    target_date: str,
    week_start: str,
    week_end: str,
    selected_dates: list[str],
    user_data: dict,
) -> DailyDashboard:
    """按周聚合：日期范围 + 一周 HRV 曲线。"""
    model = FocusModel()
    all_score_list_per_pomodoro = []
    weekly_trend_points: list[TrendPoint] = []
    weekly_focus_periods: list[FocusPeriod] = []
    total_minutes = 0
    total_hr_values = []

    for date_key in selected_dates:
        history_dict = user_data[date_key]
        if not history_dict.get("time") or not history_dict.get("hr"):
            continue

        day_focus_periods, day_scores, _day_curve = build_pomodoro_periods(history_dict)
        all_score_list_per_pomodoro.extend(day_scores)

        interval_minutes = sample_interval_minutes(history_dict["time"])
        day_total_minutes = estimate_duration_minutes(
            history_dict["time"][0],
            history_dict["time"][-1],
            sample_interval_minutes=interval_minutes,
        )
        total_minutes += day_total_minutes
        total_hr_values.extend(history_dict["hr"])

        for item, period in zip(day_scores, day_focus_periods):
            weekly_focus_periods.append(
                FocusPeriod(
                    start_time=f"{date_key[5:]} {item['start_time']}",
                    end_time=f"{date_key[5:]} {add_clock_minutes(item['end_time'], interval_minutes)}",
                    stress=float(item["stress"]),
                    focus=float(item["focus"]),
                    duration_minutes=estimate_duration_minutes(
                        item["start_time"],
                        item["end_time"],
                        sample_interval_minutes=interval_minutes,
                    ),
                    state=period.state,
                    hrv_points=period.hrv_points,
                )
            )

    analysis = LearningAnalysis()
    analysis_result = analysis.analyze_daily_learning(all_score_list_per_pomodoro)
    recommendation = RecommendationEngine().generate(analysis_result)
    report = ReportGenerator().generate(analysis_result, recommendation)
    recent_sessions = [
        RecentSession(
            session_id=row[0],
            start_time=row[1],
            end_time=row[2],
            focus_score=float(row[3] or 0.0),
            avg_stress=float(row[4] or 0.0),
            duration_seconds=calculate_duration(row[1], row[2]) if row[2] else None,
        )
        for row in get_all_sessions()[:5]
    ]

    avg_heart_rate = round(mean(total_hr_values), 2) if total_hr_values else 0.0
    weekly_trend_points = build_weekday_trend_points(week_start, week_end, user_data)
    focus_minutes = min(
        sum(period.duration_minutes for period in weekly_focus_periods if period.focus >= 70),
        total_minutes,
    )

    return DailyDashboard(
        period="week",
        user_id=user_id,
        date=target_date,
        range_label=f"{format_short_cn_date(week_start)} - {format_short_cn_date(week_end)}",
        start_date=week_start,
        end_date=week_end,
        focus_score=float(report.get("focus_average") or 0.0),
        study_count=int(analysis_result.get("study_count") or 0),
        stress_average=float(analysis_result.get("stress_average") or 0.0),
        focus_average=float(analysis_result.get("focus_average") or 0.0),
        stress_trend=str(analysis_result.get("stress_trend") or ""),
        focus_trend=str(analysis_result.get("focus_trend") or ""),
        state=str(recommendation.get("state") or ""),
        advice=str(recommendation.get("advice") or ""),
        total_minutes=total_minutes,
        focus_minutes=focus_minutes,
        avg_heart_rate=avg_heart_rate,
        recommendation=recommendation,
        trend_points=weekly_trend_points,
        focus_periods=weekly_focus_periods,
        recent_sessions=recent_sessions,
    )


def parse_clock_time(time_str: str) -> datetime:
    """将 HH:MM 转成可比较的时间对象。"""
    return datetime.strptime(time_str, "%H:%M")


def sample_interval_minutes(times: List[str]) -> int:
    """
    根据一组时间推测采样间隔，至少返回 1 分钟。
    """
    if len(times) < 2:
        return 1

    sorted_times = sorted(parse_clock_time(t) for t in times)
    intervals = []
    for left, right in zip(sorted_times, sorted_times[1:]):
        diff = (right - left).total_seconds() / 60
        if diff > 0:
            intervals.append(diff)

    if not intervals:
        return 1

    return max(1, int(round(median(intervals))))


def estimate_duration_minutes(start_time: str, end_time: str, sample_interval_minutes: int = 1) -> int:
    """
    用“停止 - 开始 + 一个采样间隔”估算覆盖时长。
    这样更接近一串逐分钟记录的真实展示时长。
    """
    try:
        start = parse_clock_time(start_time)
        end = parse_clock_time(end_time)
        duration = (end - start).total_seconds() / 60
        if duration < 0:
            return max(1, sample_interval_minutes)
        return max(1, int(round(duration + sample_interval_minutes)))
    except ValueError:
        return max(1, sample_interval_minutes)


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

@app.get("/daily_dashboard", summary="F4: 获取日统计看板", response_model=DailyDashboard)
def daily_dashboard(
    user_id: Optional[str] = Query(default=None, description="用户 ID"),
    date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    period: str = Query(default="day", description="day 或 week"),
):
    """
    返回前端统计页所需的日统计数据。
    """
    return build_daily_dashboard(user_id, date, period)


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
