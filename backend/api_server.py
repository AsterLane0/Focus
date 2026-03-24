# backend/api_server.py
import hashlib
import json
import os

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import Optional, List
import uuid
import logging
from pathlib import Path
from statistics import mean, median

from .database import (
    init_db,
    create_session,
    update_session,
    get_session,
    get_all_sessions,
    get_user_ai_preference,
    upsert_user_ai_preference,
    get_user_daily_task,
    upsert_user_daily_task,
    get_ai_report,
    save_ai_report,
)
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

EXTENDED_RAW_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "en_gage_hrv.csv"
RAW_DATA_PATH = (
    EXTENDED_RAW_DATA_PATH
    if EXTENDED_RAW_DATA_PATH.exists()
    else Path(__file__).resolve().parent.parent / "data" / "raw" / "en_gage_hrv.csv"
)

# =====配置层======
_HRV_DATA_CACHE: dict | None = None
_HRV_DATA_CACHE_SOURCE: tuple[str, float, int] | None = None
_AI_ANALYSIS_CACHE: dict[str, str] = {}

def get_cached_hrv_data() -> dict:
    """读取并缓存原始 HRV 数据，避免每次请求都重新解析整份 CSV。"""
    global _HRV_DATA_CACHE, _HRV_DATA_CACHE_SOURCE
    try:
        stat = RAW_DATA_PATH.stat()
    except FileNotFoundError:
        _HRV_DATA_CACHE = None
        _HRV_DATA_CACHE_SOURCE = None
        return {}

    source = (str(RAW_DATA_PATH), stat.st_mtime, stat.st_size)
    if _HRV_DATA_CACHE is None or _HRV_DATA_CACHE_SOURCE != source:
        _HRV_DATA_CACHE = load_and_process_hrv_data(str(RAW_DATA_PATH))
        _HRV_DATA_CACHE_SOURCE = source
    return _HRV_DATA_CACHE or {}

