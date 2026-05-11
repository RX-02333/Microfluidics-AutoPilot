# Microfluidics AutoPilot

基于 LLM Agent 驱动的微流控实验自动化控制系统。系统采用模块化 Task 架构，每个实验任务独立运行，AI Agent 通过 MCP 工具调用控制硬件设备。

---

## 目录

- [系统架构](#系统架构)
- [环境要求](#环境要求)
- [安装指南](#安装指南)
  - [1. 克隆项目](#1-克隆项目)
  - [2. Python 环境](#2-python-环境)
  - [3. Node.js 环境](#3-nodejs-环境)
  - [4. LM Studio 安装与模型下载](#4-lm-studio-安装与模型下载)
- [配置说明](#配置说明)
  - [系统配置](#系统配置)
  - [硬件配置](#硬件配置)
  - [Task 配置](#task-配置)
- [启动系统](#启动系统)
- [项目结构](#项目结构)
- [开发指南：创建新 Task](#开发指南创建新-task)

## 安装指南

### 1. 克隆项目

```bash
git clone <repository-url>
cd new_system
```

### 2. Python 环境

推荐使用 Conda 创建独立环境：

```bash
# 创建并激活虚拟环境
conda create -n microfluidics python=3.12 -y
conda activate microfluidics

# 安装 PyTorch (CUDA 12.x)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu129

# 安装项目依赖
pip install -r requirement.txt
```

### 3. Node.js 环境

系统有多个前端项目需要安装 npm 依赖：

```bash
# ① Agent 基础 UI（所有 Task 共享的聊天界面）
cd system/components/base/agent/ui
npm install
npm run build

# ② 各 Task 的独立前端
cd tasks/liposome_gen/ui
npm install

cd tasks/reagent_preparation/ui
npm install

cd tasks/treatment/ui
npm install
```

### 4. LM Studio 安装与模型下载

本系统使用 [LM Studio](https://lmstudio.ai/) 在本地运行大语言模型。

#### 4.1 安装 LM Studio

1. 访问 https://lmstudio.ai/download
2. 下载 Windows 版本并安装
3. 首次启动后，确认左下角显示 **Local Server: Running**（默认端口 `1234`）

#### 4.2 下载模型

在 LM Studio 中搜索并下载以下模型：

| 模型名称 | 搜索关键词 | 推荐量化 |
|---------|-----------|---------|
| **Qwen 3.5 27B** | `qwen3.5-27b` | Q4_K_M |

**下载步骤：**
1. 打开 LM Studio → 点击左侧 **搜索图标** (Discover)
2. 搜索 `qwen3.5-27b`，选择 GGUF 格式的 Q4_K_M 量化版本
3. 点击 **Download** 等待下载完成

#### 4.3 创建 No-Thinking 模型副本

由于 LM Studio **无法通过 API 动态控制 Thinking 开关**，需要手动创建一个关闭 Thinking 的模型副本：

1. 打开模型存储目录（LM Studio 左下角可查看路径，默认为 `C:\Users\<用户名>\.lmstudio\models`）
2. 找到已下载的 `qwen3.5-27b` 模型文件夹
3. **复制整个文件夹**，将副本重命名为 `qwen3.5-27b-no_thinking`
4. 回到 LM Studio → **My Models**，确认可以看到两个模型

**配置 No-Thinking 模型的 Jinja 模板：**

1. 在 LM Studio 的 **My Models** 列表中选中 `qwen3.5-27b-no_thinking`
2. 右侧面板切换到 **Inference** 标签
3. 展开 **提示词模板 (Prompt Template)** 区域，切换到 **模板 (Jinja)** 模式
4. 在模板的**最前面**插入以下内容：

```jinja
{%- set enable_thinking = false %}
```

> 这会禁用模型的内部推理过程，使其直接输出回答，适用于不需要 Thinking 的 Task（如 Liposome Generation、Treatment 等需要严格遵循 workflow 的任务）。

最终两个模型的用途：

| 模型 | Thinking | 适用场景 |
|------|---------|---------|
| `qwen3.5-27b` | ✅ 启用 | Reagent Preparation 等需要推理的任务 |
| `qwen3.5-27b-no_thinking` | ❌ 禁用 | Liposome Generation、Treatment 等遵循固定流程的任务 |

#### 4.4 配置模型推理参数

选中模型后，在右侧面板的 **Inference** 标签中，按以下参数配置（两个模型均需设置）：

**Load 设置：**

| 参数 | Thinking 模型 | No-Thinking 模型 | 说明 |
|-----|-------------|-----------------|------|
| Context Length | 32768 | 16384 | Thinking 需要更多上下文容纳推理过程 |
| GPU Offload | 最大值 | 最大值 | 尽可能多地使用 GPU 加速 |
| CPU Thread Pool Size | 最大值 | 最大值 | 根据 CPU 核心数自动设置 |
| Eval Batch Size | 4096 | 4096 | 评估批处理大小 |
| Max Concurrent Predictions | 1 | 1 | 并发预测数 |
| Min P Sampling | 0 | 0 | — |

**Inference 设置：**

| 参数 | 值 | 说明 |
|-----|-----|------|
| Temperature | 0.7 | 控制输出随机性 |
| Context Overflow | Truncate Middle | 上下文溢出时截断中间部分 |

**Sampling 设置：**

| 参数 | 值 |
|-----|-----|
| Top K | 20 |
| Repetition Penalty ✅ | 1.1 |
| Presence Penalty | ❌ 禁用 |
| Top P ✅ | 0.8 |
| Min P ✅ | 0 |

#### 4.5 启动 LM Studio 服务

1. 在 LM Studio 中，点击左侧 **↔️ Developer** 标签
2. 确认 Server 状态为 **Running**，端口为 `1234`
3. 系统启动 Task 时会**自动通过 API 加载/卸载模型**，无需手动操作

> **注意：** 系统会在每次启动 Task 时自动执行：
>
> 1. 列出当前已加载的模型
> 2. 卸载所有已加载的模型
> 3. 加载 `task.json` 中 `lmstudio.load_model` 指定的模型

---

## 配置说明

### 系统配置

**`system/server/static/config.json`** — 主控仪表板配置：

```json
{
    "server": {
        "host": "服务器IP地址",   // 服务器 IP（改为本机 IP）
        "port": 8000                 // 主控仪表板端口
    },
    "taskUi": {
        "port": 8501                 // Task UI 默认端口
    }
}
```

### 硬件配置

**`tasks/common_config.json`** — 所有 Task 共享的硬件和网络配置：

```json
{
    "camera": {
        "type": "toupcam",           // 相机类型
        "rtsp_url": "rtsp://IP:8554/test"
    },
    "hardware": {
        "pressure_controller_port": "COM3"  // 压力控制器串口号
    },
    "server": {
        "api_port": 8002,            // Task API 端口
        "agent_port": 8001,          // Agent Server 端口
        "frontend_port": 8501,       // Task UI 开发服务器端口
        "host": "服务器IP地址"     // 服务绑定 IP
    }
}
```

> ⚠️ **首次部署必须修改 `host` 为本机实际 IP 地址。**

### Task 配置

每个 Task 目录下的 **`task.json`** 定义任务的名称、LLM 配置和行为：

```json
{
    "name": "Task 显示名称",
    "description": "任务描述",
    "entry_point": "logic.py",
    "version": "1.0.0",
    "config": {
        "llm": {
            "model": "qwen3.5-27b",                    // OpenAI API 模型名
            "model_server": "http://127.0.0.1:1234/v1", // LM Studio 端点
            "api_key": "EMPTY"
        },
        "lmstudio": {
            "load_model": "lmstudio-community/qwen3.5-27b"  // LM Studio 模型 key
        },
        "agent": {
            "system_message": "系统提示词..."
        }
    }
}
```

**关键字段说明：**
- `llm.model` — 调用 OpenAI 兼容 API 时使用的模型名称
- `lmstudio.load_model` — LM Studio 加载模型的完整 key（可在 LM Studio My Models 页面的 LLM 列查看）
- 如果不设置 `lmstudio.load_model`，启动时不会自动加载/卸载模型

> ⚠️ **首次部署必须修改所有 task.json 中的 `lmstudio.load_model`！**
>
> `load_model` 的值必须与 LM Studio 中显示的模型 key 完全一致。以下文件均需检查并修改：
>
> - `tasks/reagent_preparation/task.json`
> - `tasks/liposome_gen/task.json`
> - `tasks/treatment/task.json`
>
> 在 LM Studio → **My Models** 页面，LLM 列显示的即为模型 key（如 `lmstudio-community/qwen3.5-27b`）。
> 需要关闭 Thinking 的 Task，应将 `load_model` 指向 No-Thinking 副本（如 `rx0/qwen3.5-27b-no_thinking`）。

---

## 启动系统

### 快速启动

```bash
cd new_system

# 确保 conda 环境已激活
conda activate microfluidics

# 启动主控仪表板
python start_system.py
```

浏览器访问 `http://<你的IP>:8000` 打开 Microfluidics AutoPilot 仪表板。

### 启动流程

1. **`start_system.py`** 启动 FastAPI 主服务（端口 8000）
2. 仪表板页面展示所有可用 Task
3. 点击 Task 卡片的 **Start** 按钮启动对应任务
4. Engine 以**子进程**方式启动 Task 的 `logic.py`
5. Task 子进程内部自动启动：
   - LM Studio 模型加载（如果配置了 `lmstudio.load_model`）
   - Agent Server（端口 8001）
   - Task API Server（端口 8002）
   - Task UI 开发服务器（端口 8501）
6. 仪表板自动跳转到 Task UI 页面

### 单独启动某个 Task（调试用）

```bash
cd tasks/reagent_preparation
python logic.py
```

---

## 项目结构

```
├── start_system.py                 # 系统入口
├── requirement.txt                 # Python 依赖
├── README.md                       # 英文文档
├── README_zh.md                    # 中文文档
├── LICENSE
│
├── system/                         # 系统框架层
│   ├── core/
│   │   └── engine.py               # 任务引擎（扫描/启动/停止 Task）
│   ├── server/
│   │   ├── main.py                 # 主控 FastAPI 服务
│   │   └── static/                 # 仪表板前端
│   │       ├── index.html          # 主控仪表板页面
│   │       ├── config.json         # 服务器配置
│   │       ├── logo.png            # 系统 Logo
│   │       └── tailwindcss.js      # Tailwind CSS 运行时
│   ├── task/
│   │   ├── __init__.py
│   │   ├── base_logic.py           # Task 基类（Agent 初始化/UI/生命周期）
│   │   └── base_mcp.py             # MCP 基础工具
│   └── components/
│       └── base/
│           ├── agent/              # AI Agent 组件
│           │   ├── __init__.py
│           │   ├── core.py         # Agent 封装（qwen_agent）
│           │   ├── server.py       # Agent 流式 API 服务
│           │   └── ui/             # Agent 聊天界面（React + Vite）
│           ├── camera/             # 相机组件
│           │   ├── base.py         # 相机基类
│           │   ├── controller.py   # 相机控制器
│           │   ├── toupcam.py      # ToupCam SDK 绑定
│           │   ├── toupcam.dll     # ToupCam 原生驱动
│           │   └── ui/             # 相机画面 UI
│           └── pressure/           # 压力控制器组件
│               ├── base.py         # 压力基类
│               ├── controller.py   # 压力控制器驱动
│               ├── fluidlab.py     # FluidLab 集成
│               └── calibration_data.json
│
└── tasks/                          # 实验任务（可扩展）
    ├── common_config.json          # 共享硬件/网络配置
    ├── liposome_gen/               # 脂质体生成任务
    │   ├── task.json               # 任务配置
    │   ├── logic.py                # 任务逻辑（硬件控制+检测）
    │   ├── workflow.txt            # Agent 工作流程
    │   ├── mcp_server.py           # MCP 工具定义
    │   └── ui/                     # 任务专属前端
    ├── reagent_preparation/        # 试剂配制任务
    │   ├── task.json
    │   ├── logic.py
    │   ├── workflow.txt
    │   └── ui/
    └── treatment/                  # 处理流程任务
        ├── task.json
        ├── logic.py
        ├── workflow.txt
        ├── mcp_server.py
        └── ui/
```

---

## 开发指南：创建新 Task

### 1. 创建 Task 目录

```bash
mkdir tasks/my_new_task
```

### 2. 创建 task.json

```json
{
    "name": "My New Task",
    "description": "任务描述",
    "entry_point": "logic.py",
    "version": "1.0.0",
    "config": {
        "llm": {
            "model": "qwen3.5-27b",
            "model_server": "http://127.0.0.1:1234/v1",
            "api_key": "EMPTY"
        },
        "lmstudio": {
            "load_model": "rx0/qwen3.5-27b@q4_k_m"
        },
        "agent": {
            "system_message": "你的系统提示词"
        }
    }
}
```

### 3. 创建 logic.py

```python
from system.task import BaseTaskLogic

class MyNewTask(BaseTaskLogic):
    def __init__(self):
        super().__init__()

    def start(self):
        print("Starting My New Task...")
        # 自定义初始化（硬件等）
        super().start()  # 启动 Agent + UI

    def stop(self):
        # 自定义清理
        super().stop()

    def get_status(self):
        return {"mode": "READY", "message": "Task Ready"}

if __name__ == "__main__":
    MyNewTask().run_as_main()
```

### 4.创建 MCP 工具

如果 Agent 需要调用硬件功能，创建 `mcp_server.py`：

```python
from fastmcp import FastMCP
mcp = FastMCP("my_task_tools")

@mcp.tool()
async def my_tool(param: str) -> str:
    """工具描述"""
    # 通过 Task API 调用硬件
    return "result"

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

> `BaseTaskLogic` 会自动检测 `mcp_server.py` 并将其注册为 Agent 工具。

### 5.创建 workflow.txt

定义 Agent 的工作流程步骤，Agent 根据此文件指导实验过程。

### 6. 刷新仪表板

重启主服务或刷新浏览器，新 Task 会自动出现在仪表板中。

---

## 常见问题

### LM Studio 连接失败

```
Warning: Cannot connect to LM Studio at http://127.0.0.1:1234. Is it running?
```

**解决：** 打开 LM Studio → Developer → 确认 Server 状态为 Running。

### Agent Chat 中 LaTeX 公式不渲染

确保 Agent 基础 UI 已构建：
```bash
cd system/components/base/agent/ui
npm run build
```

### Task UI 空白页

确保对应 Task 的前端依赖已安装：
```bash
cd tasks/<task_name>/ui
npm install
```
