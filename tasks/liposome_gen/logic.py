
import os
import threading
import time
import cv2
import numpy as np
from ultralytics import YOLO
from fastapi import FastAPI

from system.task import BaseTaskLogic
from system.components.base.pressure.controller import PressureController
from system.components.base.camera.controller import CameraFactory

class LiposomeGenTask(BaseTaskLogic):
    def __init__(self):
        super().__init__()

        # Task-specific state
        self.mode = "IDLE" 
        self.status_message = "Idle"
        self.data_log = []
        self.current_counts = []
        self.pressure_vesicle_data = []
        self.auto_troubleshooting_enabled = False
        self.troubleshooting_count = 0
        self.last_troubleshooting_time = 0
        
        # Recognition mode parameters
        self.recognition_sizes = []
        self.current_sizes = []
        self.recognition_num = 0
        self.recognition_mode_num = 0
        self.recognition_frame_count = 0
        self.target_liposome_size = 0
        self.is_size_adjustment_active = False
        self.liposome_size_bins = [x/10.0 for x in range(50, 255, 5)]
        
        # Crop settings
        self.crop_size = 640
        self.crop_offset_x = 100
        
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
             print("Camera initialized")
        except ValueError as e:
             print(f"Error creating camera: {e}")
             self.camera_ctrl = None
             
        self.yolo_model = None
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        print("Starting Liposome Gen Task...")
        try:
            self.pressure_ctrl.initialize()
            if self.camera_ctrl:
                 self.camera_ctrl.initialize()
            
            model_cfg = self.config.get('detection_model', {})
            model_path = model_cfg.get('path', 'lip.engine')
            if not os.path.isabs(model_path):
                model_path = os.path.join(self._task_dir, model_path)
                
            if os.path.exists(model_path):
                self.yolo_model = YOLO(model_path)
            else:
                print(f"YOLO model not found at {model_path}")
            
            # Start control loop
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._control_loop, daemon=True)
            self._thread.start()
            
            # Initialize Agent + UI (base class)
            super().start()
            
        except Exception as e:
            print(f"Start Error: {e}")

    def stop(self):
        self._stop_event.set()
        if self.camera_ctrl:
            self.camera_ctrl.close()
        if self.pressure_ctrl:
            self.pressure_ctrl.stop()
        super().stop()  # UI cleanup

    # initialize_agent inherited from BaseTaskLogic (auto-detects mcp_server.py)

    # ... [Rest of logic: _control_loop, _draw_ui, _send_ui_message, etc.] ...
    # Copying existing methods...

    def _control_loop(self):
        while not self._stop_event.is_set():
            loop_start = time.perf_counter()
            try:
                # ========================================
                # COMMON CODE (IDLE + GENERATION)
                # ========================================
                
                # Get current frame
                frame = self.camera_ctrl.get_latest_frame() if self.camera_ctrl else None
                if frame is None:
                    time.sleep(0.01)
                    continue
                
                h, w = frame.shape
                crop_start_x = w - self.crop_size - self.crop_offset_x
                crop_start_y = (h - self.crop_size) // 2
                
                # ========================================
                # MODE-SPECIFIC CODE
                # ========================================
                
                if self.mode == "GENERATION":
                    # GENERATION mode: liposome detection and size measurement
                    # Logic aligned with old system's recognition mode (30-frame batch settlement)
                    
                    self.recognition_frame_count += 1
                    cropped = frame[crop_start_y:crop_start_y+self.crop_size, crop_start_x:crop_start_x+self.crop_size]
                    
                    if self.yolo_model:
                        results = self.yolo_model(cropped, stream=True, verbose=False, conf=0.55)
                        # Process detection results: draw boxes + collect sizes (same as old _process_detection_results_for_recognition)
                        for r in results:
                            for xyxy in r.boxes.xyxy:
                                # Draw vesicle detection box (white, matching old system COLOR)
                                cv2.rectangle(frame, 
                                             (int(xyxy[0] + crop_start_x), int(xyxy[1] + crop_start_y)), 
                                             (int(xyxy[2] + crop_start_x), int(xyxy[3] + crop_start_y)), 
                                             (255, 255, 255), 2)
                                # Append size to flat list (same as old system)
                                self.recognition_sizes.append(
                                    round(float((int(xyxy[3]) - int(xyxy[1])) * 100 / 336), 1)
                                )
                    
                    # === 30-frame settlement (aligned with old system) ===
                    if self.recognition_frame_count % 30 == 0:
                        if self.recognition_sizes:
                            try:
                                self.current_sizes = self.recognition_sizes.copy()
                                vals, counts = np.unique(self.recognition_sizes, return_counts=True)
                                self.recognition_mode_num = float(vals[np.argmax(counts)])
                                self.recognition_num = len(self.recognition_sizes) // 30
                            except Exception as e:
                                print(f"Error calculating mode: {e}")
                                self.recognition_mode_num = 0
                                self.recognition_num = 0
                            self.recognition_sizes = []
                        else:
                            self.current_sizes = []
                            self.recognition_num = 0
                            self.recognition_mode_num = 0
                        self._auto_troubleshooting_check()
                    
                    # === 120-frame pressure adjustment (aligned with old system) ===
                    if self.recognition_frame_count >= 120:
                        self.recognition_frame_count = 0
                        if self.target_liposome_size > 0:
                            self._adjust_pressure_for_recognition()
                
                # ========================================
                # COMMON CODE (IDLE + GENERATION)
                # ========================================
                
                # Draw UI
                display_frame = frame.copy()
                cv2.rectangle(display_frame, (crop_start_x, crop_start_y), 
                             (crop_start_x+self.crop_size, crop_start_y+self.crop_size), (0, 255, 0), 2)
                
                if self.mode != "IDLE":
                    self._draw_ui(display_frame)
                else:
                    cv2.putText(display_frame, "IDLE", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                # Stream to FFmpeg
                if self.camera_ctrl:
                    self.camera_ctrl.stream_to_ffmpeg(display_frame)
                
                # FPS Control (Target 60 FPS = ~16.6ms)
                elapsed = time.perf_counter() - loop_start
                sleep_time = max(0, 0.016 - elapsed)
                time.sleep(sleep_time)
                
            except Exception as e:
                time.sleep(1)

    def _draw_ui(self, img):
        h, w = img.shape
        start_x = w - self.crop_size - self.crop_offset_x
        start_y = (h - self.crop_size) // 2
        cv2.rectangle(img, (start_x, start_y), (start_x+self.crop_size, start_y+self.crop_size), (255, 255, 255), 2)
        
        cv2.putText(img, f"Mode: {self.mode}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)
        cv2.putText(img, f"Count (avg):{int(self.recognition_num)} Size (mode):{self.recognition_mode_num}um", 
                    (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)
        cv2.putText(img, self.status_message, (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200,200,200), 1)

    # _send_ui_message inherited from BaseTaskLogic

    def _liposome_troubleshooting(self):
        try:
            current_p = self.pressure_ctrl.get_target_pressures()
            p1, p2, p3 = current_p[0], current_p[1], current_p[2]
            self.pressure_ctrl.set_pressure(p1, p2, 0)
            time.sleep(0.2)
            self.pressure_ctrl.set_pressure(p1, p2, p3)
            return True
        except Exception as e:
            print(f"Troubleshooting error: {e}")
            return False

    def _auto_troubleshooting_check(self):
        """Auto troubleshooting check (aligned with old system: checks recognition_num from 30-frame batch)"""
        if not self.auto_troubleshooting_enabled:
            return
            
        current_time = time.time()
        # Avoid frequent triggering (every 10 seconds)
        if current_time - self.last_troubleshooting_time < 10:
            return

        # Check recognition_num (avg count per frame from last 30-frame batch)
        if self.recognition_num < 10:
            print(f"Auto troubleshooting triggered: recognition_num {self.recognition_num} < 10")
            self._liposome_troubleshooting()
            self.troubleshooting_count += 1
            self.last_troubleshooting_time = current_time
            
            if self.troubleshooting_count >= 2:
                print("Troubleshooting failed twice, restarting process...")
                self.auto_troubleshooting_enabled = False
                self.troubleshooting_count = 0
                threading.Thread(target=self._restart_liposome_process, daemon=True).start()

    def _test_pressure_for_10_seconds(self, p1, p2, p3):
        print(f"Testing pressure: P1={p1}, P2={p2}, P3={p3}")
        self.pressure_ctrl.set_pressure(p1, p2, p3)
        time.sleep(0.5)
        
        # Use troubleshooting after setting pressure
        self._liposome_troubleshooting()
        
        # Record vesicle count every second for 10 seconds
        vesicle_counts = []
        for second in range(10):
            time.sleep(1)
            vesicle_count = self.recognition_num
            vesicle_counts.append(vesicle_count)
            print(f"  Second {second+1}: {vesicle_count} liposome")
        
        return vesicle_counts

    def _record_pressure_vesicle_data(self, p1, p2, p3, counts):
        data_entry = {
            'pressure_ch1': p1, 'pressure_ch2': p2, 'pressure_ch3': p3,
            'vesicle_counts': counts,
            'total_liposome': sum(counts),
            'max_liposome': max(counts) if counts else 0,
            'avg_liposome': sum(counts)/len(counts) if counts else 0
        }
        self.pressure_vesicle_data.append(data_entry)
        print(f"Recorded: P1={p1}, P2={p2}, P3={p3}, counts={counts}, total={sum(counts)}")

    def _find_best_pressure_combination(self):
        if not self.pressure_vesicle_data:
            return None, "No pressure data available"
        best_data = max(self.pressure_vesicle_data, key=lambda x: x['total_liposome'])
        successful_combinations = [data for data in self.pressure_vesicle_data if data['avg_liposome'] >= 5]
        if successful_combinations:
            best_data = max(successful_combinations, key=lambda x: x['total_liposome'])
            return best_data, f"Found successful combination with {best_data['avg_liposome']:.1f} avg liposome"
        else:
            return best_data, f"Best combination has {best_data['avg_liposome']:.1f} avg liposome (below threshold)"

    def _optimize_channel3_pressure(self, base_ch1, base_ch2):
        print(f"Optimizing channel 3 pressure with fixed P1={base_ch1}, P2={base_ch2}")
        best_p3 = base_ch2
        max_total = 0
        
        for offset in range(-20, 30, 10):
            test_p3 = base_ch2 + offset
            if test_p3 < 0:
                continue
                
            vesicle_counts = self._test_pressure_for_10_seconds(base_ch1, base_ch2, test_p3)
            total = sum(vesicle_counts)
            
            if total > max_total:
                max_total = total
                best_p3 = test_p3
                
        return best_p3, max_total

    def _liposome_create_process(self):
        try:
            self.troubleshooting_count = 0
            self.pressure_vesicle_data = []
            self.status_message = "Starting Generation..."
            
            self.pressure_ctrl.set_pressure(1500, 1500, 1500)
            time.sleep(60) 
            
            current_pressure_val = 800
            while current_pressure_val > 200:
                current_pressure_val -= 200
                print(f"Reducing to {current_pressure_val}")
                self.pressure_ctrl.set_pressure(current_pressure_val, current_pressure_val, current_pressure_val)
                time.sleep(2)
                
            # Start vesicle recognition
            self.mode = "GENERATION"
            self.recognition_sizes = []
            self.recognition_frame_count = 0
            self.recognition_mode_num = 0
            
            ch2_ch3_pressure = 200
            min_liposome = 0
            while ch2_ch3_pressure > 80:
                 ch2_ch3_pressure -= 10
                 self.status_message = f"Loop: P2/3={ch2_ch3_pressure}"
                 
                 vesicle_counts = self._test_pressure_for_10_seconds(200, ch2_ch3_pressure, ch2_ch3_pressure)
                 self._record_pressure_vesicle_data(200, ch2_ch3_pressure, ch2_ch3_pressure, vesicle_counts)
                 
                 min_liposome = min(vesicle_counts[-2:]) if len(vesicle_counts) >= 2 else 0
                 if min_liposome >= 5:
                     self.auto_troubleshooting_enabled = True
                     break
                     
            if min_liposome < 5:
                 best_data, message = self._find_best_pressure_combination()
                 if best_data:
                     print(f"Best pressure combination found: {message}")
                     print(f"P1={best_data['pressure_ch1']}, P2={best_data['pressure_ch2']}, P3={best_data['pressure_ch3']}")
                     if best_data['total_liposome'] > 0:
                         self.status_message = f"Optimizing Ch3 with P1={best_data['pressure_ch1']}, P2={best_data['pressure_ch2']}"
                         best_ch3, best_total = self._optimize_channel3_pressure(best_data['pressure_ch1'], best_data['pressure_ch2'])
                         print(f"Optimized channel 3 pressure: {best_ch3} with {best_total} total liposome")
                         self.pressure_ctrl.set_pressure(best_data['pressure_ch1'], best_data['pressure_ch2'], best_ch3)
                         self.auto_troubleshooting_enabled = True
                         msg = f"Optimized pressure set: P1={best_data['pressure_ch1']}, P2={best_data['pressure_ch2']}, P3={best_ch3}, total_liposome={best_total}. Auto troubleshooting enabled."
                         self.status_message = msg
                         self._send_ui_message(msg)
                         print(msg)
                     else:
                         msg = "No liposome generated with any pressure combination. Manual intervention required."
                         self.status_message = msg
                         self._send_ui_message(msg)
                         print(msg)
                 else:
                     msg = "No pressure data available. Manual intervention required."
                     self.status_message = msg
                     self._send_ui_message(msg)
                     print(msg)
            else:
                 msg = "Liposome generation process completed"
                 self.status_message = msg
                 self._send_ui_message(msg)
                 print(msg)
        except Exception as e:
            msg = f"Error during execution: {str(e)}"
            self.status_message = msg
            self._send_ui_message(msg)
            print(msg)

    def _restart_liposome_process(self):
        """API: Execute liposome generation process with pressure optimization (Recreate)"""
        try:
            self._send_ui_message("Warning: Restarting process due to low yield...")
            self.troubleshooting_count = 0
            self.pressure_vesicle_data = []
            self.status_message = "Restarting Generation..."
            if self.mode != "GENERATION":
                self.mode = "GENERATION"
            
            ch2_ch3_pressure = 200
            min_liposome = 0
            while ch2_ch3_pressure > 80:
                ch2_ch3_pressure -= 10
                
                self.status_message = f"Loop: P2/3={ch2_ch3_pressure}"
                vesicle_counts = self._test_pressure_for_10_seconds(200, ch2_ch3_pressure, ch2_ch3_pressure)
                self._record_pressure_vesicle_data(200, ch2_ch3_pressure, ch2_ch3_pressure, vesicle_counts)
                
                min_liposome = min(vesicle_counts[-2:]) if len(vesicle_counts) >= 2 else 0
                if min_liposome >= 5:
                    self.auto_troubleshooting_enabled = True
                    break
            
            if min_liposome < 5:
                 best_data, message = self._find_best_pressure_combination()
                 if best_data:
                     print(f"Best pressure combination found: {message}")
                     print(f"P1={best_data['pressure_ch1']}, P2={best_data['pressure_ch2']}, P3={best_data['pressure_ch3']}")
                     if best_data['total_liposome'] > 0:
                         self.status_message = f"Optimizing Ch3 with P1={best_data['pressure_ch1']}, P2={best_data['pressure_ch2']}"
                         best_ch3, best_total = self._optimize_channel3_pressure(best_data['pressure_ch1'], best_data['pressure_ch2'])
                         print(f"Optimized channel 3 pressure: {best_ch3} with {best_total} total liposome")
                         self.pressure_ctrl.set_pressure(best_data['pressure_ch1'], best_data['pressure_ch2'], best_ch3)
                         self.auto_troubleshooting_enabled = True
                         msg = f"Optimized pressure set: P1={best_data['pressure_ch1']}, P2={best_data['pressure_ch2']}, P3={best_ch3}, total_liposome={best_total}. Auto troubleshooting enabled."
                         self.status_message = msg
                         self._send_ui_message(msg)
                         print(msg)
                     else:
                         msg = "No liposome generated with any pressure combination. Manual intervention required."
                         self.status_message = msg
                         self._send_ui_message(msg)
                         print(msg)
                 else:
                     msg = "No pressure data available. Manual intervention required."
                     self.status_message = msg
                     self._send_ui_message(msg)
                     print(msg)
            else:
                 msg = "Liposome generation process completed"
                 self.status_message = msg
                 self._send_ui_message(msg)
                 print(msg)
        except Exception as e:
            msg = f"Error during execution: {str(e)}"
            self.status_message = msg
            self._send_ui_message(msg)
            print(msg)

    def start_generation(self):
        if self.mode == "IDLE":
            threading.Thread(target=self._liposome_create_process, daemon=True).start()
            return {"status": "started"}
        return {"status": "busy"}

    def stop_generation(self):
        self.mode = "IDLE"
        self.status_message = "Stopped"
        return {"status": "stopped"}
    
    def get_status(self):
         return {
            "mode": self.mode,
            "message": self.status_message,
            "current_counts": self.current_counts[-1] if self.current_counts else 0,
        }

    def _adjust_pressure_for_recognition(self):
        """Recognition mode pressure adjustment (aligned with old system)"""
        if not self.is_size_adjustment_active or self.target_liposome_size <= 0 or self.recognition_mode_num <= 0:
            return
            
        diff = self.target_liposome_size - self.recognition_mode_num
        current_p = self.pressure_ctrl.get_target_pressures()
        adjusted = False
        
        if diff < -0.2:
            current_p[0] += 2.0  # P1
            adjusted = True
        elif diff > 0.2:
            current_p[0] -= 2.0  # P1
            adjusted = True
        
        if adjusted:
            current_p[0] = max(min(current_p[0], 2000), 0)
            self.pressure_ctrl.set_pressure(current_p[0], current_p[1], current_p[2])
            print(f"Recognition pressure adjusted. New P1: {current_p[0]}")
            self._send_ui_message(f"adjusting!\nCurrent liposome size {self.recognition_mode_num}")
            
        if -0.2 <= diff <= 0.2:
            print("Recognition pressure adjustment complete, target reached.")
            self._send_ui_message("Success!\nLiposome size adjustment completed!")

    def size_adjustment(self, action, target_size=0):
        """API: Start or stop size adjustment mode"""
        if action == "start":
            try:
                target_size = float(target_size)
                if target_size <= 0:
                    return {"status": "error", "message": "Target size must be positive."}
                self.target_liposome_size = target_size
                self.is_size_adjustment_active = True
                return {"status": "success", "message": f"Size adjustment mode started with target size {target_size}"}
            except ValueError:
                return {"status": "error", "message": "Invalid target size format."}
        elif action == "stop":
            if not self.is_size_adjustment_active:
                return {"status": "warning", "message": "Size adjustment mode is not active."}
            self.is_size_adjustment_active = False
            self.target_liposome_size = 0
            return {"status": "success", "message": "Size adjustment mode stopped."}
        else:
            return {"status": "error", "message": f"Invalid action: {action}"}

    def create_api_app(self):
        import numpy as np
        app = super().create_api_app()

        @app.get("/distribution/data")
        def get_distribution():
            hist_data = []
            all_sizes = self.current_sizes
            if all_sizes:
                hist, bin_edges = np.histogram(all_sizes, bins=self.liposome_size_bins)
                for i in range(len(hist)):
                    hist_data.append({"size": f"{bin_edges[i]:.1f}", "count": int(hist[i])})
            return {
                "histogram": hist_data,
                "recognition_num": self.recognition_num,
                "recognition_mode_num": self.recognition_mode_num,
                "total_count": len(all_sizes)
            }

        @app.post("/control/start_generation")
        def api_start_gen():
            return self.start_generation()

        @app.post("/control/stop")
        def api_stop_gen():
            return self.stop_generation()

        @app.post("/control/pressure")
        def api_pressure(p1: float = None, p2: float = None, p3: float = None, p4: float = None):
            try:
                self.pressure_ctrl.set_pressure(p1, p2, p3, p4)
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        @app.post("/control/size_adjustment")
        def api_size_adjustment(action: str, target_size: float = 0):
            return self.size_adjustment(action, target_size)

        return app


if __name__ == "__main__":
    LiposomeGenTask().run_as_main()