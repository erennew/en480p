#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (c) gautamajay52 | Shrimadhav U K | @AbirHasan2005

import logging
import asyncio
import os
import time
import subprocess
from datetime import datetime
from pyrogram import Client

from tobrot import DOWNLOAD_LOCATION
from tobrot.helper_funcs.display_progress_g import progress_for_pyrogram_g
from tobrot.helper_funcs.upload_to_tg import upload_to_gdrive
from tobrot.helper_funcs.create_compressed_archive import unzip_me, unrar_me, untar_me

# Import the unified progress functions
from display_progress import progress_for_pyrogram, progress_for_torrent

# Import LibTorrent downloader
try:
    import libtorrent as lt
    from typing import Tuple, List, Dict, Optional
    
    class LibTorrentDownloader:
        """Enhanced LibTorrent downloader with progress tracking"""
        
        def __init__(self, magnet_link: str, download_dir: str):
            self.magnet_link = magnet_link
            self.download_dir = download_dir
            self.session = lt.session()
            self.handle = None
            self.status = None
            self._stop_event = asyncio.Event()
            
            # Configure session settings
            settings = {
                'listen_interfaces': '0.0.0.0:6881',
                'enable_dht': True,
                'enable_upnp': True,
                'enable_natpmp': True,
                'connections_limit': 200,
                'active_downloads': 3,
                'download_rate_limit': 0,
                'upload_rate_limit': 0,
            }
            self.session.apply_settings(settings)

        async def start_download(self, progress_callback=None):
            """Start download with progress tracking"""
            try:
                # Parse magnet link
                atp = lt.parse_magnet_uri(self.magnet_link)
                atp.save_path = self.download_dir
                atp.storage_mode = lt.storage_mode_t.storage_mode_sparse
                
                self.handle = self.session.add_torrent(atp)
                self.status = self.handle.status()
                
                # Wait for metadata
                logger.info("Waiting for metadata...")
                metadata_timeout = 300
                start_time = time.time()
                
                while not self.handle.status().has_metadata:
                    if self._stop_event.is_set():
                        self.session.remove_torrent(self.handle)
                        raise asyncio.CancelledError("Download stopped by user")
                    if time.time() - start_time > metadata_timeout:
                        raise TimeoutError("Metadata timeout - no peers found")
                    await asyncio.sleep(1)
                    
                # Start downloading
                self.handle.resume()
                logger.info("Download started...")
                
                # Wait for completion
                while not self.handle.status().is_seeding:
                    if self._stop_event.is_set():
                        self.session.remove_torrent(self.handle)
                        raise asyncio.CancelledError("Download stopped by user")
                        
                    self.status = self.handle.status()
                    
                    # Call progress callback if provided
                    if progress_callback and self.status.total_wanted > 0:
                        progress = self.status.progress * 100
                        await progress_callback(progress, self.status)
                    
                    if self.status.state == lt.torrent_status.seeding:
                        break
                        
                    await asyncio.sleep(2)
                    
                logger.info("Download completed successfully")
                return self.download_dir
                
            except Exception as e:
                if self.handle:
                    self.session.remove_torrent(self.handle)
                logger.error(f"Download failed: {str(e)}")
                raise e

        def stop_download(self):
            """Stop the download"""
            self._stop_event.set()
            if self.handle:
                self.session.remove_torrent(self.handle)
                
        def get_status(self):
            """Get current status"""
            return self.status

except ImportError:
    logger.warning("libtorrent not available, magnet downloads disabled")
    LibTorrentDownloader = None


async def download_media_f(client, message):
    """
    Unified download function for both media files and magnet links
    """
    user_id = message.from_user.id
    mess_age = await message.reply_text("🔄 Processing...", quote=True)
    
    if not os.path.isdir(DOWNLOAD_LOCATION):
        os.makedirs(DOWNLOAD_LOCATION)

    start_time = time.time()
    
    # Check if it's a magnet link command
    if message.command and message.command[0] == "magnet" and len(message.command) > 1:
        await handle_magnet_download(client, message, mess_age, user_id, start_time)
    # Check if it's a reply to media
    elif message.reply_to_message is not None:
        await handle_media_download(client, message, mess_age, user_id, start_time)
    else:
        await mess_age.edit_text("❌ Please reply to a media file or use /magnet with a magnet link.")


async def handle_media_download(client, message, mess_age, user_id, start_time):
    """Handle media file downloads"""
    try:
        download_location = DOWNLOAD_LOCATION + "/"
        c_time = time.time()
        
        the_real_download_location = await client.download_media(
            message=message.reply_to_message,
            file_name=download_location,
            progress=progress_for_pyrogram_g,
            progress_args=(
                "📥 Downloading from Telegram", 
                mess_age, 
                c_time
            )
        )
        
        end_t = datetime.now()
        ms = (end_t - datetime.fromtimestamp(start_time)).seconds
        
        await mess_age.edit_text(f"✅ Downloaded to `{the_real_download_location}` in {ms} seconds")
        
        # Move file and process
        await process_downloaded_file(client, message, mess_age, user_id, the_real_download_location)
        
    except Exception as e:
        await mess_age.edit_text(f"❌ Download failed: {str(e)}")
        logger.error(f"Media download error: {e}")


