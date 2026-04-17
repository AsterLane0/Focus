# Focus

Focus 是一个面向学习场景的桌面应用项目，包含：

- 基于 HRV 数据的专注度与压力分析
- FastAPI 后端接口
- Electron 桌面端前端
- 可选的 AI 分析与日报生成功能

这个 README 重点解决三件事：

1. 让新机器能把项目跑起来
2. 让阅读者快速理解项目结构和运行方式
3. 让部署到云服务器和打包给用户这两件事有清晰说明

## 目录

- [项目结构](#项目结构)
- [技术栈](#技术栈)
- [运行前准备](#运行前准备)
- [环境变量](#环境变量)
- [本地开发启动](#本地开发启动)
- [桌面端连接云服务器后端](#桌面端连接云服务器后端)
- [云服务器部署](#云服务器部署)
- [接口与数据说明](#接口与数据说明)
- [AI 功能说明](#ai-功能说明)
- [打包与交付](#打包与交付)
- [常用命令](#常用命令)
- [常见问题排查](#常见问题排查)

## 项目结构

```text
Focus/
├─ analysis/                  # 专注度、学习状态、建议和报告生成逻辑
├─ backend/                   # FastAPI 服务、数据库访问、启动入口
├─ data/                      # 原始数据、SQLite 数据库、运行期产物
├─ electron-dist/             # Electron 桌面端源码与打包配置
├─ src/                       # 数据加载与辅助工具
├─ main.py                    # 本地演示入口
├─ requirements.txt           # Python 依赖
├─ start-focus.bat            # Windows 下启动桌面端的快捷入口
└─ README.md
```

### 目录职责

- `analysis/`
  负责专注度分析、学习行为分析、建议生成、AI 报告组织。

- `backend/`
  提供 FastAPI 接口，对外暴露 `/users`、`/daily_dashboard`、`/calendar_index`、`/user_ai_preference`、`/user_daily_task` 等接口。

- `data/`
  保存项目运行所依赖和生成的数据。数据库也会落在这里，例如学习会话记录数据库。

- `electron-dist/`
  是当前桌面端前端的真实运行目录。桌面端不是传统 Web 项目的 `src + Vite` 架构，而是 Electron 加静态 HTML/JS 页面。

## 技术栈

- **语言**：Python 3、JavaScript
- **后端框架**：FastAPI
- **后端服务**：Uvicorn
- **数据处理**：Pandas
- **数据存储**：SQLite
- **桌面端**：Electron
- **打包工具**：electron-builder
- **AI 接入**：ARK / 豆包接入点

## 运行前准备

### 本地开发环境

- Python 3.10 及以上
- Node.js 20.x
- npm（随 Node.js 一起安装即可）

### 云服务器部署环境

- Ubuntu 22.04 或其他兼容 Linux 环境
- Python 3.10 及以上
- 可正常对外开放后端端口

## 环境变量

项目后端启动时会自动读取 `.env` 文件。

### 必填

| 变量名 | 说明 |
| --- | --- |
| `ARK_API_KEY` | AI 接口访问 key |
| `DOUBAO_MODEL` | 豆包 / ARK 接入点 ID |

### 兼容变量

| 变量名 | 说明 |
| --- | --- |
| `DOUBAO_API_KEY` | 兼容写法，代码会在找不到 `ARK_API_KEY` 时继续尝试读取它 |

### 后端启动相关

| 变量名 | 说明 | 默认值 |
| --- | --- | --- |
| `FOCUS_HOST` | 后端监听地址 | `0.0.0.0` |
| `FOCUS_PORT` | 后端监听端口 | `8000` |

### `.env` 示例

```env
ARK_API_KEY=your_api_key_here
DOUBAO_MODEL=your_endpoint_id_here
```

说明：

- `.env` 只应该保留在本地电脑或云服务器上
- 不要把真实 key 提交到 GitHub
- `DOUBAO_MODEL` 应填写接入点 ID，而不是旧模型别名

## 本地开发启动

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd Focus
```

### 2. 安装 Python 依赖

Windows：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Linux / macOS：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 安装 Electron 依赖

```bash
cd electron-dist
npm install
cd ..
```

### 4. 配置 AI（可选）

如果只联调基础接口，不需要 AI，可跳过。

如果要启用 AI 分析，请在项目根目录创建 `.env`：

```env
ARK_API_KEY=your_api_key_here
DOUBAO_MODEL=your_endpoint_id_here
```

### 5. 启动本地后端

方式一：直接运行 Uvicorn

Windows：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8000
```

Linux / macOS：

```bash
source .venv/bin/activate
uvicorn backend.api_server:app --host 0.0.0.0 --port 8000
```

方式二：使用项目封装入口

Windows：

```powershell
$env:FOCUS_HOST="0.0.0.0"
$env:FOCUS_PORT="8000"
.\.venv\Scripts\python.exe -m backend.run_server
```

Linux / macOS：

```bash
export FOCUS_HOST=0.0.0.0
export FOCUS_PORT=8000
python -m backend.run_server
```

### 6. 启动桌面端

```bash
cd electron-dist
npm start
```

启动后，桌面端会打开 Electron 窗口。

### 7. 验证本地后端是否正常

先在浏览器中访问：

- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- [http://127.0.0.1:8000/users](http://127.0.0.1:8000/users)

如果这两个地址正常返回，说明本地后端已启动成功。

## 桌面端连接云服务器后端

当前项目已经支持“本地电脑运行桌面端，云服务器运行后端”的联调方式。

### 当前桌面端后端地址机制

桌面端后端地址优先级如下：

1. 启动参数传入的 `api_base`
2. 本地保存的 `focus_api_base`
3. Electron 主进程中的默认地址

### Windows 快捷启动方式

项目根目录提供了：

```text
start-focus.bat
```

这个脚本当前行为是：

- 不启动本地 FastAPI
- 只启动 Electron 桌面端
- 启动时将 `FOCUS_API_BASE` 传给桌面端

如果你当前联调目标是云服务器后端，可以直接双击这个文件。

### 云服务器联调时的验证方法

桌面端打开后，至少检查这几个点：

- 登录页是否能正常拉出用户列表
- 进入主界面后是否能读取日报、任务、偏好等数据
- 浏览器是否能访问云服务器 Swagger 文档

例如当前常见验证地址为：

```text
http://<server-ip>:9000/docs
http://<server-ip>:9000/users
```

## 云服务器部署

### 1. 上传或拉取项目

```bash
git clone <your-repo-url>
cd Focus
```

### 2. 创建虚拟环境并安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 配置 `.env`

```bash
cat > .env <<'EOF'
ARK_API_KEY=your_api_key_here
DOUBAO_MODEL=your_endpoint_id_here
EOF
```

### 4. 启动后端

开发联调方式：

```bash
source .venv/bin/activate
uvicorn backend.api_server:app --host 0.0.0.0 --port 9000 --reload
```

更稳定的方式：

```bash
source .venv/bin/activate
uvicorn backend.api_server:app --host 0.0.0.0 --port 9000
```

说明：

- `0.0.0.0` 代表监听所有网卡
- 外部设备访问时，不是访问 `0.0.0.0`
- 外部访问应使用服务器公网 IP，例如 `http://<server-ip>:9000`

### 5. 服务器自检

在服务器上检查 9000 端口是否在监听：

```bash
ss -ltnp | grep 9000
```

在服务器本机测试：

```bash
curl http://127.0.0.1:9000/docs
curl http://127.0.0.1:9000/users
```

### 6. 客户端验证

在你自己的电脑上访问：

```text
http://<server-ip>:9000/docs
http://<server-ip>:9000/users
```

如果这两个地址能打开，说明云服务器后端已对外可用。

## 接口与数据说明

### 常用接口

| 接口 | 作用 |
| --- | --- |
| `/docs` | Swagger 文档页 |
| `/openapi.json` | OpenAPI 描述 |
| `/users` | 获取用户列表 |
| `/calendar_index` | 获取用户日历数据索引 |
| `/daily_dashboard` | 获取日 / 周分析数据 |
| `/user_ai_preference` | 获取或保存用户 AI 偏好 |
| `/user_daily_task` | 获取或保存用户当日任务 |

### 数据存储

项目运行数据主要位于：

- `data/raw/`：原始 HRV 数据
- `data/processed/`：处理产物
- `data/*.db`：SQLite 数据库

后端数据库初始化日志中通常会出现类似：

```text
Database initialized at /path/to/Focus/data/study_sessions.db
```

这表示 SQLite 数据库已经建立。

## AI 功能说明

### AI 功能依赖

如果未配置 `ARK_API_KEY` 或 `DOUBAO_API_KEY`，后端会启动，但 AI 功能不可用。

也就是说：

- 基础接口仍然可用
- 登录、用户列表、日报基础数据仍可工作
- 只有 AI 分析 / AI 报告会失效

### 如何判断 AI 已生效

后端启动后如果不再出现这句警告，通常说明 key 已被正确读取：

```text
ARK_API_KEY / DOUBAO_API_KEY 未配置，AI 功能将不可用
```

然后再去前端实际触发一次 AI 分析或报告生成，确认结果能返回。

## 打包与交付

### Windows 打包

在 `electron-dist/` 目录执行：

```bash
npm run pack:win
```

### macOS 打包

```bash
npm run pack:mac
```

### 只打出目录

```bash
npm run pack:dir
```

### apk打包
在 Android Studio 中加载 electron-dist

1. 软件和环境
```text
Android Studio: D:\android-studio - 用于打开和管理 Android 项目
Gradle: Android 构建系统（版本 8.2）
Java: JDK（Android Studio 自带）
```

2. 项目结构
```text
E:\Focus-main (3)\Focus-main\electron-dist\
├── index.html          # 源前端文件
├── www\              # Web 资源目录
└── android\          # Android 项目
    ├── app\
    │   ├── src\main\
    │   │   ├── assets\public\  # 前端打包目录
    │   │   ├── java\com\asterlane\focus\
    │   │   └── res\
    │   └── build.gradle
    └── gradle\
```

3. 构建命令
```bash
cd E:\Focus-main (3)\Focus-main\electron-dist\android
.\gradlew.bat assembleDebug
APK 输出位置：android\app\build\outputs\apk\debug\app-debug.apk
```

4. 关键配置
```text
AndroidManifest.xml: 允许 HTTP 连接 (android:usesCleartextTraffic="true")
network_security_config.xml: 允许特定域名的 HTTP
focus.config.json: 后端 API 地址
```
5.APK 输出位置
```text
android\app\build\outputs\apk\debug\app-debug.apk
```

### 打包输出说明

常见输出目录：

```text
electron-dist/dist/
```

如果生成了 `win-unpacked`，测试时应优先发送整个目录，而不是只发送单个 `.exe`。

### `focus.config.json`

打包配置中已经声明会把 `focus.config.json` 一起带进产物。

它的作用是给打包后的桌面端覆盖 API 地址，例如：

```json
{
  "apiBase": "http://your-server-ip:9000"
}
```

如果你要把软件交给用户使用，最稳的方式是：

- 打包时确保后端地址明确
- 把 `focus.config.json` 和可执行文件放在一起
- 在另一台普通电脑上做一次完整启动验证

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `python -m backend.run_server` | 按环境变量启动后端 |
| `uvicorn backend.api_server:app --host 0.0.0.0 --port 8000` | 本地启动后端 |
| `uvicorn backend.api_server:app --host 0.0.0.0 --port 9000 --reload` | 云服务器联调启动 |
| `cd electron-dist && npm start` | 启动桌面端 |
| `cd electron-dist && npm run pack:win` | 打包 Windows 版本 |
| `ss -ltnp | grep 9000` | 查看服务器是否监听 9000 |
| `curl http://127.0.0.1:9000/users` | 在服务器本机测试用户列表接口 |

## 常见问题排查

### 1. 桌面端能打开，但拿不到数据

先确认：

- 后端是否启动
- `http://<server-ip>:9000/docs` 是否可打开
- `http://<server-ip>:9000/users` 是否返回用户列表

### 2. 浏览器打不开 `/docs`

常见原因：

- 后端进程没启动
- 后端没监听正确端口
- 服务器安全组 / 防火墙没开放端口
- 服务只监听了 `127.0.0.1`，没有监听 `0.0.0.0`

### 3. 桌面端登录页还能看到用户列表，但浏览器一度打不开文档页

这种情况不一定表示桌面端地址错了。

排查方向应优先看：

- 云服务器服务是否间歇性波动
- 程序本地缓存是否残留
- 实际请求地址是否仍然是目标服务器地址

### 4. AI 功能不可用

先检查：

- `.env` 是否存在
- `ARK_API_KEY` 是否正确
- `DOUBAO_MODEL` 是否正确
- 启动日志里是否还在报“AI 功能将不可用”

### 5. 打包后用户电脑打不开

优先检查：

- 是否发送了完整打包目录
- `focus.config.json` 是否在正确位置
- 用户电脑能否访问云服务器后端

## 维护建议

- 真实 API key 只保存在本地 `.env` 或服务器 `.env`
- 不要把真实 key 写进 `.env_example`
- 联调完成后，建议固定桌面端后端地址配置来源，减少“代码默认值”和“外部配置文件”不一致的问题