# ===== AI缓存Key=====
def _make_ai_analysis_cache_key(
    *,
    period_label: str,
    display_label: str,
    user_id: str,
    analysis_result: dict,
    recommendation: dict,
    profile_summary: str,
    user_preference: str,
    task_summary: str,
    summary_text: str,
    focus_periods: list["FocusPeriod"] | None,
) -> str:
    """把 AI 输入压成一个稳定的缓存键。"""
    focus_signature: list[dict] = []
    for period in focus_periods or []:
        try:
            focus_signature.append(period.model_dump(exclude={"hrv_points"}))
        except Exception:
            focus_signature.append(
                {
                    "start_time": getattr(period, "start_time", ""),
                    "end_time": getattr(period, "end_time", ""),
                    "stress": getattr(period, "stress", 0.0),
                    "focus": getattr(period, "focus", 0.0),
                    "duration_minutes": getattr(period, "duration_minutes", 0),
                    "state": getattr(period, "state", "正常"),
                }
            )

    payload = {
        "period_label": period_label,
        "display_label": display_label,
        "user_id": user_id,
        "analysis_result": analysis_result,
        "recommendation": recommendation,
        "profile_summary": profile_summary,
        "user_preference": user_preference,
        "task_summary": task_summary,
        "summary_text": summary_text,
        "focus_periods": focus_signature,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()

# =====数据结构=====
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
    ai_stress_analysis: Optional[str] = None
    user_ai_preference: Optional[str] = None
    user_daily_task: Optional[str] = None
    trend_points: List[TrendPoint]
    focus_periods: List[FocusPeriod]
    recent_sessions: List[RecentSession]

class UserAIPreference(BaseModel):
    user_id: str
    preference_text: str = ""
    updated_at: Optional[str] = None

class UserDailyTask(BaseModel):
    user_id: str
    task_date: str
    task_text: str = ""
    updated_at: Optional[str] = None

# ====API接口====
@app.get("/users", summary="获取可用用户列表", response_model=List[str])
def list_users():
    """
    返回当前 HRV 数据里存在的所有用户 ID。
    """
    daily_data = get_cached_hrv_data()
    if not daily_data:
        raise HTTPException(status_code=404, detail="No HRV data available")
    return sorted(daily_data.keys())

@app.get("/calendar_index", summary="获取用户可用日期索引")
def calendar_index(user_id: Optional[str] = Query(None, description="用户 ID")):
    """
    返回某个用户所有可用日期、月份和年份，供前端做月历高亮。
    """
    daily_data = get_cached_hrv_data()
    if not daily_data:
        raise HTTPException(status_code=404, detail="No HRV data available")

    selected_user_id = str(user_id) if user_id is not None else sorted(daily_data.keys())[-1]
    if selected_user_id not in daily_data:
        raise HTTPException(status_code=404, detail=f"User not found: {selected_user_id}")

    user_data = daily_data[selected_user_id]
    available_dates = sorted(user_data.keys())
    month_counts: dict[str, int] = {}
    years = set()
    for date_key in available_dates:
        dt = datetime.strptime(date_key, "%Y-%m-%d")
        years.add(dt.year)
        month_key = f"{dt.year}-{dt.month:02d}"
        month_counts[month_key] = month_counts.get(month_key, 0) + 1

    return {
        "user_id": selected_user_id,
        "available_dates": available_dates,
        "available_months": sorted(month_counts.keys()),
        "month_counts": month_counts,
        "years": sorted(years),
        "min_date": available_dates[0] if available_dates else None,
        "max_date": available_dates[-1] if available_dates else None,
    }

@app.get("/user_ai_preference", summary="获取用户 AI 记忆")
def read_user_ai_preference(user_id: str = Query(..., description="用户 ID")):
    """读取某个用户保存的 AI 个人偏好。"""
    row = get_user_ai_preference(str(user_id))
    if not row:
        return {
            "user_id": str(user_id),
            "preference_text": "",
            "updated_at": None,
        }

    return {
        "user_id": row[0],
        "preference_text": row[1] or "",
        "updated_at": row[2],
    }

@app.post("/user_ai_preference", summary="保存用户 AI 记忆")
def save_user_ai_preference(payload: UserAIPreference):
    """保存某个用户的 AI 个人偏好。"""
    user_id = str(payload.user_id).strip()
    preference_text = str(payload.preference_text or "").strip()
    updated_at = payload.updated_at or datetime.now().isoformat(timespec="seconds")
    success = upsert_user_ai_preference(user_id, preference_text, updated_at)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save AI preference")
    return {
        "user_id": user_id,
        "preference_text": preference_text,
        "updated_at": updated_at,
    }

@app.get("/user_daily_task", summary="获取用户当天任务")
def read_user_daily_task(
    user_id: str = Query(..., description="用户 ID"),
    task_date: str = Query(..., description="YYYY-MM-DD"),
):
    """读取某个用户某一天填写的任务。"""
    row = get_user_daily_task(str(user_id), str(task_date))
    if not row:
        return {
            "user_id": str(user_id),
            "task_date": str(task_date),
            "task_text": "",
            "updated_at": None,
        }

    return {
        "user_id": row[0],
        "task_date": row[1],
        "task_text": row[2] or "",
        "updated_at": row[3],
    }

@app.post("/user_daily_task", summary="保存用户当天任务")
def save_user_daily_task(payload: UserDailyTask):
    """保存某个用户某一天的任务。"""
    user_id = str(payload.user_id).strip()
    task_date = str(payload.task_date).strip()
    task_text = str(payload.task_text or "").strip()
    updated_at = payload.updated_at or datetime.now().isoformat(timespec="seconds")
    success = upsert_user_daily_task(user_id, task_date, task_text, updated_at)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save daily task")
    return {
        "user_id": user_id,
        "task_date": task_date,
        "task_text": task_text,
        "updated_at": updated_at,
    }

# =====工具函数=====
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

def _format_float_value(value: Optional[float], digits: int = 1) -> str:
    if value is None:
        return "--"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "--"

# ===== 本地AI fallback=====
def _build_local_ai_pressure_analysis(
    *,
    period_label: str,
    display_label: str,
    user_id: str,
    analysis_result: dict,
    recommendation: dict,
    task_summary: str = "",
    summary_text: str,
) -> str:
    stress_trend = str(analysis_result.get("stress_trend") or "no data")
    focus_trend = str(analysis_result.get("focus_trend") or "no data")
    state = str(recommendation.get("state") or "正常状态")
    task_text = str(task_summary or "").strip()
    advice_text = str(recommendation.get("advice") or "可以先放慢一点，别把自己逼太紧。").strip()

    state_phrase = {
        "压力过载": "整体有点绷",
        "疲惫状态": "看起来有点累",
        "状态优秀": "状态挺在线",
        "状态良好": "今天节奏还不错",
        "正常状态": "今天整体还算稳",
    }.get(state, "今天整体还算稳")

    stress_phrase = {
        "increasing": "压力是往上走的",
        "decreasing": "压力有慢慢缓下来",
        "stable": "压力没有太大波动",
        "insufficient data": "压力变化暂时还不好判断",
        "no data": "暂时还看不出明显压力变化",
    }.get(stress_trend, "压力没有太大波动")

    focus_phrase = {
        "improving": "专注状态在往好走",
        "declining": "专注有点往下掉",
        "stable": "专注状态比较稳",
        "insufficient data": "专注变化暂时还不好判断",
        "no data": "暂时还看不出明显专注变化",
    }.get(focus_trend, "专注状态比较稳")

    parts = []
    if task_text:
        parts.append(f"你今天主要在忙的是：{task_text}。")
    parts.append(f"这一天整体{state_phrase}，{stress_phrase}，{focus_phrase}。")
    parts.append("这种状态并不算差，但也不是那种可以完全放空的一天，还是得一边推进一边照顾节奏。")
    parts.append(f"接下来可以先试试：{advice_text}")
    return "\n\n".join(part for part in parts if part)

# =====Prompt构建层=====
def _build_daily_prompt(
    *,
    display_label: str,
    analysis_result: dict,
    recommendation: dict,
    profile_summary: str,
    user_preference: str,
    task_summary: str,
) -> str:

    stress_average = _format_float_value(analysis_result.get("stress_average"))
    focus_average = _format_float_value(analysis_result.get("focus_average"))
    study_count = int(analysis_result.get("study_count") or 0)
    stress_trend = str(analysis_result.get("stress_trend") or "no data")
    focus_trend = str(analysis_result.get("focus_trend") or "no data")

    state = str(recommendation.get("state") or "正常状态")

    return f"""
你是一个理性但不冷冰冰的学习分析者，说话像一个会认真观察人的朋友。

【用户风格偏好】
{user_preference or "无明显偏好"}

【这个人的长期状态】
{profile_summary}

⚠️ 注意：这是“今天”的数据，绝对不要出现“一周、本周”等词。

任务：{task_summary}
当前状态：{state}
压力：{stress_average}
专注：{focus_average}
趋势：压力{stress_trend}，专注{focus_trend}
学习次数：{study_count}

要求：
- 不要复述数据
- 不要鼓励（不要“加油”）
- 重点解释“为什么会这样”
- 只说1-2个关键点
- 注意格式易读，按点输出1️⃣，2️⃣，3️⃣等

结构：
1️⃣ 先判断今天状态（一句话）
2️⃣ 解释原因（结合任务 + 状态变化）
3️⃣ 给一个具体可执行建议

输出：3-4句自然中文
"""

def _build_weekly_prompt(
    *,
    display_label: str,
    analysis_result: dict,
    recommendation: dict,
    profile_summary: str,
    user_preference: str,
    task_summary: str,
) -> str:

    stress_average = _format_float_value(analysis_result.get("stress_average"))
    focus_average = _format_float_value(analysis_result.get("focus_average"))
    study_count = int(analysis_result.get("study_count") or 0)
    stress_trend = str(analysis_result.get("stress_trend") or "no data")
    focus_trend = str(analysis_result.get("focus_trend") or "no data")

    return f"""
你是一个基于数据做判断的学习分析者，不允许凭空猜测。

【用户长期状态】
{profile_summary}

【本周任务】
{task_summary}

【数据】
- 平均压力：{stress_average}
- 平均专注：{focus_average}
- 趋势：压力{stress_trend}，专注{focus_trend}
- 学习次数：{study_count}

⚠️ 强约束：
- 必须基于“数据变化”推断原因，不允许空泛描述
- 如果出现“学习次数多但专注下降”，必须解释为“可能存在疲劳或效率下降”
- 不允许说“可能是因为任务难”这种泛化推测
- 建议必须具体到行为（例如：缩短学习时长 / 调整节奏）
- 注意格式易读，按点输出1️⃣，2️⃣，3️⃣等

输出结构：
1️⃣ 一句话总结本周状态（必须包含趋势）
2️⃣ 用“数据之间的关系”解释原因
3️⃣ 给一个具体行为建议

输出：3句话
"""

# =====AI解析层=====
def _extract_doubao_response_text(data):
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None

# =====用户画像层=====
def _build_user_profile_summary(
    *,
    user_data: dict,
    reference_dates: list[str],
    current_stress_average: Optional[float],
    current_focus_average: Optional[float],
) -> dict:
    """从历史记录里提炼出用户画像（结构化 + 文本）"""

    if not reference_dates:
        return {
            "habit": [],
            "comparison": [],
            "baseline_focus": None,
            "baseline_stress": None,
            "learning_type": None,
            "text": "暂时还没有足够的历史记录来提炼这个人的个人节奏。"
        }

    baseline_stress_list = []
    baseline_focus_list = []
    active_hours = []
    daily_session_counts = []

    # ====== 1. 收集历史数据 ======
    for date_key in reference_dates:
        history_dict = user_data.get(date_key)
        if not history_dict or not history_dict.get("time") or not history_dict.get("hr"):
            continue

        for time_text in history_dict.get("time", []):
            try:
                active_hours.append(parse_clock_time(time_text).hour)
            except ValueError:
                continue

        focus_periods, score_list, _ = build_pomodoro_periods(history_dict)

        if score_list:
            baseline_stress_list.extend(float(item.get("stress") or 0.0) for item in score_list)
            baseline_focus_list.extend(float(item.get("focus") or 0.0) for item in score_list)
            daily_session_counts.append(len(score_list))
        elif focus_periods:
            baseline_stress_list.extend(float(period.stress) for period in focus_periods)
            baseline_focus_list.extend(float(period.focus) for period in focus_periods)
            daily_session_counts.append(len(focus_periods))

    # ====== 2. 没数据直接返回 ======
    if not baseline_stress_list or not baseline_focus_list:
        return {
            "habit": [],
            "comparison": [],
            "baseline_focus": None,
            "baseline_stress": None,
            "learning_type": None,
            "text": "暂时还没有足够稳定的历史记录来形成这个人的习惯画像。"
        }

    # ====== 3. 计算基线 ======
    baseline_stress = mean(baseline_stress_list)
    baseline_focus = mean(baseline_focus_list)
    session_mean = mean(daily_session_counts) if daily_session_counts else 0.0
    active_hour_mean = mean(active_hours) if active_hours else None

    habit_bits = []

    # ====== 4. 学习时间类型 ======
    learning_type = None
    if active_hour_mean is not None:
        if active_hour_mean < 11:
            learning_type = "morning"
            habit_bits.append("你通常更容易在上午把状态提起来")
        elif active_hour_mean < 16:
            learning_type = "afternoon"
            habit_bits.append("你更常在下午慢慢进入状态")
        else:
            learning_type = "night"
            habit_bits.append("你多半要到晚上才更容易沉下来")

    # ====== 5. 专注能力 ======
    if baseline_focus >= 70:
        habit_bits.append("你的专注底子整体还不错")
    elif baseline_focus <= 45:
        habit_bits.append("你平时就比较容易被分神")
    else:
        habit_bits.append("你的专注起伏不算太夸张")

    # ====== 6. 压力状态 ======
    if baseline_stress >= 70:
        habit_bits.append("但学习一忙起来，压力也会跟着上去")
    elif baseline_stress <= 50:
        habit_bits.append("平时压力通常不算重")
    else:
        habit_bits.append("平时压力大多还在可控范围")

    # ====== 7. 学习结构 ======
    if session_mean >= 4:
        habit_bits.append("你通常能把学习拆成几段完成")
    elif session_mean <= 2:
        habit_bits.append("你更像是少量几段就能推进的人")

    # ====== 8. 和今天对比 ======
    comparison_bits = []

    if current_stress_average is not None:
        if current_stress_average > baseline_stress + 8:
            comparison_bits.append("今天比你平时更紧一点")
        elif current_stress_average < baseline_stress - 8:
            comparison_bits.append("今天比你平时松一些")
        else:
            comparison_bits.append("今天压力和你平时差不多")

    if current_focus_average is not None:
        if current_focus_average > baseline_focus + 8:
            comparison_bits.append("专注比你平时更在线")
        elif current_focus_average < baseline_focus - 8:
            comparison_bits.append("专注比你平时弱一点")
        else:
            comparison_bits.append("专注大体上和你平时差不多")

    # ====== 9. 生成文本（给AI或展示用） ======
    profile_sentence = "；".join(habit_bits)
    comparison_sentence = "；".join(comparison_bits)

    profile_text = profile_sentence
    if comparison_sentence:
        profile_text += "。" + comparison_sentence

    # ====== 10. 返回结构化结果 ======
    return {
        "habit": habit_bits,
        "comparison": comparison_bits,
        "baseline_focus": baseline_focus,
        "baseline_stress": baseline_stress,
        "learning_type": learning_type,
        "text": profile_text
    }

def _build_task_summary(
    user_id: str,
    task_date: str,
    selected_dates: Optional[list[str]] = None,
    user_data: Optional[dict] = None,
) -> str:
    """提炼用户今天或本周的任务描述。"""
    if selected_dates and user_data:
        task_lines: list[str] = []
        for date_key in selected_dates:
            row = get_user_daily_task(user_id, date_key)
            if row and row[2]:
                task_lines.append(f"{format_short_cn_date(date_key)}：{str(row[2]).strip()}")
        if task_lines:
            return "；".join(task_lines)

    row = get_user_daily_task(user_id, task_date)
    if row and row[2]:
        return str(row[2]).strip()
    return "今天还没有写具体任务。"

# =====AI主函数=====
def build_ai_analysis(
    *,
    period: str,
    display_label: str,
    user_id: str,
    analysis_result: dict,
    recommendation: dict,
    profile_summary: str = "",
    user_preference: str = "",
    task_summary: str = "",
    focus_periods: list[FocusPeriod] | None = None,
    generate_report: bool = False,
) -> str:
    """
    使用豆包生成压力分析。若未配置密钥或请求失败，则回退到本地摘要。
    """
    # Normalize user_id for isolation and cache
    safe_user_id = str(user_id).strip() if user_id else "default"
    state = str(recommendation.get("state") or "正常状态")
    if focus_periods:
        normal_count = sum(1 for period in focus_periods if period.state == "正常")
        overload_count = sum(1 for period in focus_periods if period.state != "正常")
        if overload_count > 0 and normal_count > 0:
            summary_text = "今天有几段状态不错，也有几段明显更吃力，节奏不是完全一样的。"
        elif overload_count > 0:
            summary_text = "今天有几段明显更吃力，说明中间还是有些地方需要你多留意。"
        else:
            summary_text = "今天大部分时间状态都还算平稳。"
    else:
        summary_text = "当天整体状态可以先按当前判断来理解。"

    existing = get_ai_report(safe_user_id, display_label, period)
    if existing and not generate_report:
        return existing

    if not generate_report:
        return None

    cache_key = _make_ai_analysis_cache_key(
        period_label=period,
        display_label=display_label,
        user_id=safe_user_id,
        analysis_result=analysis_result,
        recommendation=recommendation,
        profile_summary=profile_summary,
        user_preference=user_preference,
        task_summary=task_summary,
        summary_text=summary_text,
        focus_periods=focus_periods,
    )
    cached_text = _AI_ANALYSIS_CACHE.get(cache_key)
    if cached_text and not generate_report:
        return cached_text

    api_key = os.getenv("ARK_API_KEY", os.getenv("DOUBAO_API_KEY", "")).strip()
    if not api_key:
        # 如果用户没有主动生成报告，不允许 fallback 自动生成
        if not generate_report:
            return None
        result = _build_local_ai_pressure_analysis(
            period_label=period,
            display_label=display_label,
            user_id=safe_user_id,
            analysis_result=analysis_result,
            recommendation=recommendation,
            task_summary=task_summary,
            summary_text=summary_text,
        )
        _AI_ANALYSIS_CACHE[cache_key] = result
        return result
    base_url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    model_name = os.getenv("DOUBAO_MODEL", "Doubao-pro-32k").strip()

    # prompt logic
    if period == "day":
        prompt = _build_daily_prompt(
            display_label=display_label,
            analysis_result=analysis_result,
            recommendation=recommendation,
            profile_summary=profile_summary,
            user_preference=user_preference,
            task_summary=task_summary,
        )
    else:
        prompt = _build_weekly_prompt(
            display_label=display_label,
            analysis_result=analysis_result,
            recommendation=recommendation,
            profile_summary=profile_summary,
            user_preference=user_preference,
            task_summary=task_summary,
        )

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "你是一个严谨认真的学习复盘助手"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 150
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            base_url,
            json=payload,
            headers=headers,
            timeout=(3, 20)
        )
        response.raise_for_status()
        data = response.json()
        content = _extract_doubao_response_text(data)
        if content:
            try:
                save_ai_report(safe_user_id, display_label, period, content)
            except Exception as e:
                logger.warning(f"save_ai_report failed: {e}")
            _AI_ANALYSIS_CACHE[cache_key] = content
            return content
    except Exception as exc:
        logger.warning(
            "Doubao %s analysis failed for %s %s: %s",
            period,
            safe_user_id,
            display_label,
            exc,
        )

    # 如果用户没有主动生成报告，不允许 fallback 自动生成
    if not generate_report:
        return None
    result = _build_local_ai_pressure_analysis(
        period_label=period,
        display_label=display_label,
        user_id=safe_user_id,
        analysis_result=analysis_result,
        recommendation=recommendation,
        task_summary=task_summary,
        summary_text="\n\n".join(
            part
            for part in [
                profile_summary.strip(),
                user_preference.strip(),
                task_summary.strip(),
                summary_text.strip(),
            ]
            if part
        ),
    )
    _AI_ANALYSIS_CACHE[cache_key] = result
    return result

