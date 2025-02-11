// Modules
const Telegraf = require('telegraf');
const fs = require('fs');
const youtubedl = require('youtube-dl-exec');
const winston = require('winston');
require('dotenv').config(); // Load environment variables from .env

// Winston Logger Setup
const logger = winston.createLogger({
    level: "info",
    format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.printf(info => {
            return `${info.timestamp} ${info.level}: ${info.message}`;
        }),
    ),
    transports: [
        new winston.transports.Console(),
        new winston.transports.File({ filename: 'info.log' })
    ]
});

// Global Vars
const DOWN_URL = "https://www.youtube.com/watch?v=";
let infor;
const TeleMaxData = 50; // 50mb || This might change in the future!
let videosize;

// Bot setup
const bot = new Telegraf(process.env.TELEGRAM_BOT_TOKEN); // Load token from .env
logger.log('info', "Bot is running;; TOKEN: " + process.env.TELEGRAM_BOT_TOKEN);

// Bot commands
bot.start((ctx) => ctx.reply('Hey there!\nI\'m sending Youtube videos to you!'));
bot.help((ctx) => ctx.reply('Send me a link and I will send you the vid :) \n cmds: \n \n /video {videoID}'));
bot.startPolling();

// Catch all errors from bot
bot.catch((err) => logger.log('info', err));

// Commands
bot.command('/video', async (ctx) => {
    try {
        const userID = ctx.from.id;
        const input = ctx.message.text;
        const subText = input.split(" ");
        let videoURL;

        logger.log('info', `-----------NEW_DOWNLOAD_BY_${userID}-----------`);

        if (subText[1].includes("https://youtu.be/")) {
            const subSplit = subText[1].split(".be/");
            videoURL = DOWN_URL + subSplit[1];
        } else {
            videoURL = DOWN_URL + subText[1];
        }
        logger.log('info', `Youtube video URL: ${videoURL}`);

        // Temporary file path
        const tempFilePath = `${__dirname}/${userID}_temp.mp4`;

        // Download video using youtube-dl-exec
        const result = await youtubedl(videoURL, {
            format: 'mp4',
            output: tempFilePath,
        });

        // Get video info
        const info = await youtubedl(videoURL, { dumpSingleJson: true });
        infor = info;
        videosize = info.filesize / 1000000;

        if (videosize < TeleMaxData) {
            ctx.reply('Download Started');

            // Send the video
            await ctx.replyWithVideo({
                source: fs.createReadStream(tempFilePath)
            });

            // Delete the video immediately after sending
            fs.unlink(tempFilePath, (err) => {
                if (err) {
                    logger.log('info', `Error deleting file: ${err}`);
                } else {
                    logger.log('info', `File deleted: ${tempFilePath}`);
                }
            });

            ctx.reply(`Download completed!\nVideo sent! \n \n Title: \n ${infor.title}. It's ${videosize}mb big.`);
            logger.log('info', `Video sent! \n Title: ${infor.title}, Size: ${videosize}`);
        } else {
            ctx.reply(`The video is ${videosize}mb. The maximum size for sending videos from Telegram is ${TeleMaxData}mb.`);
            logger.log('info', `The video size is too big! (${videosize}mb)`);
        }
    } catch (err) {
        ctx.reply("ERROR");
        logger.log("info", `Error: ${err}`);
    }
});