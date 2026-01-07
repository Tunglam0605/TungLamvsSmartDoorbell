from picamera2 import Picamera2
from config import FRAME_WIDTH, FRAME_HEIGHT

class CameraManager:
    def __init__(self):
        self.picam = Picamera2()
        cfg = self.picam.create_preview_configuration(
            main={"format": "RGB888", "size": (FRAME_WIDTH, FRAME_HEIGHT)}
        )
        self.picam.configure(cfg)
        self.picam.start()

    def get_frame(self):
        return self.picam.capture_array()
