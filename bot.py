import os
     import yt_dlp
     from telegram import Update
     from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
     from dotenv import load_dotenv

     # Load environment variables from .env file
     load_dotenv()

     # Get the bot token from the environment variable
     BOT_TOKEN = os.getenv('BOT_TOKEN')

     async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
         await update.message.reply_text('Welcome! Send me a YouTube link to download the video.')

     async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
         url = update.message.text
         download_directory = 'downloads'

         if not os.path.exists(download_directory):
             os.makedirs(download_directory)

         ydl_opts = {
             'outtmpl': f'{download_directory}/%(title)s.%(ext)s',
             'format': 'best',
         }

         try:
             with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                 info = ydl.extract_info(url, download=True)
                 video_title = info.get('title', 'video')
                 video_file = ydl.prepare_filename(info)

             await update.message.reply_text(f'Download successful: {video_title}')
             await update.message.reply_document(document=open(video_file, 'rb'))
         except Exception as e:
             await update.message.reply_text(f'Error: {e}')

     def main():
         application = Application.builder().token(BOT_TOKEN).build()

         application.add_handler(CommandHandler('start', start))
         application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

         application.run_polling()

     if __name__ == '__main__':
         main()