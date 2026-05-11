
import abc
import subprocess
import threading
import numpy as np
from typing import Optional

class BaseCamera(abc.ABC):
    """Abstract base class for camera implementations"""
    
    def __init__(self, rtsp_url: str = "rtsp://127.0.0.1:8554/test", width: int = 1920, height: int = 1200, ffmpeg_command: Optional[list] = None):
        self.rtsp_url = rtsp_url
        self.width = width
        self.height = height
        self.ffmpeg_command = ffmpeg_command
        self.ffmpeg_process = None
        self._running = False
        self.lock = threading.Lock()
        
    @abc.abstractmethod
    def initialize(self) -> bool:
        """Initialize the camera"""
        pass
        
    @abc.abstractmethod
    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Return the latest frame as numpy array"""
        pass
        
    @abc.abstractmethod
    def close(self):
        """Release resources"""
        pass

    def _init_ffmpeg(self):
        """Initialize FFmpeg process for RTSP streaming"""
        if not self.rtsp_url:
            return None
            
        if self.ffmpeg_command:
            command = self.ffmpeg_command
        else:
            command = [
                'ffmpeg', '-y', '-f', 'rawvideo', '-hwaccel', 'amf',
                '-vcodec', 'rawvideo', '-pix_fmt', 'gray', # Note: ToupCam impl used gray/raw8, ensure matches
                '-s', f'{self.width}x{self.height}', '-r', '60',
                '-i', '-', '-c:v', 'hevc_amf', '-bf', '0', '-b:v', '5000k', 
                '-f', 'rtsp', self.rtsp_url
            ]
        try:
            process = subprocess.Popen(command, stdin=subprocess.PIPE)
            print(f"FFmpeg process started for RTSP streaming to {self.rtsp_url}")
            return process
        except Exception as e:
            print(f"Failed to start FFmpeg process: {e}")
            return None

    def stream_to_ffmpeg(self, frame: np.ndarray):
        """Stream frame to FFmpeg"""
        if not self.ffmpeg_process:
            self.ffmpeg_process = self._init_ffmpeg()
            
        if self.ffmpeg_process and self.ffmpeg_process.stdin and not self.ffmpeg_process.stdin.closed:
            try:
                self.ffmpeg_process.stdin.write(frame.tobytes())
            except IOError as e:
                print(f"Error writing to FFmpeg stdin: {e}")
                self.ffmpeg_process.stdin.close()
                self.ffmpeg_process.wait()
                self.ffmpeg_process = None
