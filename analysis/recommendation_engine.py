"""
    用于总结每日数据并生成状态、描述和建议
"""

class RecommendationEngine:
    def __init__(self):
        self.high_focus_threshold = 70
        self.low_focus_threshold = 40
        self.high_stress_threshold = 80
        self.low_stress_threshold = 60

    def create_recommendation_over_day(self, analysis_dict):
        recommendation_dict = {}
        recommendation_dict["state"] = None
        recommendation_dict["message"] = None
        recommendation_dict["advice"] = None

        # 从analysis_dict里取出数据
        stress_average = analysis_dict["stress_average"]
        focus_average = analysis_dict["focus_average"]
        stress_trend = analysis_dict["stress_trend"]
        focus_trend = analysis_dict["focus_trend"]

        # 判断状态
        # 1. 高压：stress高 focus低
        if stress_average > self.low_stress_threshold and focus_average < self.low_focus_threshold:
            recommendation_dict["state"] = "压力过载"
            recommendation_dict["message"] = "🔴压力过高，专注度过低"
            recommendation_dict["advice"] = "注意压力和注意力！请尝试调整一下吧"

        # 2. 疲惫：stress高 focus下降
        elif stress_average > self.high_stress_threshold and focus_trend == "declining":
            recommendation_dict["state"] = "疲惫状态"
            recommendation_dict["message"] = "🟡压力过高，专注度下降"
            recommendation_dict["advice"] = "休息一下吧今天不要太累了，深呼吸。"

        # 3. 状态优秀：stress低，focus高
        elif stress_average < self.low_stress_threshold and focus_average > self.high_focus_threshold:
            recommendation_dict["state"] = "状态优秀"
            recommendation_dict["message"] = "🟢压力低，专注度高"
            recommendation_dict["advice"] = "优秀又专注的一天！继续保持！"
            if focus_trend == "declining":
                recommendation_dict["message"] += "，专注度呈下降趋势"
                recommendation_dict["advice"] += "但请注意专注力有下降问题"
            elif focus_trend == "improving":
                recommendation_dict["message"] += "，专注度呈上升趋势"
            else:
                recommendation_dict["message"] += "，专注度稳定"

        # 4. 状态良好：stress中等 focus高
        elif stress_average < self.high_stress_threshold and focus_average > self.high_focus_threshold:
            recommendation_dict["state"] = "状态良好"
            recommendation_dict["message"] = "🟣压力正常，专注度高"
            recommendation_dict["advice"] = "高效又专注的一天，明天也要加油！"
            if focus_trend == "declining":
                recommendation_dict["message"] += "，专注度呈下降趋势"
                recommendation_dict["advice"] += "但请注意专注力有下降问题"

        # 5. 其他状态
        else:
            recommendation_dict["state"] = "正常状态"
            recommendation_dict["message"] = "🔵压力正常，专注度正常"
            recommendation_dict["advice"] = "继续保持当前学习节奏，加油！"
            if focus_trend == "declining":
                recommendation_dict["message"] += "，专注度呈下降趋势"
                recommendation_dict["advice"] += "但请注意专注力有下降问题"
            elif focus_trend == "improving":
                recommendation_dict["message"] += "，专注度呈上升趋势"
            else:
                recommendation_dict["message"] += "，专注度稳定"

        return recommendation_dict