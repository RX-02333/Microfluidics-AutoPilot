
import os
import time
import threading
import cv2
import numpy as np
from ultralytics import YOLO
from fastapi import FastAPI

from system.task import BaseTaskLogic
from system.components.base.pressure.controller import PressureController
from system.components.base.camera.controller import CameraFactory


class TreatmentTask(BaseTaskLogic):
    def __init__(self):
        super().__init__()

        # Task-specific state
        self.is_running = False
        self.mode = "IDLE"
        self.latest_result = {}
        self.target_x = 255
        self.pressure_adjustment_enabled = False
        
        # Interface detection
        self.interface_detected = False
        self.interface_monitor_thread = None
        
        # Hardware
        hard_cfg = self.config.get('hardware', {})
        self.pressure_ctrl = PressureController(port=hard_cfg.get('pressure_controller_port', 'COM3'))
        
        cam_cfg = self.config.get('camera', {})
        try:
             self.camera_ctrl = CameraFactory.create_camera(
                 cam_cfg.get('type', 'toupcam'), 
                 rtsp_url=cam_cfg.get('rtsp_url'),
                 ffmpeg_command=cam_cfg.get('ffmpeg_command')
             )
        except ValueError as e:
             print(f"Error creating camera: {e}")
             self.camera_ctrl = None
        self.yolo_model = None
        self.channel_model = None
        
        # Crop settings
        self.crop_size = 640
        self.img_width = 1920 
        self.img_height = 1200

        self._stop_event = threading.Event()
        self._thread = None
        
        # Channel Detection
        self.frame_count_channel_detection = 0
        self.channel_left_x = None
        
        # Pressure adjustment frame counter
        self.frame_count_treatment_adjustment = 0

        # Treatment Timer
        self.treatment_timer_active = False
        self.treatment_start_time = 0
        self.treatment_duration = 15 * 60  # 15 minutes

    def start(self):
        print("Initializing Treatment Task...")
        try:
            self.pressure_ctrl.initialize()
            if self.camera_ctrl:
                self.camera_ctrl.initialize()
            
            model_cfg = self.config.get('models', {})
            model_path = model_cfg.get('interface_model_path', 'interface.engine')
            channel_model_path = model_cfg.get('channel_model_path', 'channel.engine')

            if not os.path.isabs(model_path):
                model_path = os.path.join(self._task_dir, model_path)
            if not os.path.isabs(channel_model_path):
                channel_model_path = os.path.join(self._task_dir, channel_model_path)

            if os.path.exists(model_path):
                self.yolo_model = YOLO(model_path)
            else:
                print(f"Warning: Model {model_path} not found.")

            if os.path.exists(channel_model_path):
                self.channel_model = YOLO(channel_model_path)
            else:
                print(f"Warning: Model {channel_model_path} not found.")
            
            self._thread = threading.Thread(target=self._control_loop, daemon=True)
            self._thread.start()
            
            # Initialize Agent + UI (base class)
            super().start()
            
        except Exception as e:
            print(f"Initialization failed: {e}")

    def stop(self):
        self._stop_event.set()
        if self.camera_ctrl:
            self.camera_ctrl.close()
        if self.pressure_ctrl and hasattr(self.pressure_ctrl, 'stop'):
            self.pressure_ctrl.stop()
        super().stop()  # UI cleanup

    # ---------- Control Loop ----------
    def _monitor_interface_formation(self):
        print("Interface monitor thread started")
        while self.mode == "TREATMENT":
            if self.interface_detected:
                time.sleep(2)
                print("Qualified gas-liquid interface formed!")
                self._send_ui_message("Qualified gas-liquid interface formed!", msg_type="user")
                break
            time.sleep(0.1)

    def _control_loop(self):
        print("Control loop started")
        while not self._stop_event.is_set():
            loop_start = time.perf_counter()
            try:
                frame = self.camera_ctrl.get_latest_frame() if self.camera_ctrl else None
                if frame is None:
                    time.sleep(0.01)
                    continue
                
                h, w = frame.shape
                self.img_width = w
                self.img_height = h
                
                crop_start_x = (w - self.crop_size) // 2
                crop_start_y = (h - self.crop_size) // 2
                cropped = frame[crop_start_y:crop_start_y+self.crop_size, crop_start_x:crop_start_x+self.crop_size]
                
                x_max_detected = 0
                
                if self.mode == "TREATMENT":
                    self.frame_count_treatment_adjustment += 1
                    
                    if self.treatment_timer_active:
                        elapsed_time = time.time() - self.treatment_start_time
                        if elapsed_time >= self.treatment_duration:
                            self.treatment_timer_active = False
                            self._send_ui_message("treatment timer complete", msg_type="user")
                            print("Treatment timer finished.")
                    
                    self.frame_count_channel_detection += 1
                    if self.frame_count_channel_detection >= 10:
                        self.frame_count_channel_detection = 0
                        channel_x = self._process_channel_detection(cropped)
                        if channel_x is not None:
                            self.channel_left_x = channel_x
                            self.target_x = channel_x
                    
                    if self.yolo_model:
                        results = self.yolo_model(cropped, stream=True, verbose=False, conf=0.6, task="segment")
                        x_max_overall = 0
                        interface_found = False
                        
                        for res in results:
                            if res is not None and res.boxes is not None and len(res.boxes) > 0:
                                for box in res.boxes:
                                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                                    x1_abs = int(x1) + crop_start_x
                                    y1_abs = int(y1) + crop_start_y
                                    x2_abs = int(x2) + crop_start_x
                                    y2_abs = int(y2) + crop_start_y
                                    
                                    if x2_abs > x_max_overall:
                                        x_max_overall = x2_abs
                                    if x2_abs > 0:
                                        interface_found = True
                        
                        x_max_detected = x_max_overall
                        
                        if interface_found and not self.interface_detected:
                            self.interface_detected = True
                            print("Interface detected!")
                    
                    if self.frame_count_treatment_adjustment >= 120:
                        self.frame_count_treatment_adjustment = 0
                        if self.pressure_adjustment_enabled and x_max_detected > 0:
                            self.adjust_pressure(x_max_detected, crop_start_x)
                
                # Update State
                self.latest_result = {"x_max": x_max_detected}
                
                # Draw UI
                display_frame = frame.copy()
                self._draw_ui(display_frame, x_max_detected, crop_start_x, crop_start_y)
                
                # Stream to FFmpeg
                if self.camera_ctrl:
                    self.camera_ctrl.stream_to_ffmpeg(display_frame)
                
                # FPS Control
                elapsed = time.perf_counter() - loop_start
                sleep_time = max(0, 0.016 - elapsed)
                time.sleep(sleep_time)
                
            except Exception as e:
                print(f"Error in loop: {e}")
                time.sleep(1)

    def _draw_ui(self, img, x_max, start_x, start_y):
        cv2.rectangle(img, (start_x, start_y), (start_x+self.crop_size, start_y+self.crop_size), (255, 255, 255), 2)
        
        if self.mode == "TREATMENT":
            target_x = self.target_x + start_x
            cv2.line(img, (target_x, start_y + 20), (target_x, start_y + 600), (255, 255, 255), 2)
            cv2.line(img, (target_x + 10, start_y + 20), (target_x + 10, start_y + 600), (255, 255, 255), 2)
            if x_max > 0:
                 cv2.line(img, (x_max, start_y + 250), (x_max, start_y + 400), (0, 255, 0), 2)

    def _process_channel_detection(self, cropped_img):
        if not self.channel_model:
            return None
        try:
            results = self.channel_model(cropped_img, stream=True, verbose=False, conf=0.5)
            for result in results:
                if result.boxes is not None and len(result.boxes) > 0:
                    for box in result.boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        return int(x1)
            return None
        except Exception as e:
            print(f"Channel detection error: {e}")
            return None

    def adjust_pressure(self, x_max_detected, crop_start_x):
        if x_max_detected == 0:
            return
        target_abs = self.target_x + crop_start_x
        current_p = self.pressure_ctrl.get_target_pressures()
        adjusted = False
        
        if x_max_detected < target_abs + 2:
            current_p[1] += 5.0
            current_p[2] += 5.0
            current_p[0] -= 10.0
            adjusted = True
        elif x_max_detected > target_abs + 7:
            current_p[1] -= 5.0
            current_p[2] -= 5.0
            current_p[0] += 10.0
            adjusted = True
            
        if adjusted:
             for i in range(3):
                 current_p[i] = max(min(current_p[i], 2000), 0)
             self.pressure_ctrl.set_pressure(current_p[0], current_p[1], current_p[2])

    # ---------- Public API ----------
    def switch_mode(self, mode: str):
        mode_upper = mode.upper()
        if mode_upper == 'TREATMENT':
            if self.mode == "TREATMENT":
                return {"status": "warning", "message": "Already in treatment mode"}
            self.mode = "TREATMENT"
            self.interface_detected = False
            self.interface_monitor_thread = threading.Thread(target=self._monitor_interface_formation, daemon=True)
            self.interface_monitor_thread.start()
            return {"status": "success", "message": "Treatment mode started"}
        elif mode_upper == 'IDLE':
            self.mode = "IDLE"
            self.pressure_adjustment_enabled = False
            return {"status": "success", "message": "Switched to idle mode"}
        else:
            return {"status": "error", "message": f"Invalid mode: {mode}. Use 'treatment' or 'idle'."}

    def set_pressure(self, p1=None, p2=None, p3=None, p4=None):
        self.pressure_ctrl.set_pressure(p1, p2, p3, p4)
        return {"status": "success"}

    def start_treatment_timer(self):
        if self.treatment_timer_active:
            return {"status": "warning", "message": "Timer already running"}
        self.treatment_start_time = time.time()
        self.treatment_timer_active = True
        return {"status": "success", "message": "Timer started (15 min)"}

    def set_treatment_pressure_adjustment(self, enabled: bool):
        self.pressure_adjustment_enabled = enabled
        return {
            "status": "success", 
            "message": f"Treatment pressure adjustment {'enabled' if enabled else 'disabled'}.",
            "pressure_adjustment_enabled": self.pressure_adjustment_enabled
        }

    def get_status(self):
        if self.treatment_timer_active:
            elapsed = time.time() - self.treatment_start_time
            remaining = max(0, self.treatment_duration - elapsed)
        else:
            remaining = self.treatment_duration
        return {
            "mode": self.mode,
            "is_running": self.is_running,
            "result": self.latest_result,
            "interface_detected": self.interface_detected,
            "pressure_adjustment_enabled": self.pressure_adjustment_enabled,
            "treatment_timer_active": self.treatment_timer_active,
            "timer_remaining": remaining
        }

    def create_api_app(self):
        app = super().create_api_app()

        @app.post("/control/switch_mode")
        def api_switch_mode(mode: str):
            return self.switch_mode(mode)

        @app.post("/control/pressure")
        def api_pressure(p1: float = None, p2: float = None, p3: float = None, p4: float = None):
            return self.set_pressure(p1, p2, p3, p4)

        @app.post("/control/start_timer")
        def api_start_timer():
            return self.start_treatment_timer()

        @app.post("/control/set_pressure_adjustment")
        def api_set_pressure_adjustment(enabled: bool):
            return self.set_treatment_pressure_adjustment(enabled)

        return app


if __name__ == "__main__":
    TreatmentTask().run_as_main()
