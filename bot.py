from urllib.parse import urlparse
import datetime
import telebot
import yt_dlp
import re
import os
from telebot import types
from telebot.util import quick_markup
import time
from dotenv import load_dotenv
import subprocess

# Load environment variables from .env file
load_dotenv()

# Initialize the bot with the token from .env
bot = telebot.TeleBot(os.getenv('BOT_TOKEN'))
last_edited = {}

def youtube_url_validation(url):
    youtube_regex = (
        r'(https?://)?(www.)?'
        r'(youtube|youtu|youtube-nocookie).(com|be)/'
        r'(watch?v=|embed/|v/|.+?v=)?([^&=%?]{11})'
    )

    youtube_regex_match = re.match(youtube_regex, url)
    if youtube_regex_match:
        return youtube_regex_match

    return youtube_regex_match

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_message = (
        f"👋 Hello *{message.from_user.first_name}*! Welcome to *ClickYoutube*! 🎉\n\n"
        "I'm here to make your video downloading experience super easy and fun! 🎥\n\n"
        "Just send me a video link from YouTube, Twitter, TikTok, Reddit, or other supported platforms, "
        "and I'll download it for you in no time! ⏱️\n\n"
        "Here are some commands you can use:\n"
        "- /download <url> - Download a video\n"
        "- /audio <url> - Download audio only\n"
        "- /custom <url> - Choose a custom format\n\n"
        "Let's get started! Send me a link and I'll do the rest! 🚀\n\n"
        "_Powered by @DevClickBots_"
    )
    bot.reply_to(
        message,
        welcome_message,
        parse_mode="MARKDOWN",
        disable_web_page_preview=True
    )

def compress_video(input_path, output_path, target_size_mb=50):
    target_size_bytes = target_size_mb * 1000000  # Convert MB to bytes
    command = [
        'ffmpeg', '-i', input_path, '-vf', 'scale=640:-1', '-b:v', '1000k',
        '-maxrate', '1000k', '-bufsize', '2000k', output_path
    ]
    subprocess.run(command)

    # Check if the compressed file is within the size limit
    if os.path.getsize(output_path) > target_size_bytes:
        # Further compress if needed
        command = [
            'ffmpeg', '-i', input_path, '-vf', 'scale=480:-1', '-b:v', '500k',
            '-maxrate', '500k', '-bufsize', '1000k', output_path
        ]
        subprocess.run(command)

def convert_video(input_path, output_path):
    command = [
        'ffmpeg', '-i', input_path, '-c:v', 'libx264', '-c:a', 'aac', output_path
    ]
    subprocess.run(command)

