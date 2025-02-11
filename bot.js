require('dotenv').config();
const TelegramBot = require('node-telegram-bot-api');
const ytdlp = require('yt-dlp-exec').exec;
const fs = require('fs');
const path = require('path');
const ffmpeg = require('fluent-ffmpeg');
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

    if (ytdlp.validateURL(text)) {
        try {
            const info = await ytdlp(text, { dumpSingleJson: true });
            userStates[chatId] = { info, url: text };

            // Send video details and thumbnail
            const title = info.title;
            const thumbnail = info.thumbnail;
            const description = `Title: ${title}\nDuration: ${info.duration}s`;

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
            const playlistInfo = await ytdlp(text, { dumpSingleJson: true });
            userStates[chatId] = { playlistInfo, url: text };

            bot.sendMessage(chatId, `Playlist: ${playlistInfo.title}\nTotal videos: ${playlistInfo.entries.length}`, {
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
        // Send video format options
        const formats = info.formats.filter(format => format.vcodec !== 'none' && format.acodec !== 'none');
        const buttons = formats.map(format => ({
            text: `${format.format_note || format.ext} - ${format.filesize ? (format.filesize / 1024 / 1024).toFixed(2) + 'MB' : 'Unknown'}`,
            callback_data: `format_${format.format_id}`
        }));

        bot.sendMessage(chatId, 'Choose a video format:', {
            reply_markup: {
                inline_keyboard: [buttons]
            }
        });
    } else if (data === 'audio') {
        // Extract audio
        const title = info.title.replace(/[^a-zA-Z0-9]/g, '_');
        const outputFilePath = path.join(downloadDir, `${title}.mp3`);

        bot.sendMessage(chatId, `Downloading audio for "${title}"...`);

        ytdlp(url, {
            extractAudio: true,
            audioFormat: 'mp3',
            output: outputFilePath
        })
            .then(() => {
                bot.sendAudio(chatId, outputFilePath)
                    .then(() => {
                        fs.unlinkSync(outputFilePath); // Delete the file after sending
                    })
                    .catch(err => {
                        console.error('Error sending audio:', err);
                        bot.sendMessage(chatId, 'Error sending audio. Please try again.');
                    });
            })
            .catch(err => {
                console.error('Error downloading audio:', err);
                bot.sendMessage(chatId, 'Error downloading audio. Please try again.');
            });
    } else if (data === 'subtitles') {
        // Download subtitles
        const title = info.title.replace(/[^a-zA-Z0-9]/g, '_');
        const subtitles = info.subtitles;

        if (subtitles && subtitles.length > 0) {
            const subtitle = subtitles[0];
            const outputFilePath = path.join(downloadDir, `${title}.${subtitle.ext}`);

            bot.sendMessage(chatId, `Downloading subtitles for "${title}"...`);

            fs.writeFileSync(outputFilePath, subtitle.url);
            bot.sendDocument(chatId, outputFilePath)
                .then(() => {
                    fs.unlinkSync(outputFilePath); // Delete the file after sending
                })
                .catch(err => {
                    console.error('Error sending subtitles:', err);
                    bot.sendMessage(chatId, 'Error sending subtitles. Please try again.');
                });
        } else {
            bot.sendMessage(chatId, 'No subtitles available for this video.');
        }
    } else if (data.startsWith('format_')) {
        // Download selected video format
        const formatId = data.split('_')[1];
        const format = info.formats.find(f => f.format_id === formatId);

        if (format) {
            const title = info.title.replace(/[^a-zA-Z0-9]/g, '_');
            const outputFilePath = path.join(downloadDir, `${title}.${format.ext}`);

            bot.sendMessage(chatId, `Downloading "${title}" in ${format.format_note || format.ext}...`);

            const progressMessage = await bot.sendMessage(chatId, 'Download progress: 0%');

            ytdlp(url, {
                format: formatId,
                output: outputFilePath
            })
                .on('progress', (progress) => {
                    const percent = (progress.percent || 0).toFixed(2);
                    bot.editMessageText(`Download progress: ${percent}%`, {
                        chat_id: chatId,
                        message_id: progressMessage.message_id
                    });
                })
                .then(() => {
                    bot.sendDocument(chatId, outputFilePath)
                        .then(() => {
                            fs.unlinkSync(outputFilePath); // Delete the file after sending
                        })
                        .catch(err => {
                            console.error('Error sending file:', err);
                            bot.sendMessage(chatId, 'Error sending file. Please try again.');
                        });
                })
                .catch(err => {
                    console.error('Error downloading video:', err);
                    bot.sendMessage(chatId, 'Error downloading video. Please try again.');
                });
        } else {
            bot.sendMessage(chatId, 'Invalid format selected. Please try again.');
        }
    } else if (data === 'playlist_video' || data === 'playlist_audio') {
        // Download entire playlist
        const isAudio = data === 'playlist_audio';
        const totalVideos = playlistInfo.entries.length;

        bot.sendMessage(chatId, `Downloading ${totalVideos} ${isAudio ? 'audio files' : 'videos'}...`);

        for (let i = 0; i < totalVideos; i++) {
            const video = playlistInfo.entries[i];
            const title = video.title.replace(/[^a-zA-Z0-9]/g, '_');
            const outputFilePath = path.join(downloadDir, `${title}.${isAudio ? 'mp3' : 'mp4'}`);

            if (isAudio) {
                ytdlp(video.url, {
                    extractAudio: true,
                    audioFormat: 'mp3',
                    output: outputFilePath
                })
                    .then(() => {
                        bot.sendAudio(chatId, outputFilePath)
                            .then(() => {
                                fs.unlinkSync(outputFilePath); // Delete the file after sending
                            })
                            .catch(err => {
                                console.error('Error sending audio:', err);
                            });
                    });
            } else {
                ytdlp(video.url, {
                    format: 'best',
                    output: outputFilePath
                })
                    .then(() => {
                        bot.sendDocument(chatId, outputFilePath)
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
