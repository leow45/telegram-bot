"""
Telegram Media Forwarder Bot
يسحب الصور والفيديوهات من قناة محمية وينشرها بقناتك
الميزات: تجنب التكرار + وضع الصمت (إيقاف/تشغيل)
"""

import asyncio
import os
import json
import logging
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from telethon.tl.functions.channels import JoinChannelRequest

load_dotenv()

# ===================== الإعدادات =====================
API_ID       = int(os.environ.get("API_ID", "0"))
API_HASH     = os.environ.get("API_HASH", "")
PHONE        = os.environ.get("PHONE", "")
TWO_FA       = os.environ.get("TWO_FA_PASSWORD", "")

SOURCE_CHANNEL = os.environ.get("SOURCE_CHANNEL", "")
TARGET_CHANNEL = os.environ.get("TARGET_CHANNEL", "")

# رقم حسابك الشخصي على تلغرام (لاستقبال أوامر الإيقاف/التشغيل)
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "")

# ملف حفظ الرسائل المنشورة
POSTED_FILE = "posted_ids.json"
# ======================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

client = TelegramClient("session", API_ID, API_HASH)

# حالة البوت — True = يعمل، False = متوقف مؤقتاً
is_active = True


# =================== تجنب التكرار ===================

def load_posted_ids():
    """تحميل IDs الرسائل المنشورة مسبقاً"""
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_posted_id(msg_id):
    """حفظ ID رسالة تم نشرها"""
    posted_ids.add(msg_id)
    with open(POSTED_FILE, "w") as f:
        json.dump(list(posted_ids), f)

posted_ids = load_posted_ids()
# =====================================================


def is_media(message):
    """تحقق إذا كانت الرسالة صورة أو فيديو فقط"""
    if not message.media:
        return False
    if isinstance(message.media, MessageMediaPhoto):
        return True
    if isinstance(message.media, MessageMediaDocument):
        mime = getattr(message.media.document, "mime_type", "") or ""
        if mime.startswith("video/") or mime.startswith("image/"):
            return True
    return False


async def send_media(message):
    """تنزيل الميديا ونشرها بالقناة الهدف"""
    try:
        file_path = await client.download_media(message.media)
        logger.info(f"⬇️ تم التنزيل: {file_path}")

        is_video = isinstance(file_path, str) and any(
            file_path.lower().endswith(ext)
            for ext in [".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"]
        )
        await client.send_file(
            TARGET_CHANNEL,
            file_path,
            caption="",
            supports_streaming=is_video,
            force_document=False
        )
        logger.info("✅ تم النشر بنجاح!")

        # حفظ ID الرسالة لتجنب التكرار
        posted_ids.add(message.id)
        save_posted_id(message.id)

        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        logger.error(f"❌ خطأ أثناء النشر: {e}")


# =================== مراقبة القناة ===================

@client.on(events.NewMessage(chats=SOURCE_CHANNEL))
async def handler(event):
    """يراقب الرسائل الجديدة تلقائياً"""
    global is_active
    message = event.message

    # تجاهل لو البوت متوقف
    if not is_active:
        logger.info("⏸️ البوت متوقف مؤقتاً، تم تجاهل الرسالة")
        return

    # تجنب التكرار
    if message.id in posted_ids:
        logger.info(f"⚠️ رسالة {message.id} منشورة مسبقاً، تم تجاهلها")
        return

    if not is_media(message):
        return

    logger.info("🆕 ميديا جديدة وصلت!")
    await send_media(message)


# =================== وضع الصمت ===================

@client.on(events.NewMessage(chats=ADMIN_USERNAME if ADMIN_USERNAME else "me", pattern=r"(?i)^(stop|pause|وقف)$"))
async def pause_bot(event):
    """إيقاف البوت مؤقتاً بأمر منك"""
    global is_active
    is_active = False
    await event.respond("⏸️ تم إيقاف البوت مؤقتاً. أرسل 'start' أو 'شغل' لتشغيله.")
    logger.info("⏸️ البوت متوقف بأمر المدير")

@client.on(events.NewMessage(chats=ADMIN_USERNAME if ADMIN_USERNAME else "me", pattern=r"(?i)^(start|resume|شغل)$"))
async def resume_bot(event):
    """تشغيل البوت مجدداً بأمر منك"""
    global is_active
    is_active = True
    await event.respond("▶️ تم تشغيل البوت! يراقب القناة الآن.")
    logger.info("▶️ البوت يعمل بأمر المدير")

@client.on(events.NewMessage(chats=ADMIN_USERNAME if ADMIN_USERNAME else "me", pattern=r"(?i)^(status|حالة)$"))
async def bot_status(event):
    """اعرف حالة البوت"""
    state = "▶️ يعمل" if is_active else "⏸️ متوقف مؤقتاً"
    count = len(posted_ids)
    await event.respond(f"حالة البوت: {state}\nعدد الرسائل المنشورة: {count}")
# =====================================================


async def main():
    logger.info("🚀 جاري تشغيل البوت...")

    await client.start(phone=PHONE, password=lambda: TWO_FA if TWO_FA else None)
    logger.info("✅ تم تسجيل الدخول بنجاح!")

    # الانضمام للقناة المصدر
    try:
        await client(JoinChannelRequest(SOURCE_CHANNEL))
        logger.info(f"✅ تم الانضمام لـ {SOURCE_CHANNEL}")
    except Exception as e:
        logger.info(f"ℹ️ {e}")

    logger.info(f"👂 يراقب {SOURCE_CHANNEL} → ينشر في {TARGET_CHANNEL}")
    logger.info(f"💬 أرسل 'stop' لإيقاف البوت أو 'start' لتشغيله أو 'status' لمعرفة حالته")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
