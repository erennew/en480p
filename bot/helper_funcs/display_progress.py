#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (c) Shrimadhav U K | @AbirHasan2005

# the logging things
import logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

import math
import os
import time
import json
from typing import Optional, Union

from bot import (
    FINISHED_PROGRESS_STR,
    UN_FINISHED_PROGRESS_STR,
    DOWNLOAD_LOCATION
)


async def progress_for_pyrogram(
    current,
    total,
    bot,
    ud_type,
    message,
    start,
    download_type: str = "normal"  # "normal" or "torrent"
):
    """
    Unified progress function for both normal downloads and torrent downloads
    """
    now = time.time()
    diff = now - start
    
    if round(diff % 5.00) == 0 or current == total:  # Update every 5 seconds
        # Check if download should be stopped
        status = DOWNLOAD_LOCATION + "/status.json"
        if os.path.exists(status):
            with open(status, 'r+') as f:
                statusMsg = json.load(f)
                if not statusMsg["running"]:
                    bot.stop_transmission()
        
        percentage = current * 100 / total
        speed = current / diff if diff > 0 else 0
        elapsed_time = round(diff) * 1000
        time_to_completion = round((total - current) / speed) * 1000 if speed > 0 else 0
        estimated_total_time = elapsed_time + time_to_completion

        elapsed_time_str = TimeFormatter(milliseconds=elapsed_time)
        estimated_total_time_str = TimeFormatter(milliseconds=estimated_total_time)

        # Create progress bar
        progress_bar = "".join([
            FINISHED_PROGRESS_STR for i in range(math.floor(percentage / 10))
        ]) + "".join([
            UN_FINISHED_PROGRESS_STR for i in range(10 - math.floor(percentage / 10))
        ])

        progress_text = (
            f"<blockquote>"
            f"<code>[{progress_bar}]</code>\n"
            f"<b>📊 Progress:</b> {round(percentage, 2)}%\n"
            f"<b>📁 Size:</b> {humanbytes(current)} of {humanbytes(total)}\n"
            f"<b>⚡ Speed:</b> {humanbytes(speed)}/s\n"
            f"<b>⏰ ETA:</b> {estimated_total_time_str if estimated_total_time_str else '0s'}\n"
            f"<b>🕐 Elapsed:</b> {elapsed_time_str if elapsed_time_str else '0s'}</blockquote>"
        )

        if download_type == "torrent":
            # Add torrent-specific info if available
            if hasattr(bot, 'torrent_status'):
                torrent_status = bot.torrent_status
                progress_text += (
                    f"<blockquote>"
                    f"<b>👥 Peers:</b> {torrent_status.get('peers', 0)}\n"
                    f"<b>🔄 State:</b> {torrent_status.get('state', 'Downloading')}</blockquote>"
                )

        try:
            if not message.photo:
                await message.edit_text(
                    text=f"{ud_type}\n{progress_text}"
                )
            else:
                await message.edit_caption(
                    caption=f"{ud_type}\n{progress_text}"
                )
        except Exception as e:
            logger.warning(f"Failed to update progress: {e}")


async def progress_for_torrent(
    progress: float,
    status,
    bot,
    ud_type: str,
    message,
    start_time: float,
    total_size: float
):
    """
    Progress function specifically for torrent downloads
    """
    now = time.time()
    diff = now - start_time
    
    if round(diff % 5.00) == 0 or progress >= 100:  # Update every 5 seconds
        # Store torrent status for unified progress function
        bot.torrent_status = {
            'peers': status.num_peers,
            'state': str(status.state).split('.')[-1],
            'download_rate': status.download_rate
        }
        
        current = (progress / 100) * total_size
        speed = status.download_rate / 1024  # KB/s
        
        await progress_for_pyrogram(
            current=current,
            total=total_size,
            bot=bot,
            ud_type=ud_type,
            message=message,
            start=start_time,
            download_type="torrent"
        )


def humanbytes(size: float) -> str:
    """
    Convert bytes to human readable format
    """
    if not size:
        return "0 B"
    
    power = 2**10
    n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    
    while size >= power and n < len(power_labels) - 1:
        size /= power
        n += 1
    
    return f"{size:.2f} {power_labels[n]}"


def TimeFormatter(milliseconds: int) -> str:
    """
    Convert milliseconds to human readable time format
    """
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    
    time_parts = []
    if days > 0:
        time_parts.append(f"{days}d")
    if hours > 0:
        time_parts.append(f"{hours}h")
    if minutes > 0:
        time_parts.append(f"{minutes}m")
    if seconds > 0:
        time_parts.append(f"{seconds}s")
    
    return " ".join(time_parts) if time_parts else "0s"
