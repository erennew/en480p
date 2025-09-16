import datetime
import logging
import os
import time
import asyncio
import json
from bot.localisation import Localisation
from bot import (
    DOWNLOAD_LOCATION, 
    AUTH_USERS,
    app
)
from bot.helper_funcs.ffmpeg import (
    convert_video,
    media_info,
    take_screen_shot
)
from bot.helper_funcs.display_progress import (
    progress_for_pyrogram,
    TimeFormatter
)
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
LOGGER = logging.getLogger(__name__)

CURRENT_PROCESSES = {}
CHAT_FLOOD = {}
bot = app

async def incoming_start_message_f(bot, update):
    """/start command"""
    await bot.send_message(
        chat_id=update.chat.id,
        text=Localisation.START_TEXT,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton('Owner', url='tg://settings/Hacked')]]
        ),
        reply_to_message_id=update.id,
    )

async def incoming_compress_message_f(update):
    """/compress command"""
    isAuto = True
    d_start = time.time()
    sent_message = await bot.send_message(
        chat_id=update.chat.id,
        text=Localisation.DOWNLOAD_START,
        reply_to_message_id=update.id
    )

    try:
        status = DOWNLOAD_LOCATION + "/status.json"
        with open(status, 'w') as f:
            statusMsg = {
                'running': True,
                'message': sent_message.id
            }
            json.dump(statusMsg, f, indent=2)

        video = await bot.download_media(
            message=update,
            progress=progress_for_pyrogram,
            progress_args=(
                bot,
                Localisation.DOWNLOAD_START,
                sent_message,
                d_start
            )
        )
        saved_file_path = video

        if not os.path.exists(saved_file_path):
            raise FileNotFoundError("Downloaded file not found.")

        downloaded_time = TimeFormatter((time.time() - d_start) * 1000)
        duration, bitrate = await media_info(saved_file_path)

        if duration is None or bitrate is None:
            raise ValueError("Failed to retrieve video metadata.")

        thumb_image_path = await take_screen_shot(
            saved_file_path,
            os.path.dirname(os.path.abspath(saved_file_path)),
            (duration / 2)
        )

        # Update the message instead of sending a new one
        await sent_message.edit_text(Localisation.COMPRESS_START)

        c_start = time.time()
        o = await convert_video(
            saved_file_path,
            DOWNLOAD_LOCATION,
            duration,
            bot,
            sent_message,
            sent_message  # Using the same message object
        )
        compressed_time = TimeFormatter((time.time() - c_start) * 1000)

        if o is None:
            raise ValueError("Compression failed.")

        u_start = time.time()

        # Use the file name as the caption
        file_name = os.path.basename(o)
        caption = f"<blockquote>{file_name}</blockquote>\n\n<blockquote>Downloaded: {downloaded_time}\nCompressed: {compressed_time}</blockquote>"

        await bot.send_document(
            chat_id=update.chat.id,
            document=o,
            caption=caption,
            thumb=thumb_image_path if os.path.exists(thumb_image_path) else None,
            reply_to_message_id=update.id,
            progress=progress_for_pyrogram,
            progress_args=(
                bot,
                Localisation.UPLOAD_START,
                sent_message,
                u_start
            )
        )

        uploaded_time = TimeFormatter((time.time() - u_start) * 1000)
        await sent_message.delete()

    except Exception as e:
        LOGGER.error(f"Error: {e}")
        await sent_message.edit_text(f"⚠️ {str(e)} ⚠️")
    finally:
        if os.path.exists(status):
            os.remove(status)

async def incoming_cancel_message_f(bot, update):
    """/cancel command"""
    if update.from_user.id not in AUTH_USERS:
        try:
            await update.message.delete()
        except:
            pass
        return

    status = DOWNLOAD_LOCATION + "/status.json"
    if os.path.exists(status):
        inline_keyboard = [
            [
                InlineKeyboardButton("Yes 🚫", callback_data="fuckingdo"),
                InlineKeyboardButton("No 🤗", callback_data="fuckoff")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard)
        await update.reply_text("Are you sure? 🚫 This will stop the compression!", reply_markup=reply_markup, quote=True)
    else:
        await bot.send_message(
            chat_id=update.chat.id,
            text="No active compression exists",
            reply_to_message_id=update.id
        )
