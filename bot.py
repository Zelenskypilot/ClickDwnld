import os
import yt_dlp
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

BOT_NAME = "ClickYoutube"
DOWNLOAD_DIR = 'downloads'

# Ensure the download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Inline search command (allows users to search for videos within Telegram)
async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query:
        return

    search_url = f"ytsearch5:{query}"
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        results = ydl.extract_info(search_url, download=False)

    videos = results.get('entries', [])
    articles = []
    
    for video in videos:
        video_id = video['id']
        title = video['title']
        thumbnail = video['thumbnail']
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        articles.append({
            "type": "article",
            "id": video_id,
            "title": title,
            "description": "Click to download this video",
            "thumb_url": thumbnail,
            "input_message_content": {
                "message_text": f"🎥 *{title}*\n🔗 [Watch Here]({url})\n\nClick the button below to download.",
                "parse_mode": "Markdown"
            },
            "reply_markup": InlineKeyboardMarkup([[InlineKeyboardButton("📥 Download", callback_data=f"download:{url}")]])
        })

    await update.inline_query.answer(articles)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.from_user.first_name
    await update.message.reply_text(
        f"👋 Welcome, {user_name}! I'm {BOT_NAME}, your YouTube video downloader bot.\n\n"
        "📽️ Send a YouTube link to get started.\n"
        "🔍 Use inline search: `@ClickYoutubeBot <query>` to find videos.\n"
        "🛠️ Use /help to see all available commands."
    )

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🤖 {BOT_NAME} Help\n\n"
        "📌 Available Commands:\n"
        "/start - Start the bot.\n"
        "/help - Show help message.\n\n"
        "📥 How to Use:\n"
        "1. Send a YouTube or other supported platform link.\n"
        "2. Choose the video quality or download MP3.\n"
        "3. Download the video or audio file.\n\n"
        "📍 Supported Platforms: YouTube, Instagram, TikTok, Facebook, Twitter."
    )

# Handle received links
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    buttons = [
        [InlineKeyboardButton("🔽 144p", callback_data=f"quality:{url}:144p"),
         InlineKeyboardButton("🔽 360p", callback_data=f"quality:{url}:360p")],
        [InlineKeyboardButton("🔽 720p", callback_data=f"quality:{url}:720p"),
         InlineKeyboardButton("🔽 1080p", callback_data=f"quality:{url}:1080p")],
        [InlineKeyboardButton("🎵 Audio Only (MP3)", callback_data=f"quality:{url}:mp3")]
    ]
    
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown Title')
            thumbnail = info.get('thumbnail')

        await update.message.reply_photo(
            photo=thumbnail,
            caption=f"🎥 *{title}*\n\nSelect the download format:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# Download video/audio
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, url, quality = query.data.split(":")
    ext = "mp4" if quality != "mp3" else "mp3"
    ydl_opts = {
        'format': f'bestvideo[height={quality}]+bestaudio/best' if quality != "mp3" else 'bestaudio',
        'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.{ext}',
        'noplaylist': True,
        'quiet': True
    }

    progress_msg = await query.message.reply_text('⏳ Downloading... Please wait.')

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        await context.bot.edit_message_text(
            chat_id=query.message.chat_id,
            message_id=progress_msg.message_id,
            text="✅ Download complete!"
        )

        # Send file
        if quality == "mp3":
            await context.bot.send_audio(chat_id=query.message.chat_id, audio=open(filename, 'rb'), title=info.get('title'))
        else:
            await context.bot.send_video(chat_id=query.message.chat_id, video=open(filename, 'rb'), caption=f"🎥 {info.get('title')}")

    except Exception as e:
        await query.message.reply_text(f"❌ Error: {e}")

# Main function
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Add inline search handler
    application.add_inline_handler(inline_search)

    application.run_polling()

if __name__ == '__main__':
    main()