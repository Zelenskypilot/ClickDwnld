import os
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv
import asyncio

# Load environment variables from .env file
load_dotenv()

# Get the bot token from the environment variable
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Bot name
BOT_NAME = "ClickYoutube"

# Supported platforms
SUPPORTED_PLATFORMS = ["youtube", "instagram", "tiktok", "facebook", "twitter"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.from_user.first_name
    welcome_message = (
        f"👋 Welcome, {user_name}! I'm {BOT_NAME}, your multi-platform video downloader bot.\n\n"
        "📽️ Send me a link from YouTube, Instagram, TikTok, Facebook, or Twitter, and I'll download the content for you.\n"
        "🛠️ Use /help to see all available commands."
    )
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_message = (
        f"🤖 {BOT_NAME} Help\n\n"
        "📌 Available Commands:\n"
        "/start - Start the bot and get a welcome message.\n"
        "/help - Show this help message.\n\n"
        "📥 How to Use:\n"
        "1. Send a link from YouTube, Instagram, TikTok, Facebook, or Twitter.\n"
        "2. I'll download the content and send it to you.\n"
        "3. Use the inline buttons to select video quality or download audio-only.\n"
        "4. Use inline search with `@ClickYoutubeBot <search query>` to find YouTube videos."
    )
    await update.message.reply_text(help_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    download_directory = 'downloads'

    if not os.path.exists(download_directory):
        os.makedirs(download_directory)

    # Check if the platform is supported
    platform = None
    for p in SUPPORTED_PLATFORMS:
        if p in url:
            platform = p
            break

    if not platform:
        await update.message.reply_text("❌ Unsupported platform. Please provide a valid link from YouTube, Instagram, TikTok, Facebook, or Twitter.")
        return

    # Send a progress message
    progress_message = await update.message.reply_text('⏳ Fetching video info... Please wait.')

    try:
        ydl_opts = {
            'outtmpl': f'{download_directory}/%(title)s.%(ext)s',
            'format': 'best',
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'video')
            thumbnail = info.get('thumbnail', None)
            formats = info.get('formats', [])

        # Send thumbnail preview
        if thumbnail:
            await context.bot.send_photo(chat_id=update.message.chat_id, photo=thumbnail, caption=f"🎥 {video_title}")

        # Create quality selection buttons
        quality_buttons = []
        for f in formats:
            if f.get('height'):
                quality_buttons.append(InlineKeyboardButton(f"{f['height']}p", callback_data=f"quality_{f['format_id']}_{url}"))

        audio_button = [InlineKeyboardButton("🎵 Download Audio (MP3)", callback_data=f"audio_{url}")]
        keyboard = [quality_buttons[i:i + 3] for i in range(0, len(quality_buttons), 3)] + [audio_button]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.edit_message_text(chat_id=update.message.chat_id, message_id=progress_message.message_id, text='✅ Select a quality or download audio:')
        await update.message.reply_text("Choose an option:", reply_markup=reply_markup)
    except Exception as e:
        await update.message.reply_text(f'❌ Error: {e}')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat_id = query.message.chat_id
    message_id = query.message.message_id

    await query.answer()

    if data.startswith("quality_"):
        format_id, url = data.split("_")[1], "_".join(data.split("_")[2:])
        await download_video(query, url, format_id)
    elif data.startswith("audio_"):
        url = "_".join(data.split("_")[1:])
        await download_audio(query, url)

async def download_video(query, url, format_id):
    download_directory = 'downloads'
    ydl_opts = {
        'outtmpl': f'{download_directory}/%(title)s.%(ext)s',
        'format': format_id,
        'progress_hooks': [lambda d: progress_hook(d, query)],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_file = ydl.prepare_filename(info)

    await query.edit_message_text(text='✅ Download complete!')
    await query.message.reply_video(video=open(video_file, 'rb'), caption=f"🎥 {info.get('title', 'video')}")

async def download_audio(query, url):
    download_directory = 'downloads'
    ydl_opts = {
        'outtmpl': f'{download_directory}/%(title)s.%(ext)s',
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'progress_hooks': [lambda d: progress_hook(d, query)],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        audio_file = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.mp4', '.mp3')

    await query.edit_message_text(text='✅ Audio download complete!')
    await query.message.reply_audio(audio=open(audio_file, 'rb'), caption=f"🎵 {info.get('title', 'audio')}")

def progress_hook(d, query):
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '0%')
        speed = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        asyncio.run(query.edit_message_text(text=f"⏳ Downloading... {percent} done | Speed: {speed} | ETA: {eta}"))

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))

    application.run_polling()

if __name__ == '__main__':
    main()