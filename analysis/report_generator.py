"""
    每日总结的最终呈现格式，并接入豆包
"""
import requests


class ReportGenerator:
    def __init__(self):
        pass

    @staticmethod
    def generate_report(analysis_dict, recommendation_dict):
        daily_report = {}
        daily_report["study_count"] = analysis_dict["study_count"]
        daily_report["stress_average"] = analysis_dict["stress_average"]
        daily_report["focus_average"] = analysis_dict["focus_average"]
        daily_report["state"] = recommendation_dict["state"]
        daily_report["message"] = recommendation_dict["message"]
        daily_report["advice"] = recommendation_dict["advice"]

        return daily_report

    def generate(self, analysis_dict, recommendation_dict):
        """
        向后兼容 main.py 的调用方式。
        """
        return self.generate_report(analysis_dict, recommendation_dict)

