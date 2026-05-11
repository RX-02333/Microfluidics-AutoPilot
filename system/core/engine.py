
import os
import json
import subprocess
import signal
import sys
import time
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class TaskInfo:
    id: str
    name: str
    description: str
    path: str
    entry_point: str
    config: dict

class Engine:
    def __init__(self, system_root: str):
        self.system_root = system_root
        self.tasks_dir = os.path.join(system_root, "tasks")
        self.available_tasks: Dict[str, TaskInfo] = {}
        self.active_processes: Dict[str, subprocess.Popen] = {}
        self.current_active_task: Optional[str] = None
        
        self._scan_tasks()

    def _scan_tasks(self):
        """Scan tasks directory for task.json files"""
        self.available_tasks.clear()
        if not os.path.exists(self.tasks_dir):
            os.makedirs(self.tasks_dir)
            return

        for task_id in os.listdir(self.tasks_dir):
            task_path = os.path.join(self.tasks_dir, task_id)
            if not os.path.isdir(task_path):
                continue
            
            config_file = os.path.join(task_path, "task.json")
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        
                    task_info = TaskInfo(
                        id=task_id,
                        name=config.get("name", task_id),
                        description=config.get("description", ""),
                        path=task_path,
                        entry_point=config.get("entry_point", "logic.py"),
                        config=config
                    )
                    self.available_tasks[task_id] = task_info
                except Exception as e:
                    print(f"Error loading task {task_id}: {e}")

    def get_task_list(self) -> List[dict]:
        """Return list of available tasks"""
        self._scan_tasks() # Re-scan to catch new tasks
        return [
            {
                "id": t.id, 
                "name": t.name, 
                "description": t.description,
                "status": "running" if t.id == self.current_active_task else "stopped",
                "frontend_port": t.config.get("config", {}).get("frontend_port")
            }
            for t in self.available_tasks.values()
        ]

    def start_task(self, task_id: str):
        """Start a specific task"""
        if task_id not in self.available_tasks:
            raise ValueError(f"Task {task_id} not found")
        
        # Check if already running
        if self.current_active_task == task_id:
            if self._is_process_alive(task_id):
                return {"status": "already_running", "task_id": task_id}
            else:
                # Process died, cleanup
                self.stop_current_task()

        # Stop currently running task if any (assuming single task focus for now, or decoupled?)
        # User said "switch task", implying replacement.
        if self.current_active_task:
            self.stop_current_task()
            
        task_info = self.available_tasks[task_id]
        script_path = os.path.join(task_info.path, task_info.entry_point)
        
        if not os.path.exists(script_path):
             raise FileNotFoundError(f"Entry point {script_path} not found")
             
        # Launch subprocess
        # We assume the task runs in the same python environment
        cmd = [sys.executable, script_path]
        
        try:
            # Set PYTHONPATH to include system root
            env = os.environ.copy()
            env["PYTHONPATH"] = self.system_root + os.pathsep + env.get("PYTHONPATH", "")
            
            # New process group for easier cleanup?
            process = subprocess.Popen(
                cmd, 
                cwd=task_info.path,
                env=env
                # creationflags=subprocess.CREATE_NEW_CONSOLE # Optional: visible window?
            )
            self.active_processes[task_id] = process
            self.current_active_task = task_id
            print(f"Started task {task_id} (PID: {process.pid})")
            return {"status": "started", "task_id": task_id, "pid": process.pid}
        except Exception as e:
            print(f"Failed to start task {task_id}: {e}")
            raise e

    def stop_current_task(self):
        """Stop the currently active task"""
        if not self.current_active_task:
            return {"status": "no_active_task"}
            
        task_id = self.current_active_task
        self.stop_task(task_id)
        return {"status": "stopped", "task_id": task_id}
        
    def stop_task(self, task_id: str):
        """Stop a specific task"""
        if task_id in self.active_processes:
            process = self.active_processes[task_id]
            if process.poll() is None: # Running
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            
            del self.active_processes[task_id]
        
        if self.current_active_task == task_id:
            self.current_active_task = None
            
    def _is_process_alive(self, task_id: str) -> bool:
        if task_id not in self.active_processes:
            return False
        return self.active_processes[task_id].poll() is None
