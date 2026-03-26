# Focus

Focus 是一个面向学习场景的专注度分析桌面应用。项目把 HRV 数据分析、学习状态判断、AI 文本总结和 Electron 桌面端整合在一起，方便在比赛展示时以“可运行产品”的形式呈现。

## 项目目标

- 基于 HRV 数据估计学习过程中的压力与专注度变化
- 以日 / 周两个粒度展示学习状态
- 输出结构化建议与 AI 学习分析
- 通过 Electron 提供桌面端交互界面

## 项目结构

```text
Focus/
├─ main.py                    # 本地串联演示入口
├─ requirements.txt           # Python 依赖
├─ src/
│  └─ data_loader.py          # 数据读取与预处理
├─ analysis/
│  ├─ focus_model.py          # HRV -> 压力 / 专注度模型
│  ├─ learning_analysis.py    # 日 / 周学习分析逻辑
│  ├─ recommendation_engine.py# 状态判断与建议生成
│  └─ report_generator.py     # 报告结构整理
├─ backend/
│  ├─ api_server.py           # FastAPI 后端
│  ├─ database.py             # SQLite 持久化
│  └─ __init__.py
├─ data/
│  ├─ raw/                    # 原始样例数据
│  └─ processed/              # 运行生成数据
├─ docs/
│  └─ PROJECT_STRUCTURE.md    # 结构说明文档
├─ electron-dist/
│  ├─ index.html              # Electron 前端页面
│  ├─ main.js                 # Electron 主进程
│  ├─ package.json            # Electron 打包配置
│  ├─ build/                  # 图标与构建资源
│  └─ 启动.bat                # Windows 启动脚本
└─ .gitignore
```

## 技术栈

- Python
- FastAPI
- SQLite
- Pandas
- Electron
- Electron Builder
- 火山引擎 ARK（AI 分析）

## 环境要求

### Python

- 建议 `Python 3.11+`

### Node.js

- 建议 `Node.js 20.x`
- 不建议使用过新的 Node 版本直接打包 Electron

### AI 配置

如果需要启用 AI 学习分析，请准备：

- `ARK_API_KEY`
- ARK 控制台中的模型接入点 ID，例如 `ep-xxxxxxxxxxxxxxxx`

`DOUBAO_MODEL` 这里应填写 ARK 的接入点 ID，不是 `Doubao-pro-32k` 这种旧模型名

## 安装依赖

在项目根目录执行：

```bash
pip install -r requirements.txt
```

Electron 依赖在 `electron-dist/` 下单独安装：

```bash
cd electron-dist
npm install
```

如果安装 Electron 依赖时遇到证书问题，可临时使用：

```bash
NODE_TLS_REJECT_UNAUTHORIZED=0 npm install --no-audit
```

这只建议用于本地开发 / 比赛打包环境，不建议长期作为默认方案。

## 本地运行

### 1. 运行本地分析入口

```bash
python main.py
```

### 2. 启动后端 API

在项目根目录执行：

```bash
export ARK_API_KEY='你的ARK密钥'
export DOUBAO_MODEL='你的ARK接入点ID'
uvicorn backend.api_server:app --host 127.0.0.1 --port 8000
```

如果暂时不接 AI，也可以直接启动后端，但 AI 相关内容会退回本地摘要或不可用。

### 3. 启动 Electron 桌面端

```bash
cd electron-dist
npm start
```

## 常用接口

后端启动后，可通过以下地址验证服务状态：

- `http://127.0.0.1:8000/users`
- `http://127.0.0.1:8000/calendar_index?user_id=P1`
- `http://127.0.0.1:8000/docs`

说明：

- 根路径 `/` 返回 `{"detail":"Not Found"}` 是正常现象
- 这是 API 服务，不是后端网页首页

## AI 功能说明

AI 分析并不是页面一打开就自动生成，而是通过“生成每日报告”触发。

触发条件：

1. 当前日期有可用学习数据
2. 已填写“今日任务”
3. 后端已正确读取 `ARK_API_KEY` 和接入点 ID

如果 AI 没有生成成功，后端可能会：

- 输出日志警告
- 回退到本地文本分析

因此排查 AI 问题时，优先检查：

- 后端启动终端日志
- `DOUBAO_MODEL` 是否为 ARK 接入点 ID
- 网络 / 证书环境是否正常

## Electron 打包

打包命令都在 `electron-dist/package.json` 中定义。

### macOS

先生成目录版：

```bash
cd electron-dist
npm run pack:dir
```

再生成安装包：

```bash
npm run pack:mac
```

### Windows

推荐在 Windows 机器上执行：

```bash
cd electron-dist
npm install
npm run pack:win
```

### 打包产物位置

默认输出到：

```text
electron-dist/dist/
```

## 图标资源

Electron 使用 `electron-dist/build/` 下的图标资源：

- `icon.png`
- `icon.ico`
- `icon.icns`

如果替换 logo 后需要重新生成图标，请同步更新这些文件再重新打包。

## 协作建议

建议按三人分工维护：

- 前端：`electron-dist/`
- 后端：`backend/`
- 模型与分析：`analysis/`、`src/`

协作原则：

- 算法逻辑不要混入 `backend/`
- 接口与数据库只放 `backend/`
- 页面与打包配置统一放 `electron-dist/`
- 原始数据放 `data/raw/`
- 运行产物放 `data/processed/`
- 文档统一收口到 `docs/`

## 提交前检查

建议每次提交前至少确认：

1. `python main.py` 能跑通
2. 后端 `uvicorn backend.api_server:app --host 127.0.0.1 --port 8000` 能启动
3. Electron 页面能正常打开
4. 关键页面布局没有明显错位
5. 若涉及 AI，确认后端日志没有明显报错

## 当前已完成事项

- 项目目录已按“算法 / 后端 / 数据 / 前端打包”整理
- Electron 主界面、统计页、详情页完成一轮 UI 调整
- macOS 目录版打包链路已跑通
- AI 配置方式已切换到火山引擎 ARK 接入点思路

## 后续建议

- 在 Windows 机器上完成一次正式 `pack:win`
- 将 ARK 接入点 ID 与启动方式写入团队内部说明
- 如需长期稳定打包，建议统一 Node 版本与网络环境
- 如需正式分发 mac 应用，可进一步补充签名与 notarization
