require('dotenv').config();
const TelegramBot = require('node-telegram-bot-api');
const ytdl = require('ytdl-core'); // Using ytdl-core
const fs = require('fs');
const path = require('path');
const ffmpeg = require('fluent-ffmpeg'); // For audio extraction
const express = require('express');

const app = express();
const PORT = process.env.PORT || 3000;

// Load environment variables
const token = process.env.TELEGRAM_BOT_TOKEN;
const downloadDir = process.env.DOWNLOAD_DIR || './downloads';
const rateLimit = parseInt(process.env.RATE_LIMIT) || 5;

// Ensure download directory exists
if (!fs.existsSync(downloadDir)) {
    fs.mkdirSync(downloadDir, { recursive: true });
}

// Initialize Telegram bot
const bot = new TelegramBot(token, { polling: true });

// Store user states and rate limits
const userStates = {};
const userRateLimits = {};

// Command to start the bot
bot.onText(/\/start/, (msg) => {
    const chatId = msg.chat.id;
    bot.sendMessage(chatId, 'Welcome! Send me a YouTube URL or playlist to download videos or audio.');
});

// Handle YouTube URL or playlist
bot.on('message', async (msg) => {
    const chatId = msg.chat.id;
    const text = msg.text;

    // Rate limiting
    if (!userRateLimits[chatId]) userRateLimits[chatId] = 0;
    if (userRateLimits[chatId] >= rateLimit) {
        return bot.sendMessage(chatId, 'You have reached the rate limit. Please try again later.');
    }
    userRateLimits[chatId]++;

    if (ytdl.validateURL(text)) {
        try {
            const info = await ytdl.getInfo(text); // Get video info using ytdl-core
            userStates[chatId] = { info, url: text };

            // Send video details and thumbnail
            const title = info.videoDetails.title;
            const thumbnail = info.videoDetails.thumbnails[0].url;
            const description = `Title: ${title}\nDuration: ${info.videoDetails.lengthSeconds}s`;

            bot.sendPhoto(chatId, thumbnail, {
                caption: description,
                reply_markup: {
                    inline_keyboard: [
                        [
                            { text: '🎥 Download Video', callback_data: 'video' },
                            { text: '🎵 Download Audio', callback_data: 'audio' },
                            { text: '📝 Download Subtitles', callback_data: 'subtitles' }
                        ]
                    ]
                }
            });
        } catch (err) {
            bot.sendMessage(chatId, 'Error fetching video info. Please try again.');
            console.error('Error fetching video info:', err);
        }
    } else if (text.startsWith('https://www.youtube.com/playlist?list=')) {
        // Handle playlist
        try {
            const playlistId = new URL(text).searchParams.get('list');
            const playlistInfo = await ytdl.getBasicInfo(text); // Get basic playlist info
            userStates[chatId] = { playlistInfo, url: text };

            bot.sendMessage(chatId, `Playlist: ${playlistInfo.videoDetails.title}\nTotal videos: ${playlistInfo.related_videos.length}`, {
                reply_markup: {
                    inline_keyboard: [
                        [
                            { text: '🎥 Download All Videos', callback_data: 'playlist_video' },
                            { text: '🎵 Download All Audio', callback_data: 'playlist_audio' }
                        ]
                    ]
                }
            });
        } catch (err) {
            bot.sendMessage(chatId, 'Error fetching playlist info. Please try again.');
            console.error('Error fetching playlist info:', err);
        }
    } else if (text !== '/start') {
        bot.sendMessage(chatId, 'Invalid YouTube URL or playlist. Please send a valid URL.');
    }
});

