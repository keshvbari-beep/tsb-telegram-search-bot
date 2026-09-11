import os
import json
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.environ.get("DEMO_BOT_TOKEN")

# अपना Telegram ID यहाँ डालना
ADMIN_ID = 1881432851

SEARCH_BOT = "https://t.me/TSB_Video_Search_Bot"
DATA_FILE = "demo_data.json"

logging.basicConfig(level=logging.INFO)


def load_data():
    if not os.path.exists(DATA_FILE):
        return []

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()

    if not data:
        await update.message.reply_text(
            "🎬 TSB Demo Videos\n\n"
            "Abhi koi demo video available nahi hai."
        )
        return

    await update.message.reply_text(
        "🎬 TSB Demo Videos\n\n"
        "👇 Available Demo Videos:"
    )

    for video in data:
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔎 Search Full Video",
                    url=SEARCH_BOT
                )
            ]
        ]

        await update.message.reply_video(
            video=video["file_id"],
            caption=(
                f"🎬 {video['title']}\n\n"
                f"📝 {video['description']}"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Please use /start to view demo videos."
        )
        return

    context.user_data["video_id"] = update.message.video.file_id
    context.user_data["waiting_title"] = True
    context.user_data["waiting_description"] = False

    await update.message.reply_text(
        "🎬 Video mil gaya!\n\n"
        "Ab batao ye video kis ke bare me hai?\n\n"
        "Example: Movie Name / Video Name"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Please use /start to view demo videos."
        )
        return

    text = update.message.text.strip()

    # TITLE
    if context.user_data.get("waiting_title"):
        context.user_data["title"] = text
        context.user_data["waiting_title"] = False
        context.user_data["waiting_description"] = True

        await update.message.reply_text(
            "📝 Ab is video ka short description bhejo."
        )
        return

    # DESCRIPTION
    if context.user_data.get("waiting_description"):
        description = text

        data = load_data()

        data.append({
            "file_id": context.user_data["video_id"],
            "title": context.user_data["title"],
            "description": description
        })

        save_data(data)

        title = context.user_data["title"]
        context.user_data.clear()

        await update.message.reply_text(
            "✅ Demo Video Added!\n\n"
            f"🎬 {title}\n"
            f"📝 {description}\n\n"
            "अब /start भेजकर check करो."
        )
        return

    await update.message.reply_text(
        "🎬 Demo video add karne ke liye pehle video bhejo."
    )


def main():
    if not TOKEN:
        raise ValueError("DEMO_BOT_TOKEN is missing.")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(filters.VIDEO, handle_video)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text
        )
    )

    print("TSB Demo Bot is running...")

    app.run_polling()


if __name__ == "__main__":
    main()
