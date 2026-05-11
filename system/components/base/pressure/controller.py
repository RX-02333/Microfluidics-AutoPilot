import threading
import queue
import time
from typing import List, Optional, Any, Union
from .fluidlab import PressureControlLibrary
from .base import BasePressureController

class HardwarePressureController(BasePressureController):
    """Concrete implementation for actual hardware control."""
    
    def __init__(self, port="COM3"):
        self.cmd_queue = queue.Queue()
        self.is_running = True
        self.pressure_lib = PressureControlLibrary(port=port)
        self._calibration_data = None
        
        # State
        self.current_pressures = [0.0, 0.0, 0.0, 0.0] # P1, P2, P3, P4
        
        # Start worker thread
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def initialize(self):
        """Initialize connection and calibration (Synchronous)"""
        def _init_task():
            # In legacy, initialize() called load_calibration_data or calibrate
            # Here we assume we just load or init. 
            # The legacy fluidlab.initialize() returns calibration data.
            self._calibration_data = self.pressure_lib.initialize()
            return self._calibration_data
        
        future = queue.Queue()
        self.cmd_queue.put(("call", _init_task, future))
        result = future.get()
        if isinstance(result, Exception):
            raise result
        return result

    def set_pressure(self, p1=None, p2=None, p3=None, p4=None):
        """
        Async set pressure command.
        None means keep current value.
        """
        self.cmd_queue.put(("set", (p1, p2, p3, p4), None))

    def get_pressure_readings(self):
        """Synchronously get actual pressure readings from device"""
        future = queue.Queue()
        self.cmd_queue.put(("get_readings", None, future))
        result = future.get()
        if isinstance(result, Exception):
            raise result
        return result
        
    def get_target_pressures(self):
        """Get the current target pressures (state)"""
        return list(self.current_pressures)

    def _worker_loop(self):
        # Initialize internal state if needed? 
        # Actually initialize() should be called explicitly or lazily.
        # But we can't do much without calibration data.
        
        while self.is_running:
            try:
                task = self.cmd_queue.get(timeout=0.1)
                cmd_type, args, future = task
                
                try:
                    if cmd_type == "call":
                        func = args
                        res = func()
                        if future: future.put(res)
                        
                    elif cmd_type == "get_readings":
                        res = self.pressure_lib.read_pressures()
                        if future: future.put(res)
                        
                    elif cmd_type == "set":
                        p1, p2, p3, p4 = args
                        
                        # Update targets (handle None)
                        new_targets = list(self.current_pressures)
                        vals = [p1, p2, p3, p4]
                        for i, v in enumerate(vals):
                            if v is not None:
                                new_targets[i] = float(v)
                        
                        self.current_pressures = new_targets
                        
                        # Apply thresholds (legacy logic)
                        # Channels 1-3: < 20 -> 0
                        adjusted_targets = []
                        for i in range(3):
                            val = new_targets[i]
                            if val < 20: val = 0
                            val = max(0, min(2000, val)) # Clamp
                            adjusted_targets.append(val)
                            
                        # Channel 4: -20 < x < 20 -> 0 ??? Legacy: 
                        # if 0 <= adjusted_channel4 < 20: 0
                        # elif -20 < adjusted_channel4 < 0: 0
                        p4_val = new_targets[3]
                        if -20 < p4_val < 20:
                             p4_val = 0
                        p4_val = max(-1000, min(1000, p4_val)) # Clamp
                        adjusted_targets.append(p4_val)
                        
                        # Calculate input values using calibration
                        if self._calibration_data:
                            device_inputs = []
                            for i, target_val in enumerate(adjusted_targets):
                                # fluidlab.linear_interpolate returns a list, take [0]
                                input_val = self.pressure_lib.linear_interpolate(
                                    [self._calibration_data[f"channel_{i+1}"]], target_val
                                )[0]
                                device_inputs.append(input_val)
                            
                            # Set pressures
                            print(f"Target pressures: {new_targets} -> adjusted: {adjusted_targets}, device inputs: {device_inputs}")
                            self.pressure_lib.set_pressures(device_inputs)
                        else:
                            print("Warning: PressureController not initialized with calibration data")
                            
                        if future: future.put("done")

                except Exception as e:
                    print(f"Error in pressure worker: {e}")
                    if future: future.put(e)
                
            except queue.Empty:
                continue

    def stop(self):
        """Stop the pressure controller worker thread"""
        self.is_running = False
        if hasattr(self, 'worker_thread') and self.worker_thread:
            self.worker_thread.join(timeout=2)

# For backward compatibility
PressureController = HardwarePressureController