// Handle inline button actions
bot.on('callback_query', async (query) => {
    const chatId = query.message.chat.id;
    const data = query.data;
    const { info, url, playlistInfo } = userStates[chatId];

    if (data === 'video') {
        // Download video
        const title = info.videoDetails.title.replace(/[^a-zA-Z0-9]/g, '_');
        const outputFilePath = path.join(downloadDir, `${title}.mp4`);

        bot.sendMessage(chatId, `Downloading video for "${title}"...`);

        const progressMessage = await bot.sendMessage(chatId, 'Download progress: 0%');

        ytdl(url, { quality: 'highest' })
            .on('progress', (chunkLength, downloaded, total) => {
                const percent = ((downloaded / total) * 100).toFixed(2);
                bot.editMessageText(`Download progress: ${percent}%`, {
                    chat_id: chatId,
                    message_id: progressMessage.message_id
                });
            })
            .pipe(fs.createWriteStream(outputFilePath))
            .on('finish', () => {
                bot.sendVideo(chatId, outputFilePath)
                    .then(() => {
                        fs.unlinkSync(outputFilePath); // Delete the file after sending
                    })
                    .catch(err => {
                        console.error('Error sending video:', err);
                        bot.sendMessage(chatId, 'Error sending video. Please try again.');
                    });
            })
            .on('error', (err) => {
                console.error('Error downloading video:', err);
                bot.sendMessage(chatId, 'Error downloading video. Please try again.');
            });
    } else if (data === 'audio') {
        // Extract audio
        const title = info.videoDetails.title.replace(/[^a-zA-Z0-9]/g, '_');
        const outputFilePath = path.join(downloadDir, `${title}.mp3`);

        bot.sendMessage(chatId, `Downloading audio for "${title}"...`);

        ytdl(url, { filter: 'audioonly', quality: 'highestaudio' })
            .pipe(fs.createWriteStream(outputFilePath))
            .on('finish', () => {
                bot.sendAudio(chatId, outputFilePath)
                    .then(() => {
                        fs.unlinkSync(outputFilePath); // Delete the file after sending
                    })
                    .catch(err => {
                        console.error('Error sending audio:', err);
                        bot.sendMessage(chatId, 'Error sending audio. Please try again.');
                    });
            })
            .on('error', (err) => {
                console.error('Error downloading audio:', err);
                bot.sendMessage(chatId, 'Error downloading audio. Please try again.');
            });
    } else if (data === 'subtitles') {
        // Download subtitles (not natively supported by ytdl-core)
        bot.sendMessage(chatId, 'Subtitle download is not supported with ytdl-core. Please use yt-dlp for this feature.');
    } else if (data === 'playlist_video' || data === 'playlist_audio') {
        // Download entire playlist
        const isAudio = data === 'playlist_audio';
        const totalVideos = playlistInfo.related_videos.length;

        bot.sendMessage(chatId, `Downloading ${totalVideos} ${isAudio ? 'audio files' : 'videos'}...`);

        for (let i = 0; i < totalVideos; i++) {
            const video = playlistInfo.related_videos[i];
            const videoUrl = `https://www.youtube.com/watch?v=${video.id}`;
            const title = video.title.replace(/[^a-zA-Z0-9]/g, '_');
            const outputFilePath = path.join(downloadDir, `${title}.${isAudio ? 'mp3' : 'mp4'}`);

            if (isAudio) {
                ytdl(videoUrl, { filter: 'audioonly', quality: 'highestaudio' })
                    .pipe(fs.createWriteStream(outputFilePath))
                    .on('finish', () => {
                        bot.sendAudio(chatId, outputFilePath)
                            .then(() => {
                                fs.unlinkSync(outputFilePath); // Delete the file after sending
                            })
                            .catch(err => {
                                console.error('Error sending audio:', err);
                            });
                    });
            } else {
                ytdl(videoUrl, { quality: 'highest' })
                    .pipe(fs.createWriteStream(outputFilePath))
                    .on('finish', () => {
                        bot.sendVideo(chatId, outputFilePath)
                            .then(() => {
                                fs.unlinkSync(outputFilePath); // Delete the file after sending
                            })
                            .catch(err => {
                                console.error('Error sending video:', err);
                            });
                    });
            }
        }
    }
});

// Start the bot
app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
});
console.log('Bot is running...');
