# Tasks 开发指南

## 目录

- [架构概览](#架构概览)
- [Base Task 类参考](#base-task-类参考)
- [Base MCP Server 参考](#base-mcp-server-参考)
- [新增 Task 步骤](#新增-task-步骤)
- [Task 类型模板](#task-类型模板)
- [文件清单](#文件清单)

---

## 架构概览

每个 Task 是一个独立的子文件夹，包含以下标准组件：

```
tasks/<task_name>/
├── logic.py          # 核心逻辑（继承 BaseTaskLogic）
├── mcp_server.py     # MCP 工具服务器（可选，继承 BaseMCPServer 模式）
├── task.json         # 任务配置
├── workflow.txt      # Agent 工作流步骤
└── ui/               # 前端界面（Vite + React）
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx
        ├── main.jsx
        └── index.css
```

系统调度器（Engine）会自动扫描 `tasks/` 目录，识别含 `task.json` 的子文件夹并注册为可用任务。

---

## Base Task 类参考

所有 Task 的 `logic.py` 应继承以下公共模式。以下为 Base Task 类的抽象定义，各 Task 在此基础上扩展自己的功能。

```python
import sys
import os
import threading
import time
import json
import subprocess
import signal
import uvicorn
from fastapi import FastAPI

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
if project_root not in sys.path:
    sys.path.append(project_root)

from system.components.base.agent.core import Agent
from system.components.base.agent.server import create_agent_server


class BaseTaskLogic:
    """
    所有 Task 的基类，提供公共功能：
    - 配置加载（common_config.json + task.json 两层覆盖）
    - Agent 初始化与管理
    - UI Server 启动与停止
    - 端口清理
    - 信号处理与进程生命周期管理
    """

    def __init__(self):
        # ========== 配置加载 ==========
        current_dir = os.path.dirname(os.path.abspath(
            sys.modules[self.__class__.__module__].__file__
        ))
        task_json_path = os.path.join(current_dir, "task.json")
        common_config_path = os.path.join(current_dir, "../common_config.json")

        self.config = {}
        self._task_dir = current_dir

        # Load Common Config → Task Config (deep merge)
        if os.path.exists(common_config_path):
            with open(common_config_path, 'r', encoding='utf-8') as f:
                self._deep_update(self.config, json.load(f))

        with open(task_json_path, 'r', encoding='utf-8') as f:
            task_data = json.load(f)
            self._deep_update(self.config, task_data.get("config", {}))

        # ========== 公共状态 ==========
        self.agent = None
        self.agent_app = None
        self.ui_process = None

    # ---------- 配置工具 ----------
    @staticmethod
    def _deep_update(d, u):
        for k, v in u.items():
            if isinstance(v, dict):
                d[k] = BaseTaskLogic._deep_update(d.get(k, {}), v)
            else:
                d[k] = v
        return d

    # ---------- Agent 初始化 ----------
    def initialize_agent(self, tools=None):
        """
        初始化 Agent 和 Agent Server。
        Args:
            tools: Agent 工具列表。传 None 或 [] 为纯对话模式；
                   传 MCP 配置则自动启动 MCP 子进程。
        """
        agent_cfg = self.config.get('agent', {})

        if tools is None:
            # 检查是否存在 mcp_server.py，自动配置
            mcp_path = os.path.join(self._task_dir, "mcp_server.py")
            if os.path.exists(mcp_path):
                server_cfg = self.config.get('server', {})
                api_url = f"http://{server_cfg.get('host', 'localhost')}:{server_cfg.get('api_port', 8002)}"
                mcp_env = os.environ.copy()
                existing_pythonpath = mcp_env.get("PYTHONPATH")
                mcp_env["PYTHONPATH"] = (
                    PROJECT_ROOT + os.pathsep + existing_pythonpath
                    if existing_pythonpath else PROJECT_ROOT
                )
                tools = [{
                    "mcpServers": {
                        "task_control": {
                            "command": sys.executable,
                            "args": [mcp_path, "--api-url", api_url],
                            "env": mcp_env
                        }
                    }
                }]
            else:
                tools = []

        self.agent = Agent(
            llm_cfg=self.config.get('llm', {}),
            system_message=agent_cfg.get('system_message', "You are a helpful assistant."),
            tools=tools
        )
        self.agent_app = create_agent_server(self.agent)

    # ---------- UI Server ----------
    def start_ui_server(self):
        ui_dir = os.path.join(self._task_dir, "ui")
        if not os.path.exists(ui_dir):
            print(f"UI directory not found: {ui_dir}")
            return

        server_cfg = self.config.get('server', {})
        self.ui_port = server_cfg.get('frontend_port', 8501)
        self._kill_port_process(self.ui_port)
        time.sleep(1)

        try:
            self.ui_process = subprocess.Popen(
                "npm start", cwd=ui_dir, shell=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            print(f"UI Server started (PID {self.ui_process.pid}, port {self.ui_port})")
        except Exception as e:
            print(f"Failed to start UI server: {e}")

    # ---------- 生命周期 ----------
    def start(self):
        """子类重写此方法以添加硬件初始化等逻辑，最后调用 super().start()"""
        self.initialize_agent()
        self.start_ui_server()

    def stop(self):
        """子类重写此方法以添加硬件清理，最后调用 super().stop()"""
        if self.ui_process:
            try:
                self.ui_process.terminate()
                self.ui_process.wait(timeout=3)
            except:
                subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(self.ui_process.pid)],
                    capture_output=True, timeout=5
                )
            print("UI Server stopped")

        if hasattr(self, 'ui_port'):
            time.sleep(0.5)
            self._kill_port_process(self.ui_port)

    def get_status(self):
        """子类重写以返回任务特定状态"""
        return {"mode": "READY", "message": "Task Ready"}

    # ---------- 端口清理 ----------
    def _kill_port_process(self, port):
        try:
            result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, timeout=5)
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    pid = line.split()[-1]
                    subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True, timeout=5)
        except:
            pass

    # ---------- __main__ 入口 ----------
    def run_as_main(self):
        """标准 __main__ 启动入口，子类在 if __name__ == '__main__' 中调用"""
        signal.signal(signal.SIGTERM, lambda s, f: (self.stop(), sys.exit(0)))
        signal.signal(signal.SIGINT,  lambda s, f: (self.stop(), sys.exit(0)))

        try:
            self.start()

            # Agent Server (background thread)
            def run_agent():
                cfg = self.config.get('server', {})
                uvicorn.run(self.agent_app, host=cfg.get('host', '127.0.0.1'), port=cfg.get('agent_port', 8001))
            threading.Thread(target=run_agent, daemon=True).start()

            # Task API Server (main thread, blocking)
            app = self.create_api_app()

            cfg = self.config.get('server', {})
            uvicorn.run(app, host=cfg.get('host', '127.0.0.1'), port=cfg.get('api_port', 8002))
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            print(f"Error: {e}")
            self.stop()

    def create_api_app(self):
        """子类重写以注册自定义的 Task API 端点"""
        app = FastAPI()
        app.get("/status")(lambda: self.get_status())
        app.on_event("shutdown")(lambda: self.stop())
        return app
```

### 子类示例

```python
# tasks/my_task/logic.py

class MyTask(BaseTaskLogic):
    def __init__(self):
        super().__init__()
        # 初始化任务特定状态
        self.mode = "IDLE"

    def start(self):
        # 初始化硬件（如需要）
        # self.pressure_ctrl = PressureController(...)
        # self.camera_ctrl = CameraFactory.create_camera(...)
        super().start()  # 调用基类：初始化 Agent + 启动 UI

    def stop(self):
        # 清理硬件
        super().stop()  # 调用基类：停止 UI

    def get_status(self):
        return {"mode": self.mode, "message": "My Task Status"}

    def create_api_app(self):
        app = super().create_api_app()  # 获取带 /status 的基础 app
        # 注册自定义端点
        app.post("/control/my_action")(lambda: self.my_action())
        return app

if __name__ == "__main__":
    MyTask().run_as_main()
```

---

## Base MCP Server 参考

需要 Agent 调用工具的 Task，应创建 `mcp_server.py`，遵循以下模式：

```python
# tasks/my_task/mcp_server.py

from fastmcp import FastMCP
import requests
import argparse

# ========== 公共模式：命令行参数 + API URL ==========
parser = argparse.ArgumentParser()
parser.add_argument('--api-url', type=str, default='http://localhost:8002')
args = parser.parse_args()
API_URL = args.api_url

mcp = FastMCP("my_task_tools")

# ========== 工具定义 ==========
@mcp.tool()
def my_tool_name(param1: str, param2: float = 0) -> str:
    """
    工具描述（Agent 靠此理解何时使用工具）。

    Args:
        param1: 参数1说明
        param2: 参数2说明（默认值0）
    """
    try:
        resp = requests.post(f"{API_URL}/control/my_action", params={"p1": param1, "p2": param2})
        return str(resp.json())
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def control_pump_channels(channel1: str = "unchanged", channel2: str = "unchanged",
                          channel3: str = "unchanged", channel4: str = "unchanged") -> str:
    """通用泵控制工具（多个 Task 可共用此定义）"""
    try:
        params = {}
        for key, val in [('p1', channel1), ('p2', channel2), ('p3', channel3), ('p4', channel4)]:
            if val.lower() != "unchanged":
                params[key] = float(val)
        resp = requests.post(f"{API_URL}/control/pressure", params=params)
        return str(resp.json())
    except Exception as e:
        return f"Error: {e}"

# ========== 入口 ==========
if __name__ == "__main__":
    mcp.run()
```

### 关键规则

- 每个 `@mcp.tool()` 函数通过 HTTP 转发到 `logic.py` 的 Task API
- docstring 即 Agent 看到的工具描述，需写清楚使用场景和参数含义
- 不要在 MCP Server 中直接操作硬件，必须通过 Task API 间接调用
- 纯对话 Task（如 reagent_preparation）不需要 `mcp_server.py`

---

## 新增 Task 步骤

### Step 1: 创建目录

```bash
mkdir tasks/my_new_task
mkdir tasks/my_new_task/ui
mkdir tasks/my_new_task/ui/src
```

### Step 2: 创建 task.json

```json
{
    "name": "My New Task",
    "description": "一句话描述任务功能",
    "entry_point": "logic.py",
    "version": "1.0.0",
    "config": {
        "llm": {
            "model": "qwen3-32b",
            "model_server": "http://127.0.0.1:1234/v1",
            "api_key": "EMPTY"
        },
        "agent": {
            "system_message": "You are a ... assistant./no_think"
        }
    }
}
```

> `config` 中的字段会覆盖 `common_config.json` 中的同名字段（deep merge）。

### Step 3: 创建 logic.py

继承 `BaseTaskLogic` 模式，重写以下方法：

| 方法 | 何时重写 | 说明 |
|---|---|---|
| `__init__` | 总是 | 初始化任务状态、硬件对象 |
| `start()` | 需要硬件初始化时 | 初始化硬件后调用 `super().start()` |
| `stop()` | 需要硬件清理时 | 清理硬件后调用 `super().stop()` |
| `get_status()` | 总是 | 返回任务特定状态 |
| `create_api_app()` | 需要自定义 API 时 | 注册 Task 特定端点 |

### Step 4: 创建 workflow.txt

用自然语言描述 Agent 应遵循的步骤：

```
step 1. 做什么，调用什么工具，提醒用户什么
step 2. ...
notice:
- 异常情况处理
```

### Step 5: 创建 mcp_server.py（可选）

仅当 Agent 需要调用外部工具时才创建。每个工具函数应 HTTP 转发到 logic.py 的 API 端点。

### Step 6: 创建 UI

**package.json** — 基于模板修改名称，按需增减依赖：
```json
{
    "name": "my-new-task-ui",
    "scripts": { "start": "vite" },
    "dependencies": {
        "@ant-design/x": "^2.1.2",
        "@ant-design/x-markdown": "^2.1.3",
        "@ant-design/x-sdk": "^2.1.3",
        "antd": "^6.1.4",
        "react": "^18.2.0",
        "react-dom": "^18.2.0"
    }
}
```

**vite.config.js** — 配置代理：
```js
proxy: {
    '/api': {  // → Agent Server
        target: 'http://127.0.0.1:8001',
        rewrite: (path) => path.replace(/^\/api/, '')
    },
    '/control': {  // → Task API（如需要）
        target: 'http://127.0.0.1:8002'
    }
}
```

**App.jsx** — 组合 Base 组件：
```jsx
import AgentApp from '../../../../system/components/base/agent/ui/src/App.jsx';
import VideoStream from '../../../../system/components/base/camera/ui/VideoStream.jsx'; // 如需要
```

### Step 7: 安装依赖 & 验证

```bash
cd tasks/my_new_task/ui
npm install
```

启动系统后，在主页面侧边栏中应自动出现新 Task。

---

## Task 类型模板

| 类型 | 硬件 | MCP | UI 组件 | 示例 |
|---|---|---|---|---|
| 纯对话 | ❌ | ❌ | AgentApp | `reagent_preparation` |
| 硬件 + 对话 | ✅ | ✅ | AgentApp + VideoStream + 自定义 | `liposome_gen`, `treatment` |
| 仅监控 | ✅ | ❌ | VideoStream + 自定义 | `base` |

---

## 文件清单

| 文件 | 必需 | 说明 |
|---|---|---|
| `task.json` | ✅ | 任务被系统发现的必要条件 |
| `logic.py` | ✅ | 入口脚本（`entry_point` 指定） |
| `workflow.txt` | ⚠️ 推荐 | 无此文件则 UI 不显示 "Start Experiment" 按钮 |
| `mcp_server.py` | ❌ 可选 | 仅 Agent 需要调用工具时创建 |
| `ui/` | ⚠️ 推荐 | 无 UI 时任务仍可运行，但系统主页无法嵌入界面 |
