# Focus 项目整理说明（计算机比赛）

这个仓库建议按“算法、后端、数据、前端打包”分层，确保多人协作时不混乱。

## 目录应该怎么放

```text
Focus/
├─ main.py                    # 本地演示入口（串联数据->分析->建议->报告）
├─ src/                       # 通用数据处理层
│  └─ data_loader.py
├─ analysis/                  # 算法与分析层
│  ├─ focus_model.py
│  ├─ learning_analysis.py
│  ├─ recommendation_engine.py
│  └─ report_generator.py
├─ backend/                   # FastAPI 服务层
│  ├─ api_server.py
│  ├─ database.py
│  ├─ requirements.txt
│  └─ __init__.py
├─ data/
│  ├─ raw/                    # 原始输入数据（可保留样例）
│  └─ processed/              # 程序生成数据（建议忽略提交）
├─ docs/                      # 文档层（架构、接口、分工）
├─ electron-dist/             # Electron 相关（仅保留源码，忽略二进制产物）
└─ .gitignore
```

## 每类文件放置规则

1. 算法逻辑只放 `analysis/`，不要混到 `backend/`。
2. 数据读取和预处理放 `src/`。
3. API 和数据库只放 `backend/`。
4. 原始样例数据放 `data/raw/`；运行产生的数据放 `data/processed/`。
5. 文档统一放 `docs/`，不要散落在根目录。
6. 打包产物、IDE 文件、缓存文件必须被 `.gitignore` 忽略。

## 快速启动

### 1) 运行本地分析主流程

```bash
pip install -r requirements.txt
python main.py
```

### 2) 启动后端 API

```bash
pip install -r backend/requirements.txt
uvicorn backend.api_server:app --reload
```

## 当前已完成的整理

1. 已增强 `.gitignore`：忽略 IDE、Python 缓存、数据库、Electron 二进制产物。
2. 已修复 `ReportGenerator` 与 `main.py` 的接口不一致（新增兼容方法 `generate`）。
3. 已新增目录规范文档：`docs/PROJECT_STRUCTURE.md`。

## 协作建议（比赛版）

1. 每人负责一个模块目录，避免跨目录大改。
2. 新功能先写到对应目录，再补文档到 `docs/`。
3. 合并前至少跑一遍 `python main.py` 和后端接口自测。
