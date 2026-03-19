"""
    每日学习总结模块
    1. 番茄钟数量：今天学了几次
    2. 平均专注度：学习质量
    3. 平均压力：今日精神负担
    4. 关注趋势：是否越来越疲惫
    5. 压力趋势：是否越来越紧张
"""

class LearningAnalysis:
    def __init__(self):
        pass

    def analyze_daily_learning(self, score_list_per_pomodoro):
        """用于计算并分析基础数据"""

        analysis_dict = {}
        analysis_dict["study_count"] = 0
        analysis_dict["stress_average"] = None
        analysis_dict["focus_average"] = None
        analysis_dict["stress_trend"] = "no data"
        analysis_dict["focus_trend"] = "no data"

        if len(score_list_per_pomodoro) == 0:
            return analysis_dict

        daily_stress_list = []
        daily_focus_list = []

        for score in score_list_per_pomodoro:
            daily_stress_list.append(score['stress'])
            daily_focus_list.append(score['focus'])

        # 计算学习次数
        study_count = len(score_list_per_pomodoro)
        analysis_dict["study_count"] = study_count

        # 计算平均压力和平均专注度
        daily_stress_avg = sum(daily_stress_list) / len(daily_stress_list)
        daily_focus_avg = sum(daily_focus_list) / len(daily_focus_list)
        analysis_dict["stress_average"] = daily_stress_avg
        analysis_dict["focus_average"] = daily_focus_avg

        # 分析趋势（大于3个数据可分析）
        # 压力
        stress_trend = 'insufficient data'
        n_stress = len(daily_stress_list)
        if n_stress > 3:
            x_list = range(n_stress)

            sum_x = sum(x_list)
            sum_y = sum(daily_stress_list)

            sum_xy = 0
            for x, y in zip(x_list, daily_stress_list):
                sum_xy += x * y

            sum_x2 = 0
            for x in x_list:
                sum_x2 += x ** 2

            stress_slope = (n_stress * sum_xy - sum_x*sum_y)/(n_stress * sum_x2 - sum_x**2)

            if stress_slope > 0:
                stress_trend = "increasing"
            elif stress_slope < 0:
                stress_trend = "decreasing"
            else:
                stress_trend = "stable"
        analysis_dict["stress_trend"] = stress_trend

        focus_trend = 'insufficient data'
        n_focus = len(daily_focus_list)
        if n_focus > 3:
            x_list = range(n_focus)
            sum_x = sum(x_list)
            sum_y = sum(daily_focus_list)

            sum_xy = 0
            for x, y in zip(x_list, daily_focus_list):
                sum_xy += x * y

            sum_x2 = 0
            for x in x_list:
                sum_x2 += x ** 2

            focus_slope = (n_focus * sum_xy - sum_x * sum_y) / (n_focus * sum_x2 - sum_x ** 2)

            if focus_slope > 0:
                focus_trend = "improving"
            elif focus_slope < 0:
                focus_trend = "declining"
            else:
                focus_trend = "stable"
        analysis_dict["focus_trend"] = focus_trend

        return analysis_dict
