from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

BOT_TOKEN = "8908632279:AAF-Glydyj_2ETCYkeswpwRuNKztWOql110"

async def get_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.channel_post:
        chat = update.channel_post.chat
        print("CHANNEL ID:", chat.id)
        print("CHANNEL NAME:", chat.title)

app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(
    MessageHandler(filters.ALL, get_channel_id)
)

print("Bot is running...")
app.run_polling()
