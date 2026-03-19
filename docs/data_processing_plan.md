# Focus 项目：HRV 数据获取与处理计划

> 基于 Nature Scientific Data 数据集的心率变异性(HRV)与睡眠数据处理方案

---

## 一、数据集概览
| 属性 | 值 |
|------|-----|
| **数据来源** | Nature Scientific Data (Figshare) |
| **DOI** | https://doi.org/10.6084/m9.figshare.28509740 |
| **参与者** | 49人 (21-43岁, 51%女性) |
| **采集周期** | 4周连续数据 |
| **采样频率** | 10Hz (100ms) |
| **设备** | Samsung Galaxy Watch Active 2 |
| **数据量** | 33,600小时 (平均672小时/人) |

---

## 二、数据文件结构

### 2.1 核心文件

| 文件名 | 内容 | 大小 | 与Focus项目的关联 |
|--------|------|------|-------------------|
| `survey.csv` | 人口统计学 + 临床问卷(PHQ9, GAD7, ISI) | ~50KB | 压力标签参考 |
| `sensor_hrv.csv` | 传感器数据 + HRV特征(5分钟间隔) | ~80MB | 核心数据 |
| `sensor_hrv_filtered.csv` | 过滤后的HRV数据 (missingness < 0.35) | ~60MB | ✅ 推荐使用 |
| `sleep_diary.csv` | 每日睡眠日记 | ~100KB | 睡眠辅助分析 |

### 2.2 原始数据 (可选)

| 文件名 | 内容 |
|--------|------|
| `raw_data/ppg.csv.gz` | 原始PPG信号 |
| `raw_data/hrm.csv.gz` | 心率监测数据 |
| `raw_data/acc.csv.gz` | 加速度计数据 |
| `raw_data/gyr.csv.gz` | 陀螺仪数据 |

---

## 三、关键HRV特征

### 3.1 时域特征 (Time Domain)

| 特征 | 描述 | 推荐程度 |
|------|------|----------|
| **RMSSD** | 相邻RR间期差值均方根 | ⭐⭐⭐ 推荐 |
| **SDNN** | RR间期标准差 | ⭐⭐ |
| **SDSD** | 相邻RR间期标准差 | ⭐⭐ |
| **PNN20/PNN50** | 相邻间期差>20ms/50ms的比例 | ⭐ |

### 3.2 频域特征 (Frequency Domain)

| 特征 | 描述 | 推荐程度 |
|------|------|----------|
| **LF** | 低频功率 (0.04-0.15Hz) | ⭐⭐ |
| **HF** | 高频功率 (0.15-0.4Hz) | ⭐⭐ |
| **LF/HF** | 交感/副交感神经平衡 | ⭐⭐⭐ 压力指标 |

---

## 四、数据获取步骤

### 4.1 下载数据

1. 访问 Figshare 数据仓库: https://doi.org/10.6084/m9.figshare.28509740
2. 下载以下文件:
   - `sensor_hrv_filtered.csv` (推荐先使用)
   - `sleep_diary.csv`
   - `survey.csv`
3. 解压并存放至项目目录

### 4.2 目录结构

```
Focus/
├── data/
│   ├── raw/
│   │   ├── sensor_hrv_filtered.csv   # HRV数据
│   │   ├── sleep_diary.csv           # 睡眠日记
│   │   └── survey.csv                # 问卷数据
│   └── processed/                      # 处理后数据(生成)
├── src/
│   ├── data_loader.py                # 数据加载
│   ├── preprocessing.py              # 数据清洗
│   ├── hrv_analyzer.py               # HRV分析
│   ├── stress_calculator.py          # Stress计算
│   └── sleep_integration.py          # 睡眠数据整合
├── notebooks/
│   └── baseline_analysis.ipynb        # Baseline分析
└── docs/
    └── data_processing_plan.md        # 本文档
```

---

## 五、数据处理 Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                      数据处理 Pipeline                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │  1.数据加载  │ →  │  2.数据清洗  │ →  │  3.特征提取  │    │
│  │  pandas      │    │  过滤/处理   │    │  RMSSD/LF/HF │    │
│  └──────────────┘    └──────────────┘    └──────────────┘    │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │  4.睡眠整合  │ →  │  5.Baseline  │ →  │  6.Stress   │    │
│  │  关联睡眠    │    │  计算         │    │  计算         │    │
│  └──────────────┘    └──────────────┘    └──────────────┘    │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────────────────────────────────────────────┐     │
│  │                    7. 输出                            │     │
│  │         标准化格式 → 后端API / 模型输入              │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.1 数据加载

```python
import pandas as pd

# 加载HRV数据
hrv_df = pd.read_csv('data/raw/sensor_hrv_filtered.csv')

# 加载睡眠数据
sleep_df = pd.read_csv('data/raw/sleep_diary.csv')

# 加载问卷数据
survey_df = pd.read_csv('data/raw/survey.csv')
```

### 5.2 数据清洗

```python
def clean_hrv_data(df, missingness_threshold=0.35):
    """
    清洗HRV数据
    - 过滤missingness_score > threshold的记录
    - 处理缺失值
    - 时间戳转换
    """
    # 过滤低质量数据
    df_clean = df[df['missingness_score'] <= missingness_threshold].copy()
    
    # 转换时间戳 (epoch ms → datetime)
    df_clean['datetime'] = pd.to_datetime(df_clean['ts_start'], unit='ms')
    
    return df_clean
```

