
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
import json

# Add system root to path to import core
current_dir = os.path.dirname(os.path.abspath(__file__))
system_root = os.path.dirname(os.path.dirname(current_dir)) # new_system/
if system_root not in sys.path:
    sys.path.insert(0, system_root)

from system.core.engine import Engine

# Load configuration
config_path = os.path.join(current_dir, "static", "config.json")
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

app = FastAPI(title="Microfluidics Control System")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Engine
engine = Engine(system_root)

@app.get("/api/tasks")
async def get_tasks():
    return engine.get_task_list()

@app.post("/api/tasks/{task_id}/start")
async def start_task(task_id: str):
    try:
        result = engine.start_task(task_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tasks/stop")
async def stop_task():
    return engine.stop_current_task()



# Mount static files for frontend
static_dir = os.path.join(current_dir, "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config["server"]["host"], port=config["server"]["port"])
