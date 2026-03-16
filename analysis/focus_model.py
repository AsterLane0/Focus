"""
 HRV - Stress & Focus
 -
 基本原则：
    HRV高-情绪调节好-压力较低-专注力高
    专注力在中等压力时最佳
    本程序选取RMSSD作为测试指标

    番茄钟为25分钟一次完成，手表数据
 公式：

 2025-3-15
"""
import math
import statistics

def hr_to_rr(hr_dict):
    """
    将心率（BPM）转化为平均心跳时间间隔RR（ms）
    """
    rr_list = []
    for hr in hr_dict['hr']:
        rr = (60 * 1000) / hr
        rr_list.append(rr)
    return rr_list

def calculate_rmssd(rr_list):
    """
    计算RMSSD
    :param rr_list:
    :return: rmssd_list
    """
    diff_list = []
    for i in range(len(rr_list) - 1):
        diff = rr_list[i + 1] - rr_list[i]
        diff *= diff
        diff_list.append(diff)

    rmssd = math.sqrt(statistics.mean(diff_list))
    return rmssd

def rmssd_to_stress:



class FocusScoreModel:
    def __init__(self, ):