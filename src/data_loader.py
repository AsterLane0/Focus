import pandas as pd
import json
from pathlib import Path


def load_and_process_hrv_data(filepath: str, output_dir: str = "data/processed"):
    """
    加载 HRV 数据并按 user_id + date 生成字典格式输出

    Args:
        filepath: sensor_hrv_filtered.csv 文件路径
        output_dir: 输出目录

    Returns:
        dict: {"user_id": {"YYYY-MM-DD": {"time": [...], "hr": [...]}}}
    """
    df = pd.read_csv(filepath)

    if "user_id" not in df.columns:
        raise ValueError("CSV 文件缺少 user_id 列")

    df["user_id"] = df["user_id"].astype(str)
    df["datetime"] = pd.to_datetime(df["ts_start"], unit="ms")
    df["date"] = df["datetime"].dt.strftime("%Y-%m-%d")
    df["time"] = df["datetime"].dt.strftime("%H:%M")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    daily_data = {}

    for (user_id, date), group in df.groupby(["user_id", "date"]):
        group_sorted = group.sort_values("ts_start")

        if user_id not in daily_data:
            daily_data[user_id] = {}

        daily_data[user_id][date] = {
            "time": group_sorted["time"].tolist(),
            "hr": group_sorted["HR"].tolist(),
        }

    output_file = output_path / "daily_hrv_data.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(daily_data, f, ensure_ascii=False, indent=2)

    print(f"数据已保存至: {output_file}")
    print(f"共处理 {len(daily_data)} 个用户的数据")

    return daily_data


def get_daily_hrv(data: dict, user_id: str, date: str) -> dict:
    """
    获取指定用户、指定日期的 HRV 数据

    Args:
        data: daily_hrv_data 字典
        user_id: 用户 ID
        date: 日期字符串 "YYYY-MM-DD"

    Returns:
        dict: {"time": [...], "hr": [...]}
    """
    user_data = data.get(str(user_id), {})
    return user_data.get(date, {"time": [], "hr": []})
