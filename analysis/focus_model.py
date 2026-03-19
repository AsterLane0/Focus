"""
 HRV - Stress & Focus
 -
 基本原则：
    HRV高-情绪调节好-压力较低-专注力高
    专注力在中等压力时最佳
    本程序选取RMSSD作为测试指标

    番茄钟为25分钟一次完成，手表数据1分钟记一次，5分钟为一个窗口
 公式：
    rr = 60000 / hr
    stress =
    focus =

 2025-3-15
"""
import math
import statistics
from datetime import datetime



class FocusModel:
    def __init__(self):
        # RMSSD normalization
        self.normal_max_log = 4.8
        self.normal_min_log = 2.3

        # focus curve parameter
        self.optimal_stress = 50

    def sort_data_by_time(self, history_dict):
        """
        将数据按照时间重新排序
        {
            "time":[t1,t2,t3,...],
            "hr":[72，75，70，...]
        }
        转化为
        [
            (t1, hr1), (t2, hr2), ...
        ]
        """
        history_list = list(zip(history_dict["time"], history_dict["hr"]))
        # 排序
        history_list.sort(key=lambda x: x[0])
        return history_list

    def split_5mins_window_list(self, history_list):
        """
        将数据按5分钟分割为一个小窗口
        """
        window_list = []
        current_list = []
        start_time = datetime.strptime(history_list[0][0], '%H:%M')

        for time, hr in history_list:
            current_time = datetime.strptime(time, "%H:%M")
            diff = (current_time - start_time).seconds / 60
            if diff < 5:
                current_list.append((time, hr))
            else:
                window_list.append(current_list)
                current_list = []
                current_list.append((time, hr))
                start_time = current_time

        if current_list:
            window_list.append(current_list)

        return window_list

    def filter_time_intervals(self, window_list):
        """
        规则：每个5分钟窗口相邻数据的时间间隔：45s ≤ Δt ≤ 75s
        用于选取每个5分钟窗口的最佳数据点
        """
        filtered_window_list = []

        # 检查数据集间隔
        for five_mins_list in window_list:
            if not five_mins_list:
                continue

            current_segment_list = []
            best_segment_list = []

            # 第一个连续列表的开始
            first_time = five_mins_list[0][0]
            first_hr = five_mins_list[0][1]
            current_segment_list.append((first_time, first_hr))

            for i in range(len(five_mins_list) - 1):
                current_time = datetime.strptime(five_mins_list[i][0], '%H:%M')
                next_time = datetime.strptime(five_mins_list[i + 1][0], '%H:%M')

                diff = (next_time - current_time).seconds
                if 45 <= diff <= 75:
                    current_segment_list.append(five_mins_list[i + 1])
                else:
                    if len(best_segment_list) < len(current_segment_list):
                        best_segment_list = current_segment_list.copy()
                    # 下一个连续列表的开始
                    current_segment_list = []
                    next_time = five_mins_list[i + 1][0]
                    next_hr = five_mins_list[i + 1][1]
                    current_segment_list.append((next_time, next_hr))

            if len(best_segment_list) < len(current_segment_list):
                best_segment_list = current_segment_list.copy()
            # 检查元素个数
            if len(best_segment_list) >= 3:
                filtered_window_list.append(best_segment_list.copy())

        return filtered_window_list

    def hr_to_rr(self, window):
        """
        将每个窗口的心率（BPM）转化为平均心跳时间间隔RR（ms）
        """
        rr_list_per_window = []
        for time, hr in window:
            rr = 60000 / hr
            rr_list_per_window.append(rr)
        return rr_list_per_window

    def rr_to_rmssd(self, rr_list_per_window):
        """
        计算RMSSD
        :param rr_list_per_window:
        :return: rmssd_list
        """
        diff_list = []
        for i in range(len(rr_list_per_window) - 1):
            diff = rr_list_per_window[i + 1] - rr_list_per_window[i]
            diff *= diff
            diff_list.append(diff)

        rmssd_per_window = math.sqrt(statistics.mean(diff_list))
        return rmssd_per_window

    def rmssd_to_stress(self, rmssd_per_window):
        """
        对RMSSD数据进行归一化，并通过函数计算Stress
        """
        log_rmssd = math.log(rmssd_per_window)
        normalized = (log_rmssd - self.normal_min_log) / (self.normal_max_log - self.normal_min_log)
        stress_per_window = 100 * (1 - normalized)
        stress_per_window = max(0, min(stress_per_window, 100))
        return stress_per_window

    def stress_to_focus(self, stress_per_window):
        """
        由于压力和专注度为一个倒U形关系，通过二次函数构造专注度模型
        """
        focus_per_window = 100 - 0.04 * (stress_per_window - self.optimal_stress) ** 2
        focus_per_window = max(0, min(focus_per_window, 100))
        return focus_per_window

    def calculate_focus_from_hr(self, history_dict):
        """
        将传入数据转化为有序列表->将传入数据分割为窗口->去掉不合理数据
            ->将hr数据转为focus和stress指标->输出[(time, stress, focus), (time, stress, focus)...]
        """
        history_list = self.sort_data_by_time(history_dict)
        history_list = self.split_5mins_window_list(history_list)
        history_list = self.filter_time_intervals(history_list)

        result_list = []
        for window in history_list:

            hr_list_per_window = self.hr_to_rr(window)
            rmssd_per_window = self.rr_to_rmssd(hr_list_per_window)
            stress_per_window = self.rmssd_to_stress(rmssd_per_window)
            focus_per_window = self.stress_to_focus(stress_per_window)

            window_time = window[0][0]
            result_list.append((window_time, stress_per_window, focus_per_window))

        return result_list

    def calculate_pomodoro_score(self, result_list):
        """
        将无番茄钟分组的数据按照番茄钟（25分钟）分组，同时输出每组的focus，stress的平均值
        window: [(time, stress, focus), (time, stress, focus)]
        转化为
        [
            0:[第一组番茄钟((time, stress, focus), (time, stress, focus))]
            1:[第二组番茄钟]
        ]
        以及
        [
            (第一个番茄钟({time}, stress, focus)))
            (第二个番茄钟({time}, stress, focus)))
        ]
        """
        all_data_dict_per_pomodoro = {}
        start_time_obj = datetime.strptime(result_list[0][0], "%H:%M")

        for time, stress, focus in result_list:
            time_obj = datetime.strptime(time, "%H:%M")
            diff_minutes = (time_obj - start_time_obj).seconds // 60
            pomodoro_index = diff_minutes // 25

            if pomodoro_index not in all_data_dict_per_pomodoro:
                all_data_dict_per_pomodoro[pomodoro_index] = []
            all_data_dict_per_pomodoro[pomodoro_index].append((time, stress, focus))

        score_list_per_pomodoro = []
        for index, pomodoro in all_data_dict_per_pomodoro.items():
            start_time = pomodoro[0][0]
            end_time = pomodoro[-1][0]

            stress_per_pomodoro = []
            focus_per_pomodoro = []

            for time, stress, focus in pomodoro:
                stress_per_pomodoro.append(stress)
                focus_per_pomodoro.append(focus)

            stress_avg = sum(stress_per_pomodoro) / len(stress_per_pomodoro)
            focus_avg = sum(focus_per_pomodoro) / len(focus_per_pomodoro)

            data_dict_per_pomodoro = {}

            data_dict_per_pomodoro["start_time"] = start_time
            data_dict_per_pomodoro["end_time"] = end_time
            data_dict_per_pomodoro["stress"] = stress_avg
            data_dict_per_pomodoro["focus"] = focus_avg

            score_list_per_pomodoro.append(data_dict_per_pomodoro)

        return all_data_dict_per_pomodoro, score_list_per_pomodoro


