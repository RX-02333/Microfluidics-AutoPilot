
import threading
import subprocess
import numpy as np
import time
from typing import Optional
from .base import BaseCamera

try:
    from . import toupcam
except ImportError:
    toupcam = None


class ToupCamCamera(BaseCamera):
    """Implementation for ToupCam cameras"""
    
    def __init__(self, rtsp_url="rtsp://192.168.31.178:8554/test", width=1920, height=1200, ffmpeg_command=None):
        super().__init__(rtsp_url, width, height, ffmpeg_command)
        self.hcam = None
        self.buf = None
        self.total_frames = 0
        self.img_array = None
        
    def initialize(self) -> bool:
        if not toupcam:
            print("ToupCam module not imported")
            return False
            
        camera_devices = toupcam.Toupcam.EnumV2()
        if not camera_devices:
            print('No camera found')
            return False
            
        self.hcam = toupcam.Toupcam.Open(camera_devices[0].id)
        if not self.hcam:
            print('Failed to open camera')
            return False
            
        try:
            self.hcam.put_Option(toupcam.TOUPCAM_OPTION_RGB, 3) # Raw data
            self.hcam.put_ExpoTime(1000) # Auto exposure or default? Original code had 1000
            
            # Update width/height from actual camera capabilities
            self.width, self.height = self.hcam.get_Size()
            
            # Calculate buffer size
            bufsize = toupcam.TDIBWIDTHBYTES(self.width * 8) * self.height
            self.buf = bytes(bufsize)
            
            if not self.buf:
                print('Failed to allocate buffer for camera image')
                self.hcam.Close()
                self.hcam = None
                return False
                
            self.hcam.StartPullModeWithCallback(self._camera_callback_static, self)
            self._running = True
            
            # Init ffmpeg with correct dimensions
            self.ffmpeg_process = self._init_ffmpeg()
            return True
            
        except Exception as e:
            print(f"Error starting controller: {e}")
            self.close()
            return False

    @staticmethod
    def _camera_callback_static(nEvent, ctx):
        if nEvent == toupcam.TOUPCAM_EVENT_IMAGE:
            ctx._camera_callback_method(nEvent)

    def _camera_callback_method(self, nEvent):
        if nEvent == toupcam.TOUPCAM_EVENT_IMAGE:
            try:
                self.hcam.PullImageV4(self.buf, 0, 8, 0, None)
                self.total_frames += 1
                with self.lock:
                    self.img_array = np.frombuffer(self.buf, dtype=np.uint8).reshape((self.height, self.width))
            except toupcam.HRESULTException as ex:
                print(f'Pull image failed, hr=0x{ex.hr & 0xffffffff}')

    def get_latest_frame(self) -> Optional[np.ndarray]:
        with self.lock:
            if self.img_array is not None:
                return self.img_array.copy()
            return None

    def close(self):
        self._running = False
        if self.hcam:
            self.hcam.Close()
            self.hcam = None
            
        if self.ffmpeg_process:
            self.ffmpeg_process.terminate()
            self.ffmpeg_process = None

class CameraFactory:
    @staticmethod
    def create_camera(type_name: str, **kwargs) -> BaseCamera:
        if type_name.lower() == 'toupcam':
            return ToupCamCamera(**kwargs)
        raise ValueError(f"Unknown camera type: {type_name}")

if __name__ == "__main__":
    # Example usage
    controller = CameraFactory.create_camera('toupcam')
    if controller.initialize():
        print("Camera initialized successfully.")
        try:
            while True:
                frame = controller.get_latest_frame()
                if frame is not None:
                    controller.stream_to_ffmpeg(frame)
                time.sleep(0.01)
        except KeyboardInterrupt:
            print("Stopping...")
        finally:
            controller.close()
    else:
        print("Failed to initialize camera.")
