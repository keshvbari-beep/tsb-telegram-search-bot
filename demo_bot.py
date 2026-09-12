import os
import logging
from supabase import create_client
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# =========================
# SETTINGS
# =========================

BOT_TOKEN = os.getenv("DEMO_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

ADMIN_ID = int(os.getenv("DEMO_ADMIN_ID", "1881432851"))

SEARCH_BOT = "https://t.me/TSB_Video_Search_Bot"

# Conversation states
VIDEO, TITLE, DESCRIPTION = range(3)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================
# CHECK SETTINGS
# =========================

if not BOT_TOKEN:
    raise RuntimeError("DEMO_BOT_TOKEN is missing")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing")

if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_KEY is missing")


# =========================
# SUPABASE
# =========================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        result = (
            supabase
            .table("demo_videos")
            .select("id,file_id,title,description")
            .eq("active", True)
            .order("id", desc=False)
            .execute()
        )

        videos = result.data or []

        if not videos:
            await update.message.reply_text(
                "🎬 TSB Demo\n\n"
                "अभी कोई Demo Video उपलब्ध नहीं है।"
            )
            return

        await update.message.reply_text(
            "🎬 TSB Demo Videos\n\n"
            "नीचे available demo videos हैं:"
        )

        for video in videos:

            file_id = video.get("file_id")
            title = video.get("title") or "Untitled"
            description = video.get("description") or ""

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔎 Search Full Video",
                        url=SEARCH_BOT
                    )
                ]
            ])

            caption = (
                f"🎬 {title}\n\n"
                f"{description}"
            )

            try:
                await update.message.reply_video(
                    video=file_id,
                    caption=caption,
                    reply_markup=keyboard
                )

            except Exception as e:
                logger.error(
                    "Error sending demo video %s: %s",
                    video.get("id"),
                    e
                )

    except Exception as e:

        logger.exception("Start error")

        await update.message.reply_text(
            "❌ Demo videos load नहीं हो पाए।\n"
            "कृपया थोड़ी देर बाद फिर कोशिश करें।"
        )


# =========================
# ADD DEMO
# =========================

async def add_demo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:

        await update.message.reply_text(
            "❌ आपको Demo upload करने की permission नहीं है।"
        )

        return ConversationHandler.END

    await update.message.reply_text(
        "🎬 Demo Video भेजो:"
    )

    return VIDEO


# =========================
# RECEIVE VIDEO
# =========================

async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    if not update.message.video:

        await update.message.reply_text(
            "❌ केवल video भेजो।"
        )

        return VIDEO

    video = update.message.video

    context.user_data["demo_file_id"] = video.file_id

    await update.message.reply_text(
        "📝 अब Demo का Title भेजो:"
    )

    return TITLE


# =========================
# RECEIVE TITLE
# =========================

async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    title = update.message.text.strip()

    if not title:

        await update.message.reply_text(
            "❌ Title खाली नहीं हो सकता।\n"
            "फिर से Title भेजो:"
        )

        return TITLE

    context.user_data["demo_title"] = title

    await update.message.reply_text(
        "📄 अब Demo का Description भेजो:"
    )

    return DESCRIPTION


# =========================
# RECEIVE DESCRIPTION
# =========================

async def receive_description(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    description = update.message.text.strip()

    if not description:

        await update.message.reply_text(
            "❌ Description खाली नहीं हो सकता।\n"
            "फिर से Description भेजो:"
        )

        return DESCRIPTION

    file_id = context.user_data.get("demo_file_id")
    title = context.user_data.get("demo_title")

    if not file_id or not title:

        await update.message.reply_text(
            "❌ Demo data missing है।\n"
            "फिर से /adddemo शुरू करो।"
        )

        return ConversationHandler.END

    # =========================
    # SAVE TO SUPABASE
    # =========================

    try:

        result = (
            supabase
            .table("demo_videos")
            .insert({
                "file_id": file_id,
                "title": title,
                "description": description,
                "active": True
            })
            .execute()
        )

        if not result.data:

            raise Exception(
                "Supabase returned no inserted row"
            )

        saved_id = result.data[0].get("id")

        await update.message.reply_text(
            "✅ DEMO VIDEO ADDED!\n\n"
            f"🎬 Title: {title}\n"
            f"📄 Description: {description}\n"
            f"🆔 ID: {saved_id}\n\n"
            "💾 Database Save ✓"
        )

    except Exception as e:

        logger.exception("Supabase insert error")

        await update.message.reply_text(
            "❌ Demo save नहीं हुआ।\n\n"
            f"Error: {str(e)}"
        )

    # Clear temporary data
    context.user_data.pop("demo_file_id", None)
    context.user_data.pop("demo_title", None)

    return ConversationHandler.END


# =========================
# CANCEL
# =========================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data.pop("demo_file_id", None)
    context.user_data.pop("demo_title", None)

    await update.message.reply_text(
        "❌ Demo upload cancel कर दिया गया।"
    )

    return ConversationHandler.END


# =========================
# ERROR HANDLER
# =========================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.exception(
        "Telegram error:",
        exc_info=context.error
    )


# =========================
# MAIN
# =========================

def main():

    logger.info("Starting TSB Demo Bot...")

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # /start
    application.add_handler(
        CommandHandler("start", start)
    )

    # /adddemo conversation
    conversation_handler = ConversationHandler(
        entry_points=[
            CommandHandler("adddemo", add_demo)
        ],

        states={

            VIDEO: [
                MessageHandler(
                    filters.VIDEO,
                    receive_video
                )
            ],

            TITLE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_title
                )
            ],

            DESCRIPTION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_description
                )
            ],
        },

        fallbacks=[
            CommandHandler("cancel", cancel)
        ],

        allow_reentry=True
    )

    application.add_handler(
        conversation_handler
    )

    application.add_error_handler(
        error_handler
    )

    logger.info("TSB Demo Bot is running.")

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