def download_video(message, url, audio=False, format_id="mp4"):
    url_info = urlparse(url)
    if url_info.scheme:
        if url_info.netloc in ['www.youtube.com', 'youtu.be', 'youtube.com', 'youtu.be']:
            if not youtube_url_validation(url):
                bot.reply_to(message, 'Invalid URL')
                return

    def progress(d):
        if d['status'] == 'downloading':
            try:
                update = False

                if last_edited.get(f"{message.chat.id}-{msg.message_id}"):
                    if (datetime.datetime.now() - last_edited[f"{message.chat.id}-{msg.message_id}"]).total_seconds() >= 5:
                        update = True
                else:
                    update = True

                if update:
                    perc = round(d['downloaded_bytes'] * 100 / d['total_bytes'])
                    bot.edit_message_text(
                        chat_id=message.chat.id, message_id=msg.message_id, text=f"Downloading {d['info_dict']['title']}\n\n{perc}%")
                    last_edited[f"{message.chat.id}-{msg.message_id}"] = datetime.datetime.now()
            except Exception as e:
                print(e)

    msg = bot.reply_to(message, 'Downloading...')
    video_title = round(time.time() * 1000)

    ydl_opts = {
        'format': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
        'outtmpl': f'outputs/{video_title}.%(ext)s',
        'progress_hooks': [progress],
        'max_filesize': int(os.getenv('MAX_FILESIZE', 50000000))
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

        try:
            bot.edit_message_text(
                chat_id=message.chat.id, message_id=msg.message_id, text='Sending file to Telegram...')
            try:
                if audio:
                    bot.send_audio(message.chat.id, open(
                        info['requested_downloads'][0]['filepath'], 'rb'), reply_to_message_id=message.message_id)

                else:
                    # Compress the video
                    compressed_path = f'outputs/{video_title}_compressed.mp4'
                    compress_video(info['requested_downloads'][0]['filepath'], compressed_path)

                    # Convert the video to a compatible format
                    converted_path = f'outputs/{video_title}_converted.mp4'
                    convert_video(compressed_path, converted_path)

                    # Send the converted video
                    with open(converted_path, 'rb') as video_file:
                        bot.send_video(
                            chat_id=message.chat.id,
                            video=video_file,
                            reply_to_message_id=message.message_id,
                            supports_streaming=True
                        )
                bot.delete_message(message.chat.id, msg.message_id)
            except Exception as e:
                print(f"Error sending file: {e}")
                bot.edit_message_text(
                    chat_id=message.chat.id, message_id=msg.message_id, text=f"Couldn't send file: {e}")
        except Exception as e:
            print(f"Error downloading video: {e}")
            bot.edit_message_text(
                chat_id=message.chat.id, message_id=msg.message_id, text=f"Error downloading video: {e}")
    for file in os.listdir('outputs'):
        if file.startswith(str(video_title)):
            os.remove(f'outputs/{file}')

def log(message, text: str, media: str):
    if os.getenv('LOGS'):
        if message.chat.type == 'private':
            chat_info = "Private chat"
        else:
            chat_info = f"Group: {message.chat.title} ({message.chat.id})"

        bot.send_message(
            os.getenv('LOGS'), f"Download request ({media}) from @{message.from_user.username} ({message.from_user.id})\n\n{chat_info}\n\n{text}")

def get_text(message):
    if len(message.text.split(' ')) < 2:
        if message.reply_to_message and message.reply_to_message.text:
            return message.reply_to_message.text
        else:
            return None
    else:
        return message.text.split(' ')[1]

@bot.message_handler(commands=['download'])
def download_command(message):
    text = get_text(message)
    if not text:
        bot.reply_to(
            message, 'Invalid usage, use /download url', parse_mode="MARKDOWN")
        return

    log(message, text, 'video')
    download_video(message, text)

@bot.message_handler(commands=['audio'])
def download_audio_command(message):
    text = get_text(message)
    if not text:
        bot.reply_to(
            message, 'Invalid usage, use /audio url', parse_mode="MARKDOWN")
        return

    log(message, text, 'audio')
    download_video(message, text, True)

@bot.message_handler(commands=['custom'])
def custom(message):
    text = get_text(message)
    if not text:
        bot.reply_to(
            message, 'Invalid usage, use /custom url', parse_mode="MARKDOWN")
        return

    msg = bot.reply_to(message, 'Getting formats...')

    with yt_dlp.YoutubeDL() as ydl:
        info = ydl.extract_info(text, download=False)

    data = {f"{x['resolution']}.{x['ext']}": {
        'callback_data': f"{x['format_id']}"} for x in info['formats'] if x['video_ext'] != 'none'}

    markup = quick_markup(data, row_width=2)

    bot.delete_message(msg.chat.id, msg.message_id)
    bot.reply_to(message, "Choose a format", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.from_user.id == call.message.reply_to_message.from_user.id:
        url = get_text(call.message.reply_to_message)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        download_video(call.message.reply_to_message, url, format_id=f"{call.data}+bestaudio")
    else:
        bot.answer_callback_query(call.id, "You didn't send the request")

@bot.message_handler(func=lambda m: True, content_types=["text", "pinned_message", "photo", "audio", "video", "location", "contact", "voice", "document"])
def handle_private_messages(message):
    text = message.text if message.text else message.caption if message.caption else None

    if message.chat.type == 'private':
        log(message, text, 'video')
        download_video(message, text)
        return

bot.infinity_polling()