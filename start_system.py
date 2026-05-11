
import os
import sys
import json
import uvicorn

# Ensure we can import system
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

if __name__ == "__main__":
    config_path = os.path.join(current_dir, "system", "server", "static", "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    host = config["server"]["host"]
    port = config["server"]["port"]

    print("Starting Microfluidics Control System...")
    print(f"Server running at http://{host}:{port}")
    
    # Run the main server
    # We use os.system or subprocess to run it, or import and run.
    # Uvicorn run programmatically is better.
    
    uvicorn.run("system.server.main:app", host=host, port=port, reload=True)