if __name__ == "__main__":
    model = FocusModel()
    history_dict = {
        "time": [
            "22:40", "22:41", "22:42", "22:43", "22:44", "22:45", "22:46", "22:47", "22:48", "22:49",
            "22:50", "22:51", "22:52", "22:53", "22:54", "22:55", "22:56", "22:57", "22:58", "22:59",
            "23:00", "23:01", "23:02", "23:03", "23:04", "23:05", "23:06", "23:07", "23:08", "23:09",
            "23:10", "23:11", "23:12", "23:13", "23:14", "23:15", "23:16", "23:17", "23:18", "23:19",
            "23:20", "23:21", "23:22", "23:23", "23:24", "23:25", "23:26", "23:27", "23:28", "23:29",
            "23:30", "23:31", "23:32", "23:33", "23:34", "23:35", "23:36", "23:37", "23:38", "23:39"
        ],
        "hr": [
            72, 71, 73, 74, 72, 70, 69, 71, 72, 73,
            74, 75, 73, 72, 71, 70, 69, 70, 71, 72,
            73, 74, 75, 76, 74, 73, 72, 71, 70, 69,
            70, 71, 72, 73, 74, 75, 74, 73, 72, 71,
            70, 69, 70, 71, 72, 73, 74, 75, 76, 75,
            74, 73, 72, 71, 70, 69, 70, 71, 72, 73
        ]
    }

    result_list = model.calculate_focus_from_hr(history_dict)
    all_data_per_pomodoro, score_list_per_pomodoro = model.calculate_pomodoro_score(result_list)
    print(all_data_per_pomodoro)
    print(score_list_per_pomodoro)