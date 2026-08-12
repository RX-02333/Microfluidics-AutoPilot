
import sys
import os
import threading
import time
import json
import subprocess
import signal
import uvicorn
from fastapi import FastAPI


def _setup_project_path():
    """Add project root to sys.path. Works from any depth under new_system/."""
    # Walk up from this file (system/task/base_logic.py) to find project root
    current = os.path.dirname(os.path.abspath(__file__))
    # system/task/ -> system/ -> new_system/ (project root)
    project_root = os.path.abspath(os.path.join(current, "../../"))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    return project_root

PROJECT_ROOT = _setup_project_path()

from system.components.base.agent.core import Agent
from system.components.base.agent.server import create_agent_server


class BaseTaskLogic:
    """
    Base class for all Tasks, providing common functionalities:
    - Configuration loading (common_config.json + task.json override)
    - Agent initialization and management
    - UI Server start and stop
    - Port cleanup
    - Signal handling and process lifecycle management
    
    Subclasses must call the base constructor via super().__init__().
    """

    def __init__(self):
        # ========== Determine Task Directory (based on subclass file location) ==========
        subclass_file = sys.modules[self.__class__.__module__].__file__
        self._task_dir = os.path.dirname(os.path.abspath(subclass_file))

        # ========== Configuration Loading ==========
        task_json_path = os.path.join(self._task_dir, "task.json")
        common_config_path = os.path.join(self._task_dir, "../common_config.json")

        self.config = {}

        # Load Common Config first
        try:
            if os.path.exists(common_config_path):
                with open(common_config_path, 'r', encoding='utf-8') as f:
                    self._deep_update(self.config, json.load(f))
        except Exception as e:
            print(f"Error loading common_config.json: {e}")

        # Load Task Override (deep merge)
        try:
            with open(task_json_path, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
                self._deep_update(self.config, task_data.get("config", {}))
        except Exception as e:
            print(f"Error loading task.json: {e}")

        # ========== Common State ==========
        self.agent = None
        self.agent_app = None
        self.ui_process = None
        self.ui_port = None

    # ---------- Config Utilities ----------
    @staticmethod
    def _deep_update(d, u):
        """Recursively merge dictionary u into d (in-place)"""
        for k, v in u.items():
            if isinstance(v, dict):
                d[k] = BaseTaskLogic._deep_update(d.get(k, {}), v)
            else:
                d[k] = v
        return d

    # ---------- LM Studio Model Management ----------
    def _prepare_lmstudio_model(self):
        """
        Prepare LM Studio: unload all loaded models, then load the model specified in config.
        Uses LM Studio REST API: /api/v1/models, /api/v1/models/unload, /api/v1/models/load
        
        Config: lmstudio.load_model - the model key to load (e.g. "qwen/qwen3.5-27b-gguf")
        """
        import requests

        lmstudio_cfg = self.config.get('lmstudio', {})
        target_model = lmstudio_cfg.get('load_model', '')

        llm_cfg = self.config.get('llm', {})
        model_server = llm_cfg.get('model_server', 'http://127.0.0.1:1234/v1')

        # Extract base URL (remove /v1 suffix if present)
        base_url = model_server.rstrip('/')
        if base_url.endswith('/v1'):
            base_url = base_url[:-3]

        if not target_model:
            print("No lmstudio.load_model specified, skipping LM Studio model preparation.")
            return

        print(f"Preparing LM Studio model: {target_model}")

        try:
            # Step 1: List all models and find loaded instances
            resp = requests.get(f"{base_url}/api/v1/models", timeout=10)
            resp.raise_for_status()
            models_data = resp.json()

            loaded_ids = []
            for model in models_data.get('models', []):
                for instance in model.get('loaded_instances', []):
                    loaded_ids.append(instance['id'])

            # Step 2: Unload all loaded models
            if loaded_ids:
                print(f"Unloading {len(loaded_ids)} loaded model(s): {loaded_ids}")
                for instance_id in loaded_ids:
                    try:
                        resp = requests.post(
                            f"{base_url}/api/v1/models/unload",
                            json={"instance_id": instance_id},
                            timeout=30
                        )
                        resp.raise_for_status()
                        print(f"  Unloaded: {instance_id}")
                    except Exception as e:
                        print(f"  Warning: Failed to unload {instance_id}: {e}")
            else:
                print("No models currently loaded.")

            # Step 3: Load the target model
            print(f"Loading model: {target_model} ...")
            resp = requests.post(
                f"{base_url}/api/v1/models/load",
                json={"model": target_model},
                timeout=300  # Model loading can take a long time
            )
            resp.raise_for_status()
            result = resp.json()
            load_time = result.get('load_time_seconds', '?')
            print(f"Model '{target_model}' loaded successfully in {load_time}s")

        except requests.ConnectionError:
            print(f"Warning: Cannot connect to LM Studio at {base_url}. Is it running?")
        except Exception as e:
            print(f"Warning: LM Studio model preparation failed: {e}")

    # ---------- Agent Initialization ----------
    def initialize_agent(self, tools=None):
        """
        Initialize Agent and Agent Server.
        
        Args:
            tools: Agent tool list.
                   - None: Auto-detect mcp_server.py, configure as MCP tool if exists, else pure chat
                   - []: Pure chat mode (load no tools)
                   - [{"mcpServers": {...}}]: Manually specify MCP config
        """
        # Prepare LM Studio model before agent initialization
        self._prepare_lmstudio_model()

        agent_cfg = self.config.get('agent', {})

        if tools is None:
            # Auto-detect mcp_server.py
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
        print(f"Agent initialized ({'MCP' if tools else 'pure chat'} mode)")

    # ---------- UI Server ----------
    def start_ui_server(self):
        """Start frontend UI dev server (npm start)"""
        ui_dir = os.path.join(self._task_dir, "ui")
        if not os.path.exists(ui_dir):
            print(f"UI directory not found: {ui_dir}")
            return

        server_cfg = self.config.get('server', {})
        self.ui_port = server_cfg.get('frontend_port', server_cfg.get('ui_port', 8501))
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

    # ---------- Lifecycle ----------
    def start(self):
        """
        Start Task. Subclasses override this method to add hardware initialization etc.,
        then call super().start() to complete Agent and UI startup.
        """
        self.initialize_agent()
        self.start_ui_server()

    def stop(self):
        """
        Stop Task. Subclasses override this method to add hardware cleanup,
        then call super().stop() to complete UI shutdown.
        """
        # Kill UI process
        if self.ui_process:
            try:
                self.ui_process.terminate()
                try:
                    self.ui_process.wait(timeout=3)
                except:
                    subprocess.run(
                        ['taskkill', '/F', '/T', '/PID', str(self.ui_process.pid)],
                        capture_output=True, timeout=5
                    )
                print("UI Server stopped")
            except Exception as e:
                print(f"Error stopping UI process: {e}")

        # Port cleanup
        if self.ui_port:
            time.sleep(0.5)
            self._kill_port_process(self.ui_port)
            print(f"UI port {self.ui_port} cleanup completed")

    def get_status(self):
        """Return task status. Subclasses should override this method."""
        return {"mode": "READY", "message": "Task Ready"}

    # ---------- Port Cleanup ----------
    def _kill_port_process(self, port):
        """Kill process occupying specified port"""
        try:
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    pid = line.split()[-1]
                    try:
                        subprocess.run(
                            ['taskkill', '/F', '/PID', pid],
                            capture_output=True, timeout=5
                        )
                        print(f"Killed process {pid} occupying port {port}")
                    except:
                        pass
        except Exception as e:
            print(f"Error killing port process: {e}")

    # ---------- UI Messages ----------
    def _send_ui_message(self, message, msg_type="system"):
        """Send message to frontend UI"""
        try:
            import requests
            server_cfg = self.config.get('server', {})
            ui_port = server_cfg.get('frontend_port', server_cfg.get('ui_port', 8501))
            url = f"http://localhost:{ui_port}/ui/add_{msg_type}_message"
            requests.post(url, json={"message": message}, timeout=1)
        except:
            pass

    def _send_agent_message(self, message):
        """Send message to Agent to trigger AI processing"""
        def _send():
            try:
                import requests
                server_cfg = self.config.get('server', {})
                host = server_cfg.get('host', 'localhost')
                agent_port = server_cfg.get('agent_port', 8001)
                url = f"http://{host}:{agent_port}/chat/stream"
                response = requests.post(
                    url,
                    json={"history": [{"role": "user", "content": message}]},
                    timeout=30, stream=True
                )
                for line in response.iter_lines():
                    pass
            except Exception as e:
                print(f"Error sending agent notification: {e}")
        threading.Thread(target=_send, daemon=True).start()

    # ---------- Standard __main__ Entry ----------
    def create_api_app(self):
        """
        Create Task API FastAPI app.
        Subclasses override this method to register custom endpoints, calling super().create_api_app() first.
        """
        app = FastAPI()

        @app.get("/status")
        def api_status():
            return self.get_status()

        @app.on_event("shutdown")
        def shutdown_event():
            self.stop()

        return app

    def run_as_main(self):
        """
        Standard __main__ startup entry. Subclasses call this in if __name__ == '__main__'.
        Automatically handles: signal registration, Task start, Agent Server (background thread), Task API Server (main thread blocking).
        """
        signal.signal(signal.SIGTERM, lambda s, f: (self.stop(), sys.exit(0)))
        signal.signal(signal.SIGINT, lambda s, f: (self.stop(), sys.exit(0)))

        try:
            self.start()

            # Agent Server in background thread
            def run_agent():
                cfg = self.config.get('server', {})
                host = cfg.get('host', '127.0.0.1')
                port = cfg.get('agent_port', 8001)
                print(f"Starting Agent Server on {host}:{port}")
                uvicorn.run(self.agent_app, host=host, port=port)

            threading.Thread(target=run_agent, daemon=True).start()

            # Task API Server in main thread (blocking)
            app = self.create_api_app()
            cfg = self.config.get('server', {})
            host = cfg.get('host', '127.0.0.1')
            port = cfg.get('api_port', 8002)
            print(f"Starting Task API Server on {host}:{port}")
            uvicorn.run(app, host=host, port=port)

        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            print(f"Error: {e}")
            self.stop()
