from src.data_loader import load_and_process_hrv_data
from analysis.learning_analysis import LearningAnalysis
from analysis.focus_model import FocusModel
from analysis.recommendation_engine import RecommendationEngine
from analysis.report_generator import ReportGenerator
from pathlib import Path


def main():
    # 1. 数据
    raw_data_path = Path("data/raw/virtual_hrv_extended.csv")
    if not raw_data_path.exists():
        raw_data_path = Path("data/raw/virtual_hrv_multisubject.csv")
    if not raw_data_path.exists():
        raw_data_path = Path("data/raw/senor_hrv_filtered.csv")

    daily_data = load_and_process_hrv_data(str(raw_data_path))
    if not daily_data:
        print("没有可用数据")
        return

    # 2. 模型：先选一个用户，再取该用户最新一天的数据
    latest_user = sorted(daily_data.keys())[-1]
    user_daily_data = daily_data[latest_user]
    latest_date = sorted(user_daily_data.keys())[-1]
    history_dict = user_daily_data[latest_date]
    model = FocusModel()
    focus_result = model.run(history_dict)
    score_list_per_pomodoro = focus_result["score_list_per_pomodoro"]

    # 3. 分析：对番茄钟评分做日级分析
    analysis = LearningAnalysis()
    analysis_result = analysis.analyze_daily_learning(score_list_per_pomodoro)

    # 4. 推荐
    recommender = RecommendationEngine()
    recommendation = recommender.generate(analysis_result)

    # 5. 报告
    reporter = ReportGenerator()
    report = reporter.generate(analysis_result, recommendation)
    report["user_id"] = latest_user
    report["date"] = latest_date
    print(report)


if __name__ == "__main__":
    main()
