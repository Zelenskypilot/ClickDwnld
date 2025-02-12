import os
import yt_dlp
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, InlineQueryHandler
from dotenv import load_dotenv
import asyncio
import requests

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Bot name
BOT_NAME = "ClickYoutube"

# Logging setup
logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message."""
    user_name = update.message.from_user.first_name
    welcome_message = (
        f"👋 Welcome, {user_name}! I'm {BOT_NAME}, your YouTube video downloader bot.\n\n"
        "📽️ Send me a YouTube link, and I'll download the video for you.\n"
        "🎵 You can also download audio-only (MP3).\n"
        "📺 Now supporting Instagram, TikTok, Facebook, and Twitter videos too!\n\n"
        "🛠️ Use /help to see all available commands."
    )
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message."""
    help_message = (
        f"🤖 {BOT_NAME} Help\n\n"
        "📌 Available Commands:\n"
        "/start - Start the bot and get a welcome message.\n"
        "/help - Show this help message.\n"
        "/audio <link> - Download audio-only (MP3).\n"
        "/quality <link> - Select video quality before downloading.\n\n"
        "📥 How to Use:\n"
        "1. Send a YouTube, Instagram, TikTok, Facebook, or Twitter video link.\n"
        "2. Select quality or audio option.\n"
        "3. I'll download the video and send it to you."
    )
    await update.message.reply_text(help_message)

def get_video_formats(url):
    """Fetch available video formats."""
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get('formats', [])
        video_formats = [
            (f"{fmt['format_note']} ({fmt['ext']})", fmt['format_id'])
            for fmt in formats if fmt.get('vcodec') != 'none'  # Filter only video formats
        ]
        thumbnail_url = info.get('thumbnail', None)
        title = info.get('title', 'Unknown Title')
    return video_formats, thumbnail_url, title

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE, url, format_id):
    """Download the selected video format."""
    download_directory = 'downloads'
    if not os.path.exists(download_directory):
        os.makedirs(download_directory)

    ydl_opts = {
        'outtmpl': f'{download_directory}/%(title)s.%(ext)s',
        'format': format_id,
    }

    try:
        progress_message = await update.message.reply_text('⏳ Downloading video... Please wait.')

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info.get('title', 'video')
            video_file = ydl.prepare_filename(info)

        await context.bot.edit_message_text(chat_id=update.message.chat_id, message_id=progress_message.message_id, text='✅ Download complete!')

        keyboard = [[InlineKeyboardButton("📥 Download Video", callback_data=video_file)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_video(video=open(video_file, 'rb'), caption=f"🎥 {video_title}", reply_markup=reply_markup)
    except Exception as e:
        await update.message.reply_text(f'❌ Error: {e}')

async def quality_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send available video quality options."""
    url = context.args[0] if context.args else None
    if not url:
        await update.message.reply_text("❌ Please provide a video link. Example: `/quality <link>`")
        return

    formats, thumbnail_url, title = get_video_formats(url)

    keyboard = [[InlineKeyboardButton(f"{quality} 📺", callback_data=f"{url}|{format_id}")] for quality, format_id in formats]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if thumbnail_url:
        await update.message.reply_photo(photo=thumbnail_url, caption=f"🎥 **{title}**\nSelect a quality to download:", reply_markup=reply_markup)
    else:
        await update.message.reply_text(f"🎥 **{title}**\nSelect a quality to download:", reply_markup=reply_markup)

async def audio_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Download audio-only (MP3)."""
    url = context.args[0] if context.args else None
    if not url:
        await update.message.reply_text("❌ Please provide a video link. Example: `/audio <link>`")
        return

    download_directory = 'downloads'
    if not os.path.exists(download_directory):
        os.makedirs(download_directory)

    ydl_opts = {
        'format': 'bestaudio',
        'outtmpl': f'{download_directory}/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    try:
        progress_message = await update.message.reply_text('🎵 Downloading audio... Please wait.')

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            audio_title = info.get('title', 'audio')
            audio_file = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')

        await context.bot.edit_message_text(chat_id=update.message.chat_id, message_id=progress_message.message_id, text='✅ Audio download complete!')

        await update.message.reply_audio(audio=open(audio_file, 'rb'), caption=f"🎶 {audio_title}")
    except Exception as e:
        await update.message.reply_text(f'❌ Error: {e}')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button clicks for quality selection."""
    query = update.callback_query
    url, format_id = query.data.split("|")

    await query.answer()
    await download_video(update, context, url, format_id)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle direct video links from users."""
    url = update.message.text
    formats, thumbnail_url, title = get_video_formats(url)

    keyboard = [[InlineKeyboardButton(f"{quality} 📺", callback_data=f"{url}|{format_id}")] for quality, format_id in formats]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if thumbnail_url:
        await update.message.reply_photo(photo=thumbnail_url, caption=f"🎥 **{title}**\nSelect a quality to download:", reply_markup=reply_markup)
    else:
        await update.message.reply_text(f"🎥 **{title}**\nSelect a quality to download:", reply_markup=reply_markup)

def main():
    """Start the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('quality', quality_selection))
    application.add_handler(CommandHandler('audio', audio_download))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))

    application.run_polling()

if __name__ == '__main__':
    main()