async def handle_magnet_download(client, message, mess_age, user_id, start_time):
    """Handle magnet link downloads"""
    if LibTorrentDownloader is None:
        await mess_age.edit_text("❌ LibTorrent not available. Magnet downloads disabled.")
        return

    magnet_link = message.command[1]
    
    if not magnet_link.startswith('magnet:?'):
        await mess_age.edit_text("❌ Invalid magnet link format.")
        return

    try:
        # Create download directory
        download_dir = os.path.join(DOWNLOAD_LOCATION, f"torrent_{user_id}_{int(time.time())}")
        os.makedirs(download_dir, exist_ok=True)

        # Create downloader instance
        downloader = LibTorrentDownloader(magnet_link, download_dir)
        
        # Progress callback for torrent
        async def torrent_progress_callback(progress, status):
            total_size = status.total_wanted
            await progress_for_torrent(
                progress=progress,
                status=status,
                bot=client,
                ud_type="🧲 Downloading Torrent",
                message=mess_age,
                start_time=start_time,
                total_size=total_size
            )

        await mess_age.edit_text("🔍 Fetching metadata... This may take a few minutes.")
        
        # Start download
        download_path = await downloader.start_download(torrent_progress_callback)
        
        # Download completed
        await mess_age.edit_text("✅ Torrent download completed! Processing files...")
        
        # Process downloaded files
        await process_torrent_files(client, message, mess_age, user_id, download_path)
        
    except asyncio.CancelledError:
        await mess_age.edit_text("❌ Download cancelled by user.")
    except TimeoutError as e:
        await mess_age.edit_text(f"❌ Download timeout: {str(e)}")
    except Exception as e:
        await mess_age.edit_text(f"❌ Download failed: {str(e)}")
        logger.error(f"Magnet download error: {e}")
    finally:
        if 'downloader' in locals():
            downloader.stop_download()


async def process_downloaded_file(client, message, mess_age, user_id, file_path):
    """Process downloaded media files"""
    try:
        # Move file to app directory
        gk = subprocess.Popen(['mv', f'{file_path}', '/app/'], stdout=subprocess.PIPE)
        out = gk.communicate()
        file_name = os.path.basename(file_path)
        
        # Handle extraction commands
        if len(message.command) > 1:
            if message.command[1] == "unzip":
                extracted_path = await unzip_me(file_name)
                if extracted_path:
                    await upload_to_gdrive(extracted_path, mess_age, message, user_id)
            elif message.command[1] == "unrar":
                extracted_path = await unrar_me(file_name)
                if extracted_path:
                    await upload_to_gdrive(extracted_path, mess_age, message, user_id)
            elif message.command[1] == "untar":
                extracted_path = await untar_me(file_name)
                if extracted_path:
                    await upload_to_gdrive(extracted_path, mess_age, message, user_id)
        else:
            # Direct upload
            await upload_to_gdrive(file_name, mess_age, message, user_id)
            
    except Exception as e:
        await mess_age.edit_text(f"❌ File processing failed: {str(e)}")
        logger.error(f"File processing error: {e}")


async def process_torrent_files(client, message, mess_age, user_id, download_path):
    """Process downloaded torrent files"""
    try:
        # List all downloaded files
        all_files = []
        for root, _, files in os.walk(download_path):
            for file in files:
                if not file.startswith('.'):
                    file_path = os.path.join(root, file)
                    try:
                        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                            all_files.append({
                                'name': file,
                                'size': os.path.getsize(file_path),
                                'path': file_path,
                                'is_video': file.lower().endswith(('.mkv', '.mp4', '.avi', '.mov', '.flv', '.wmv', '.webm'))
                            })
                    except Exception as e:
                        logger.warning(f"Skipping file {file}: {str(e)}")
                        continue

        if not all_files:
            raise ValueError("No valid files found in download")

        # List files to user
        file_list_text = "<blockquote>📂 Downloaded Files:\n\n"
        for file_info in all_files[:10]:
            file_size_mb = file_info['size'] / (1024 * 1024)
            file_list_text += f"• {file_info['name']} ({file_size_mb:.1f} MB)\n"
        
        if len(all_files) > 10:
            file_list_text += f"\n... and {len(all_files) - 10} more files"
        
        file_list_text += "</blockquote>"
        
        await message.reply_text(file_list_text)
        
        # Upload first video file automatically
        video_files = [f for f in all_files if f['is_video']]
        if video_files:
            await mess_age.edit_text("🔼 Uploading first video file to Google Drive...")
            first_video = video_files[0]
            await upload_to_gdrive(first_video['path'], mess_age, message, user_id)
        else:
            await mess_age.edit_text("✅ Download completed! No video files found for automatic upload.")
            
    except Exception as e:
        await mess_age.edit_text(f"❌ File processing failed: {str(e)}")
        logger.error(f"Torrent file processing error: {e}")


# Backward compatibility
down_load_media_f = download_media_f