### 5.3 特征提取

```python
def extract_hrv_features(df):
    """
    提取关键HRV特征
    - RMSSD: 推荐用于压力计算
    - LF/HF: 交感副交感平衡
    """
    features = {
        'rmssd': df['rmssd'].mean(),
        'sdnn': df['sdnn'].mean(),
        'lf_hf_ratio': df['lf'] / df['hf'],
        'heart_rate': df['heart_rate'].mean()
    }
    return features
```

---

## 六、Baseline 计算方案

### 6.1 推荐方法: 7天滑动平均

```python
def calculate_baseline_rmssd(df, window_days=7):
    """
    计算RMSSD baseline
    使用7天滑动平均
    """
    df_sorted = df.sort_values('datetime')
    df_sorted.set_index('datetime', inplace=True)
    
    # 按天聚合RMSSD均值
    daily_rmssd = df_sorted['rmssd'].resample('D').mean()
    
    # 7天滑动平均
    baseline = daily_rmssd.rolling(window=window_days, min_periods=1).mean()
    
    return baseline.iloc[-1]  # 返回最新的baseline
```

### 6.2 备选方法: 夜间静息RMSSD

```python
def calculate_resting_rmssd(df, night_hours=(0, 6)):
    """
    计算静息RMSSD
    使用夜间(0:00-6:00)最低RMSSD
    """
    df['hour'] = df['datetime'].dt.hour
    
    # 筛选夜间数据
    night_data = df[(df['hour'] >= night_hours[0]) & 
                    (df['hour'] < night_hours[1])]
    
    # 取最低值作为静息baseline
    resting_baseline = night_data['rmssd'].min()
    
    return resting_baseline
```

### 6.3 方法对比

| 方法 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| 7天滑动平均 | 稳定、反映长期趋势 | 需要连续数据 | 日常监测 ✅ |
| 夜间静息RMSSD | 更准确反映副交感神经 | 需要夜间数据 | 精确评估 |
| 分位数法 | 抗极端值 | 可能遗漏重要信息 | 嘈杂数据 |

---

## 七、Stress 计算方案

### 7.1 基于HRV的Stress计算

```python
def calculate_stress(rmssd, baseline_rmssd, lf_hf_ratio=None):
    """
    计算Stress值 (0-100)
    
    原理:
    - RMSSD下降 → 压力上升
    - LF/HF上升 → 交感神经活跃 → 压力上升
    """
    # 基于RMSSD的stress
    rmssd_ratio = rmssd / baseline_rmssd
    
    # RMSSD下降比例转换为stress (0-100)
    stress_rmssd = max(0, min(100, (1 - rmssd_ratio) * 100))
    
    # 如果有LF/HF数据，结合计算
    if lf_hf_ratio is not None:
        # LF/HF正常范围约0.5-2.0
        lf_hf_stress = max(0, min(100, (lf_hf_ratio - 1) * 50))
        
        # 综合stress
        stress = 0.7 * stress_rmssd + 0.3 * lf_hf_stress
    else:
        stress = stress_rmssd
    
    return round(stress, 2)
```

### 7.2 睡眠辅助修正

```python
def adjust_stress_with_sleep(stress, sleep_quality):
    """
    基于睡眠质量调整stress
    - 睡眠效率低 → stress增加
    - WASO(夜间醒来时间)长 → stress增加
    """
    if sleep_quality < 0.85:  # 睡眠效率 < 85%
        stress *= 1.1  # 增加10%
    
    return min(100, stress)
```

---

## 八、输出格式

### 8.1 处理后数据格式

```python
# 输出的标准化格式
processed_data = {
    'user_id': 'p001',
    'datetime': '2025-03-15 10:00:00',
    'rmssd': 45.2,           # ms
    'sdnn': 52.1,            # ms
    'lf_hf_ratio': 1.2,
    'heart_rate': 72,        # bpm
    'stress': 35.5,          # 0-100
    'baseline_rmssd': 48.0,  # 7天baseline
    'sleep_efficiency': 0.92,
    'sleep_duration': 7.5,   # hours
    'date': '2025-03-15'
}
```

### 8.2 存储

```python
# 保存处理后的数据
output_df.to_csv('data/processed/stress_data.csv', index=False)

# 定期更新baseline
baseline_df.to_csv('data/processed/baseline.csv', index=False)
```

---

## 九、注意事项

1. **数据质量**: 使用 `sensor_hrv_filtered.csv` 避免噪声数据
2. **隐私保护**: 数据已匿名化，但仍需遵守数据使用协议
3. **时间对齐**: 确保HRV数据与睡眠数据日期对齐
4. **Baseline更新**: 建议每周更新一次baseline

---

## 十、参考文献

1. Baigutanova, A. et al. (2025). A continuous real-world dataset comprising wearable-based heart rate variability alongside sleep diaries. *Scientific Data*, 12, 1474.
2. Shaffer, F. & Ginsberg, J. P. (2017). An overview of heart rate variability metrics and norms. *Frontiers in Public Health*, 5, 258.
3. Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology. (1996). Heart rate variability: standards of measurement, physiological interpretation and clinical use. *Circulation*, 93, 1043-1065.

---

> 文档创建时间: 2026-03-18
> 最后更新: 2026-03-18
