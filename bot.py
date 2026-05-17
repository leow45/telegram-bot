"""
Telegram Media Forwarder Bot
يسحب الصور والفيديوهات من قناة محمية وينشرها بقناتك
"""

import asyncio
import os
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

# تأخير بين كل رسالة بالثواني (لتجنب الحظر)
DELAY_SECONDS = 3
# ======================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

client = TelegramClient("session", API_ID, API_HASH)


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

        await client.send_file(
            TARGET_CHANNEL,
            file_path,
            caption=""
        )
        logger.info("✅ تم النشر بنجاح!")

        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        logger.error(f"❌ خطأ أثناء النشر: {e}")


async def scrape_old_messages():
    """سحب كل المحتوى القديم من القناة المصدر"""
    logger.info("📦 جاري سحب المحتوى القديم...")
    count = 0

    async for message in client.iter_messages(SOURCE_CHANNEL, reverse=True):
        if not is_media(message):
            continue

        logger.info(f"📤 نشر رسالة قديمة ID: {message.id}")
        await send_media(message)
        count += 1

        # تأخير لتجنب حظر تلغرام
        await asyncio.sleep(DELAY_SECONDS)

    logger.info(f"✅ انتهى سحب المحتوى القديم — تم نشر {count} ملف")


@client.on(events.NewMessage(chats=SOURCE_CHANNEL))
async def handler(event):
    """يراقب الرسائل الجديدة تلقائياً"""
    message = event.message

    if not is_media(message):
        return

    logger.info("🆕 ميديا جديدة وصلت!")
    await send_media(message)


async def main():
    logger.info("🚀 جاري تشغيل البوت...")

    await client.start(phone=PHONE, password=lambda: TWO_FA)
    logger.info("✅ تم تسجيل الدخول بنجاح!")

    # الانضمام للقناة المصدر
    try:
        await client(JoinChannelRequest(SOURCE_CHANNEL))
        logger.info(f"✅ تم الانضمام لـ {SOURCE_CHANNEL}")
    except Exception as e:
        logger.info(f"ℹ️ {e}")

    # سحب المحتوى القديم أولاً
    await scrape_old_messages()

    # بعدها يراقب الجديد
    logger.info(f"👂 يراقب {SOURCE_CHANNEL} → ينشر في {TARGET_CHANNEL}")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())