# =====特征工程层=====
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
    """按周一到周日输出 7 个日级专注评分点。"""
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
            _day_focus_periods, day_scores, _day_curve = build_pomodoro_periods(history_dict)
            day_values = [float(item.get("focus") or 0.0) for item in day_scores if item.get("focus") is not None]
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

# =====核心调度层=====
def build_daily_dashboard(
    user_id: Optional[str] = None,
    date: Optional[str] = None,
    period: str = "day",
    generate_report: bool = True
) -> DailyDashboard:
    daily_data = get_cached_hrv_data()
    if not daily_data:
        raise HTTPException(status_code=404, detail="No HRV data available")

    selected_user_id = str(user_id) if user_id is not None else sorted(daily_data.keys())[-1]
    if selected_user_id not in daily_data:
        raise HTTPException(status_code=404, detail=f"User not found: {selected_user_id}")

    user_data = daily_data[selected_user_id]
    available_dates = sorted(user_data.keys())
    if not available_dates:
        raise HTTPException(status_code=404, detail=f"No dates found for user {selected_user_id}")

    requested_date = str(date) if date is not None else available_dates[-1]

    # ====== 如果是周，允许用周内任一有数据日期做聚合，并在整周无数据时回退到最近一周 ======
    if period == "week":
        week_start, week_end = week_bounds(requested_date)
        selected_dates = [
            date_key
            for date_key in available_dates
            if week_start <= date_key <= week_end
        ]

        if not selected_dates:
            requested_dt = datetime.strptime(requested_date, "%Y-%m-%d")
            fallback_date = min(
                available_dates,
                key=lambda date_key: abs(datetime.strptime(date_key, "%Y-%m-%d") - requested_dt),
            )
            week_start, week_end = week_bounds(fallback_date)
            selected_dates = [
                date_key
                for date_key in available_dates
                if week_start <= date_key <= week_end
            ]
            target_date = fallback_date
        else:
            if requested_date in selected_dates:
                target_date = requested_date
            else:
                requested_dt = datetime.strptime(requested_date, "%Y-%m-%d")
                target_date = min(
                    selected_dates,
                    key=lambda date_key: abs(datetime.strptime(date_key, "%Y-%m-%d") - requested_dt),
                )

        return build_weekly_dashboard(
            selected_user_id,
            target_date,
            week_start,
            week_end,
            selected_dates,
            user_data,
        )

    if requested_date not in user_data:
        raise HTTPException(status_code=404, detail=f"Date not found for user {selected_user_id}: {requested_date}")

    target_date = requested_date

    # ====== 日数据 ======
    history_dict = user_data[target_date]

    preference_row = get_user_ai_preference(selected_user_id)
    user_preference = str(preference_row[1] or "").strip() if preference_row else ""

    task_row = get_user_daily_task(selected_user_id, target_date)
    user_daily_task = str(task_row[2] or "").strip() if task_row else ""

    focus_periods, score_list_per_pomodoro, pomodoro_trend_points = build_pomodoro_periods(history_dict)
    interval_minutes = sample_interval_minutes(history_dict["time"])
    trend_points = pomodoro_trend_points or build_hourly_trend_points(history_dict)

    analysis = LearningAnalysis()
    analysis_result = analysis.analyze_daily_learning(score_list_per_pomodoro)

    recommendation = RecommendationEngine().generate(analysis_result)
    report = ReportGenerator().generate(analysis_result, recommendation)

    # ====== AI ======
    ai_stress_analysis = None
    if period == "day":
        ai_stress_analysis = build_ai_analysis(
            period="day",
            display_label=target_date,
            user_id=selected_user_id,
            analysis_result=analysis_result,
            recommendation=recommendation,
            profile_summary="",
            user_preference=user_preference,
            task_summary=user_daily_task,
            focus_periods=focus_periods,
            generate_report=generate_report,
        )

    # ====== 返回日 ======
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
        ai_stress_analysis=ai_stress_analysis,
        user_ai_preference=user_preference,
        user_daily_task=user_daily_task,
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
    preference_row = get_user_ai_preference(user_id)
    user_preference = str(preference_row[1] or "").strip() if preference_row else ""
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
    current_task_row = get_user_daily_task(user_id, target_date)
    user_daily_task = str(current_task_row[2] or "").strip() if current_task_row else ""
    week_display_label = f"{format_short_cn_date(week_start)} - {format_short_cn_date(week_end)}"
    existing_week_report = get_ai_report(user_id, week_display_label, "week")
    ai_stress_analysis = build_ai_analysis(
        period="week",
        display_label=week_display_label,
        user_id=user_id,
        analysis_result=analysis_result,
        recommendation=recommendation,
        profile_summary="",
        user_preference=user_preference,
        task_summary=_build_task_summary(user_id, target_date, selected_dates=selected_dates, user_data=user_data),
        focus_periods=weekly_focus_periods,
        generate_report=not bool(existing_week_report),
    )
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
        range_label=week_display_label,
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
        ai_stress_analysis=ai_stress_analysis,
        user_ai_preference=user_preference,
        user_daily_task=user_daily_task,
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
    generate_report: bool = Query(default=False, description="是否生成每日 AI 报告"),
):
    """
    返回前端统计页所需的日统计数据。
    """
    return build_daily_dashboard(user_id, date, period, generate_report)


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
