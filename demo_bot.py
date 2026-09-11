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

# =========================
# SETTINGS
# =========================

TOKEN = os.environ.get("DEMO_BOT_TOKEN")

# बाद में यहाँ अपनी Telegram User ID डालेंगे
ADMIN_ID = 0

SEARCH_BOT = "https://t.me/TSB_Video_Search_Bot"

DATA_FILE = "demo_data.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


# =========================
# DATA
# =========================

def load_data():
    if not os.path.exists(DATA_FILE):
        return []

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =========================
# /START
# =========================

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
        "Neeche available demo videos hain:"
    )

    for video in data:

        caption = (
            f"🎬 {video['title']}\n\n"
            f"📝 {video['description']}"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "🔎 Search Full Video",
                    url=SEARCH_BOT
                )
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await update.message.reply_video(
                video=video["file_id"],
                caption=caption,
                reply_markup=reply_markup
            )
        except Exception as e:
            logging.error(e)


# =========================
# ADD VIDEO
# =========================

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global ADMIN_ID

    user_id = update.effective_user.id

    # First user ID detection
    if ADMIN_ID == 0:
        ADMIN_ID = user_id

        await update.message.reply_text(
            f"✅ Admin ID detected.\n\n"
            f"Your Telegram ID: `{user_id}`\n\n"
            f"Ab ye bot isi account se manage hoga.",
            parse_mode="Markdown"
        )

    if user_id != ADMIN_ID:
        await update.message.reply_text(
            "❌ You are not allowed to add demo videos."
        )
        return

    video = update.message.video

    context.user_data["pending_video"] = video.file_id

    await update.message.reply_text(
        "🎬 Video mil gaya!\n\n"
        "Ab batao ye video **kis ke bare me hai?**\n\n"
        "Example:\n"
        "Movie Name / Video Name"
    )


# =========================
# VIDEO INFORMATION
# =========================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global ADMIN_ID

    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Please use /start to view demo videos."
        )
        return

    if "pending_video" not in context.user_data:
        await update.message.reply_text(
            "🎬 Demo video add karne ke liye pehle video bhejo."
        )
        return

    title = update.message.text.strip()

    context.user_data["pending_title"] = title

    await update.message.reply_text(
        "📝 Ab is video ka **short description** bhejo.\n\n"
        "Example:\n"
        "Is video me movie ka main scene hai."
    )

    context.user_data["waiting_description"] = True


# =========================
# DESCRIPTION
# =========================

async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global ADMIN_ID

    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        return

    if not context.user_data.get("waiting_description"):
        return

    description = update.message.text.strip()

    video_id = context.user_data["pending_video"]
    title = context.user_data["pending_title"]

    data = load_data()

    data.append({
        "file_id": video_id,
        "title": title,
        "description": description
    })

    save_data(data)

    context.user_data.clear()

    await update.message.reply_text(
        "✅ Demo Video Added!\n\n"
        f"🎬 {title}\n"
        f"📝 {description}\n\n"
        "Ab /start se ye video users ko dikhega."
    )


# =========================
# UNKNOWN MESSAGE
# =========================

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message:
        await update.message.reply_text(
            "❌ Please use /start to view demo videos."
        )


# =========================
# MAIN
# =========================

def main():

    if not TOKEN:
        raise ValueError("DEMO_BOT_TOKEN is missing.")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(
            filters.VIDEO,
            handle_video
        )
    )

    # Description mode पहले check होगा
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_description
        ),
        group=0
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text
        ),
        group=1
    )

    app.add_handler(
        MessageHandler(
            filters.ALL,
            unknown
        ),
        group=2
    )

    print("TSB Demo Bot is running...")

    app.run_polling()


if __name__ == "__main__":
    main()
