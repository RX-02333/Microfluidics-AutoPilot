# Microfluidics AutoPilot

An LLM Agent-driven automated control system for microfluidic experiments. The system adopts a modular Task architecture where each experimental task runs independently, with an AI Agent controlling hardware devices through MCP tool calls.

---

## Table of Contents

- [Installation Guide](#installation-guide)
  - [1. Clone the Repository](#1-clone-the-repository)
  - [2. Python Environment](#2-python-environment)
  - [3. Node.js Environment](#3-nodejs-environment)
  - [4. LM Studio Setup & Model Download](#4-lm-studio-setup--model-download)
- [Configuration](#configuration)
  - [System Config](#system-config)
  - [Hardware Config](#hardware-config)
  - [Task Config](#task-config)
- [Running the System](#running-the-system)
- [Project Structure](#project-structure)
- [Development Guide: Creating a New Task](#development-guide-creating-a-new-task)
- [Troubleshooting](#troubleshooting)

## Installation Guide

### 1. Clone the Repository

```bash
git clone https://github.com/RX-02333/Microfluidics-AutoPilot.git
cd Microfluidics-AutoPilot
```

### 2. Python Environment

It is recommended to use Conda to create an isolated environment:

```bash
# Create and activate virtual environment
conda create -n microfluidics python=3.12 -y
conda activate microfluidics

# Install PyTorch (CUDA 12.x)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu129

# Install project dependencies
pip install -r requirement.txt
```

### 3. Node.js Environment

The system has multiple frontend projects that require npm dependencies:

```bash
# 1. Base Agent UI (shared chat interface for all Tasks)
cd system/components/base/agent/ui
npm install
npm run build

# 2. Individual Task frontends
cd tasks/liposome_gen/ui
npm install

cd tasks/reagent_preparation/ui
npm install

cd tasks/treatment/ui
npm install
```

### 4. LM Studio Setup & Model Download

This system uses [LM Studio](https://lmstudio.ai/) to run large language models locally.

#### 4.1 Install LM Studio

1. Visit https://lmstudio.ai/download
2. Download and install the Windows version
3. On first launch, verify that the bottom-left shows **Local Server: Running** (default port `1234`)

#### 4.2 Download the Model

Search and download the following model in LM Studio:

| Model | Search Keyword | Recommended Quantization |
|-------|---------------|--------------------------|
| **Qwen 3.5 27B** | `qwen3.5-27b` | Q4_K_M |

**Download steps:**
1. Open LM Studio → Click the **Search icon** (Discover) on the left sidebar
2. Search for `qwen3.5-27b`, select the GGUF format Q4_K_M quantized version
3. Click **Download** and wait for completion

#### 4.3 Create a No-Thinking Model Copy

Since LM Studio **cannot dynamically toggle Thinking mode via API**, you need to manually create a copy of the model with Thinking disabled:

1. Open the model storage directory (visible at the bottom-left of LM Studio, default: `C:\Users\<username>\.lmstudio\models`)
2. Locate the downloaded `qwen3.5-27b` model folder
3. **Duplicate the entire folder** and rename the copy to `qwen3.5-27b-no_thinking`
4. Return to LM Studio → **My Models** and verify both models are visible

**Configure the No-Thinking model's Jinja template:**

1. In LM Studio's **My Models** list, select `qwen3.5-27b-no_thinking`
2. Switch to the **Inference** tab in the right panel
3. Expand the **Prompt Template** section and switch to **Template (Jinja)** mode
4. Insert the following at the **very beginning** of the template:

```jinja
{%- set enable_thinking = false %}
```

> This disables the model's internal reasoning process, making it output answers directly. This is suitable for Tasks that don't need Thinking (e.g., Liposome Generation, Treatment, and other Tasks that follow a strict workflow).

The two models serve different purposes:

| Model | Thinking | Use Case |
|-------|---------|----------|
| `qwen3.5-27b` | ✅ Enabled | Tasks requiring reasoning (e.g., Reagent Preparation) |
| `qwen3.5-27b-no_thinking` | ❌ Disabled | Tasks following fixed workflows (e.g., Liposome Generation, Treatment) |

#### 4.4 Configure Model Inference Parameters

After selecting a model, configure the following parameters in the **Inference** tab on the right panel (apply to both models):

**Load Settings:**

| Parameter | Thinking Model | No-Thinking Model | Description |
|-----------|---------------|-------------------|-------------|
| Context Length | 32768 | 16384 | Thinking requires more context for the reasoning process |
| GPU Offload | Maximum | Maximum | Maximize GPU acceleration |
| CPU Thread Pool Size | Maximum | Maximum | Automatically set based on CPU core count |
| Eval Batch Size | 4096 | 4096 | Evaluation batch size |
| Max Concurrent Predictions | 1 | 1 | Concurrent prediction count |
| Min P Sampling | 0 | 0 | — |

**Inference Settings:**

| Parameter | Value | Description |
|-----------|-------|-------------|
| Temperature | 0.7 | Controls output randomness |
| Context Overflow | Truncate Middle | Truncates the middle when context overflows |

**Sampling Settings:**

| Parameter | Value |
|-----------|-------|
| Top K | 20 |
| Repetition Penalty ✅ | 1.1 |
| Presence Penalty | ❌ Disabled |
| Top P ✅ | 0.8 |
| Min P ✅ | 0 |

#### 4.5 Start LM Studio Server

1. In LM Studio, click the **↔️ Developer** tab on the left sidebar
2. Verify the Server status is **Running** on port `1234`
3. The system will **automatically load/unload models via API** when starting a Task — no manual operation needed

> **Note:** The system automatically performs the following each time a Task starts:
>
> 1. Lists all currently loaded models
> 2. Unloads all loaded models
> 3. Loads the model specified by `lmstudio.load_model` in `task.json`

---

## Configuration

### System Config

**`system/server/static/config.json`** — Dashboard configuration:

```json
{
    "server": {
        "host": "127.0.0.1",         // Local machine address
        "port": 8000                  // Dashboard port
    },
    "taskUi": {
        "port": 8501                  // Default Task UI port
    }
}
```

### Hardware Config

**`tasks/common_config.json`** — Shared hardware and network configuration for all Tasks:

#### Current Hardware Models

| Device | Model |
|---|---|
| Pneumatic pressure pump | FluidicLab PC1 |
| Microscope | Olympus IX83 |
| Camera | ToupTek VTP23-M |

The current component implementations are written for the hardware models listed above. To use a different hardware model, modify or add its driver under `system/components/base/` and keep the implementation compliant with the corresponding abstract interface. Pressure controller implementations must conform to `BasePressureController` in `system/components/base/pressure/base.py`, and camera implementations must conform to `BaseCamera` in `system/components/base/camera/base.py`. The microscope is currently recorded as the experimental platform; if software control is added for another microscope, define its component abstraction and implementation under the same component layer before connecting it to Task logic.

```json
{
    "camera": {
        "type": "toupcam",            // Camera type
        "rtsp_url": "rtsp://127.0.0.1:8554/test"
    },
    "hardware": {
        "pressure_controller_port": "COM3"   // Pressure controller serial port
    },
    "server": {
        "api_port": 8002,             // Task API port
        "agent_port": 8001,           // Agent Server port
        "frontend_port": 8501,        // Task UI dev server port
        "host": "127.0.0.1"          // Local service binding IP
    }
}
```

> The default network configuration is for local access only.
> If another computer needs to access this system, change the following `127.0.0.1` values to the LAN IPv4 address of the computer running the system, for example `192.168.x.x`:
> - `server.host` in `system/server/static/config.json`
> - `camera.rtsp_url`, the RTSP URL inside `camera.ffmpeg_command`, and `server.host` in `tasks/common_config.json`
> - `server.host` and proxy `target` addresses in each `tasks/*/ui/vite.config.js`
> Also allow ports `8000`, `8001`, `8002`, `8501`, and `8554` through the firewall.

### Task Config

Each Task directory contains a **`task.json`** that defines the task name, LLM configuration, and behavior:

```json
{
    "name": "Task Display Name",
    "description": "Task description",
    "entry_point": "logic.py",
    "version": "1.0.0",
    "config": {
        "llm": {
            "model": "qwen3.5-27b",                    // OpenAI API model name
            "model_server": "http://127.0.0.1:1234/v1", // LM Studio endpoint
            "api_key": "EMPTY"
        },
        "lmstudio": {
            "load_model": "lmstudio-community/qwen3.5-27b"  // LM Studio model key
        },
        "agent": {
            "system_message": "System prompt..."
        }
    }
}
```

**Key fields:**
- `llm.model` — Model name used when calling the OpenAI-compatible API
- `lmstudio.load_model` — Full model key for LM Studio loading (found in the LLM column on the LM Studio My Models page)
- If `lmstudio.load_model` is not set, automatic model loading/unloading is skipped on startup

> ⚠️ **You MUST update `lmstudio.load_model` in all task.json files on first deployment!**
>
> The `load_model` value must exactly match the model key displayed in LM Studio. The following files need to be checked and modified:
>
> - `tasks/reagent_preparation/task.json`
> - `tasks/liposome_gen/task.json`
> - `tasks/treatment/task.json`
>
> In LM Studio → **My Models**, the LLM column shows the model key (e.g., `lmstudio-community/qwen3.5-27b`).
> For Tasks that need Thinking disabled, set `load_model` to the No-Thinking copy (e.g., `rx0/qwen3.5-27b-no_thinking`).

---

## Running the System

### Quick Start

```bash
cd new_system

# Make sure the conda environment is activated
conda activate microfluidics

# Start the main dashboard
python start_system.py
```

Open `http://127.0.0.1:8000` in a browser to access the Microfluidics AutoPilot dashboard.

### Startup Flow

1. **`start_system.py`** starts the FastAPI main server (port 8000)
2. The dashboard displays all available Tasks
3. Click the **Start** button on a Task card to launch the corresponding task
4. The Engine launches the Task's `logic.py` as a **subprocess**
5. The Task subprocess automatically starts:
   - LM Studio model loading (if `lmstudio.load_model` is configured)
   - Agent Server (port 8001)
   - Task API Server (port 8002)
   - Task UI dev server (port 8501)
6. The dashboard automatically redirects to the Task UI page

### Start a Single Task (for debugging)

```bash
cd tasks/reagent_preparation
python logic.py
```

---

## Project Structure

```
├── start_system.py                 # System entry point
├── requirement.txt                 # Python dependencies
├── README.md                       # English documentation
├── README_zh.md                    # Chinese documentation
├── LICENSE
│
├── system/                         # System framework layer
│   ├── core/
│   │   └── engine.py               # Task engine (scan/start/stop Tasks)
│   ├── server/
│   │   ├── main.py                 # Main FastAPI server
│   │   └── static/                 # Dashboard frontend
│   │       ├── index.html          # Dashboard page
│   │       ├── config.json         # Server configuration
│   │       ├── logo.png            # System logo
│   │       └── tailwindcss.js      # Tailwind CSS runtime
│   ├── task/
│   │   ├── __init__.py
│   │   ├── base_logic.py           # Task base class (Agent init/UI/lifecycle)
│   │   └── base_mcp.py             # MCP base utilities
│   └── components/
│       └── base/
│           ├── agent/              # AI Agent component
│           │   ├── __init__.py
│           │   ├── core.py         # Agent wrapper (qwen_agent)
│           │   ├── server.py       # Agent streaming API server
│           │   └── ui/             # Agent chat interface (React + Vite)
│           ├── camera/             # Camera component
│           │   ├── base.py         # Camera base class
│           │   ├── controller.py   # Camera controller
│           │   ├── toupcam.py      # ToupCam SDK bindings
│           │   ├── toupcam.dll     # ToupCam native driver
│           │   └── ui/             # Camera stream UI
│           └── pressure/           # Pressure controller component
│               ├── base.py         # Pressure base class
│               ├── controller.py   # Pressure controller driver
│               ├── fluidlab.py     # FluidLab integration
│               └── calibration_data.json
│
└── tasks/                          # Experiment tasks (extensible)
    ├── common_config.json          # Shared hardware/network config
    ├── liposome_gen/               # Liposome generation task
    │   ├── task.json               # Task configuration
    │   ├── logic.py                # Task logic (hardware control + detection)
    │   ├── workflow.txt            # Agent workflow
    │   ├── mcp_server.py           # MCP tool definitions
    │   └── ui/                     # Task-specific frontend
    ├── reagent_preparation/        # Reagent preparation task
    │   ├── task.json
    │   ├── logic.py
    │   ├── workflow.txt
    │   └── ui/
    └── treatment/                  # Treatment process task
        ├── task.json
        ├── logic.py
        ├── workflow.txt
        ├── mcp_server.py
        └── ui/
```

---

## Development Guide: Creating a New Task

### 1. Create a Task Directory

```bash
mkdir tasks/my_new_task
```

### 2. Create task.json

```json
{
    "name": "My New Task",
    "description": "Task description",
    "entry_point": "logic.py",
    "version": "1.0.0",
    "config": {
        "llm": {
            "model": "qwen3.5-27b",
            "model_server": "http://127.0.0.1:1234/v1",
            "api_key": "EMPTY"
        },
        "lmstudio": {
            "load_model": "lmstudio-community/qwen3.5-27b"
        },
        "agent": {
            "system_message": "Your system prompt"
        }
    }
}
```

### 3. Create logic.py

```python
from system.task import BaseTaskLogic

class MyNewTask(BaseTaskLogic):
    def __init__(self):
        super().__init__()

    def start(self):
        print("Starting My New Task...")
        # Custom initialization (hardware, etc.)
        super().start()  # Start Agent + UI

    def stop(self):
        # Custom cleanup
        super().stop()

    def get_status(self):
        return {"mode": "READY", "message": "Task Ready"}

if __name__ == "__main__":
    MyNewTask().run_as_main()
```

### 4. Create MCP Tools

If the Agent needs to call hardware functions, create `mcp_server.py`:

```python
from fastmcp import FastMCP
mcp = FastMCP("my_task_tools")

@mcp.tool()
async def my_tool(param: str) -> str:
    """Tool description"""
    # Call hardware via Task API
    return "result"

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

> `BaseTaskLogic` automatically detects `mcp_server.py` and registers it as an Agent tool.

### 5. Create workflow.txt

Define the Agent's workflow steps. The Agent follows this file to guide the experiment process.

### 6. Refresh the Dashboard

Restart the main server or refresh the browser — the new Task will automatically appear on the dashboard.

---

## Troubleshooting

### LM Studio Connection Failed

```
Warning: Cannot connect to LM Studio at http://127.0.0.1:1234. Is it running?
```

**Solution:** Open LM Studio → Developer → Verify the Server status is Running.

### LaTeX Formulas Not Rendering in Agent Chat

Make sure the base Agent UI has been built:
```bash
cd system/components/base/agent/ui
npm run build
```

### Task UI Shows Blank Page

Make sure the corresponding Task's frontend dependencies are installed:
```bash
cd tasks/<task_name>/ui
npm install
```
