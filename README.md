# Focus

Focus 是一个面向学习场景的桌面应用，围绕 HRV 数据分析、专注度评估、FastAPI 后端和 Electron 客户端构建。它既可以本地运行，也支持通过 Cloudflare Tunnel 临时暴露到公网，方便跨设备演示和联调。

## 项目简介

这个项目主要包含以下能力：

- 读取并处理 HRV 数据
- 评估压力与专注度变化
- 提供日报、周报等分析接口
- 支持可选的 AI 文本总结
- 提供 Electron 桌面端界面

## 项目亮点

- FastAPI 后端，自带 Swagger 文档页面
- Electron 桌面应用，支持外部 API 地址配置
- SQLite 持久化学习会话与用户偏好
- `data/` 目录保留本地原始数据和运行产物
- 支持通过 Cloudflare Quick Tunnel 快速对外访问

## 项目结构

```text
Focus/
|-- analysis/                # 专注度与学习分析逻辑
|-- backend/                 # FastAPI 应用、数据库访问、服务入口
|-- data/                    # 本地数据与运行生成文件
|-- electron-dist/           # Electron 应用与打包配置
|-- src/                     # 数据加载与辅助工具
|-- main.py                  # 本地演示入口
|-- requirements.txt         # Python 依赖
`-- README.md
```

## 技术栈

- Python
- FastAPI
- Uvicorn
- SQLite
- Pandas
- Electron
- Electron Builder

## 环境要求

### Python

- 建议使用 Python 3.10 及以上版本
- 推荐使用项目本地虚拟环境 `.venv`

### Node.js

- 建议使用 Node.js 20.x

### 可选 AI 配置

如果需要启用 AI 总结能力，请提供：

- `ARK_API_KEY`
- `DOUBAO_MODEL`

说明：`DOUBAO_MODEL` 应填写 ARK 接入点 ID，而不是旧的模型别名。

## 安装依赖

### Python 依赖

在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

如果项目里已经有 `.venv`，可以直接安装：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Electron 依赖

在 `electron-dist/` 目录执行：

```powershell
cd electron-dist
npm install
```

## 本地运行

### 1. 启动 FastAPI 后端

在项目根目录执行：

```powershell
$env:FOCUS_HOST="0.0.0.0"
$env:FOCUS_PORT="8000"
.\.venv\Scripts\python.exe -m uvicorn backend.api_server:app --host 0.0.0.0 --port 8000
```

预期结果：

- Uvicorn 正常启动
- 浏览器可以打开 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

也可以使用项目内的启动入口：

```powershell
.\.venv\Scripts\python.exe -m backend.run_server
```

### 2. 启动 Electron 桌面端

```powershell
cd electron-dist
npm start
```

## 常用本地接口

后端启动后，可以先用这些地址验证服务状态：

- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- [http://127.0.0.1:8000/users](http://127.0.0.1:8000/users)
- [http://127.0.0.1:8000/calendar_index?user_id=P1](http://127.0.0.1:8000/calendar_index?user_id=P1)

说明：

- `GET /` 返回 `{"detail":"Not Found"}` 属于正常现象
- 这是 API 服务，不是传统网页首页

## 通过 Cloudflare Quick Tunnel 暴露公网

这个项目可以在 Windows 电脑上直接暴露到公网，不需要云服务器，也不需要自定义域名。

### 这意味着什么

- FastAPI 后端仍然运行在你的 Windows 电脑上
- `cloudflared` 会创建一个临时公网地址
- 其他设备可以通过这个公网地址访问你的后端
- `data/` 目录中的文件依然保存在这台 Windows 电脑上
- 远程设备只能通过 API 间接读取数据，不能直接访问本地磁盘

### Windows 快速步骤

1. 启动本地后端，监听 `8000` 端口
2. 下载 `cloudflared.exe`
3. 执行：

```powershell
C:\Cloudflared\bin\cloudflared.exe tunnel --url http://127.0.0.1:8000
```

4. 打开生成的 `https://xxxx.trycloudflare.com/docs`

注意：

- FastAPI 的终端窗口要保持开启
- `cloudflared` 的终端窗口也要保持开启
- Quick Tunnel 生成的公网地址是临时的，后续可能变化

## Electron 后端地址配置

Electron 支持通过以下方式配置后端 API 地址：

- 环境变量 `FOCUS_API_BASE`
- 外部配置文件 `focus.config.json`

配置示例：

```json
{
  "apiBase": "https://xxxx.trycloudflare.com"
}
```

打包后，`focus.config.json` 可以和可执行文件放在一起，用来覆盖默认的本地 API 地址。

## Electron 打包

在 `electron-dist/` 目录执行：

```powershell
npm run pack:win
```

当前 Windows 打包注意事项：

- `electron-builder` 可能会在下载或解压 `winCodeSign` 时失败
- 即使失败，`dist/win-unpacked/` 也可能已经生成，可以先用于测试

### 测试打包产物

如果没有成功生成最终安装包，但已经生成 `win-unpacked`，可以先测试：

- `electron-dist/dist/win-unpacked/Focus.exe`

如果要把测试版给另一台 Windows 电脑使用：

- 发送整个 `electron-dist/dist/win-unpacked/` 目录，而不是只发 `Focus.exe`
- `focus.config.json` 需要和可执行文件放在同一目录
- 作为后端宿主机的 Windows 电脑必须保持 FastAPI 和 Cloudflare Tunnel 运行中

## 数据存储说明

`data/` 目录始终保存在宿主机本地。

这意味着：

- 数据不会直接同步到客户端设备
- 远程用户不能直接浏览宿主机磁盘
- 后端只是在本机读取文件，然后把结果通过 API 返回给客户端

## 开发建议

- 后端接口与数据库逻辑放在 `backend/`
- 分析与建模逻辑放在 `analysis/` 和 `src/`
- Electron 页面与打包配置放在 `electron-dist/`
- `data/` 目录视为本地运行数据目录

## 提交前建议检查

在推送到 GitHub 前，建议至少确认：

1. 后端可以正常启动
2. `/docs` 可以本地打开
3. Electron 可以正常启动
4. 关键页面没有明显布局或数据错误
5. 即使没有 AI Key，项目也不会因相关功能而启动失败
