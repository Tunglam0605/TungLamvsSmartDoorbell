import io
import cv2
from telegram import Bot

class TelegramNotifier:
    def __init__(self, token, chat_id):
        if not token:
            raise RuntimeError("Telegram token not set")
        self.bot = Bot(token=token)
        self.chat_id = chat_id

    def send_photo(self, image_bgr, caption=""):
        success, buffer = cv2.imencode(".jpg", image_bgr,[int(cv2.IMWRITE_JPEG_QUALITY),85])
        if not success:
            print("Encode failed")
            return
        bio = io.BytesIO(buffer.tobytes())
        bio.name='visitor.jpg'
        bio.seek(0)
        try:
            self.bot.send_photo(chat_id=self.chat_id, photo=bio, caption=caption)
        except Exception as e:
            print("Telegram send failed:", e)
