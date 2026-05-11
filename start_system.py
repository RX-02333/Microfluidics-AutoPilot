
import os
import sys
import uvicorn

# Ensure we can import system
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

if __name__ == "__main__":
    print("Starting Microfluidics Control System...")
    print("Server running at http://localhost:8000")
    
    # Run the main server
    # We use os.system or subprocess to run it, or import and run.
    # Uvicorn run programmatically is better.
    
    uvicorn.run("system.server.main:app", host="0.0.0.0", port=8000, reload=True)
