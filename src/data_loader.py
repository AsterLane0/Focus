import pandas as pd
import json
from pathlib import Path


def load_and_process_hrv_data(filepath: str, output_dir: str = "data/processed"):
    """
    加载HRV数据并按天生成字典格式输出

    Args:
        filepath: sensor_hrv_filtered.csv 文件路径
        output_dir: 输出目录

    Returns:
        dict: 每天的数据字典 {"YYYY-MM-DD": {"time": [...], "hr": [...]}}
    """
    df = pd.read_csv(filepath)

    df["datetime"] = pd.to_datetime(df["ts_start"], unit="ms")
    df["date"] = df["datetime"].dt.strftime("%Y-%m-%d")
    df["time"] = df["datetime"].dt.strftime("%H:%M")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    daily_data = {}

    for date, group in df.groupby("date"):
        group_sorted = group.sort_values("ts_start")

        daily_data[date] = {
            "time": group_sorted["time"].tolist(),
            "hr": group_sorted["HR"].tolist(),
        }

    output_file = output_path / "daily_hrv_data.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(daily_data, f, ensure_ascii=False, indent=2)

    print(f"数据已保存至: {output_file}")
    print(f"共处理 {len(daily_data)} 天的数据")

    return daily_data


def get_daily_hrv(data: dict, date: str) -> dict:
    """
    获取指定日期的HRV数据

    Args:
        data: daily_hrv_data 字典
        date: 日期字符串 "YYYY-MM-DD"

    Returns:
        dict: {"time": [...], "hr": [...]}
    """
    return data.get(date, {"time": [], "hr": []})


if __name__ == "__main__":
    data_path = "data/raw/sensor_hrv_filtered.csv"

    daily_hrv = load_and_process_hrv_data(data_path)

    print("\n示例数据 (第一天):")
    first_date = list(daily_hrv.keys())[0]
    print(f"日期: {first_date}")
    sample_data = daily_hrv[first_date]
    print(f"time: {sample_data['time'][:5]}...")
    print(f"hr: {sample_data['hr'][:5]}...")
