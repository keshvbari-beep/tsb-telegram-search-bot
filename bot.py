import os
import logging
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from supabase import create_client, Client


# ============================================================
# SETTINGS
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()


CHANNELS = {
    "-1004338671388": "Channel 1",
    "-1004490954138": "Channel 2",
    "-1003963263624": "Channel 3",
    "-1003472229143": "Channel 4",
}


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# SUPABASE
# ============================================================

supabase: Client | None = None


def init_supabase():
    global supabase

    if not SUPABASE_URL:
        raise RuntimeError("SUPABASE_URL secret is missing")

    if not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_KEY secret is missing")

    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY,
    )

    logger.info("Supabase client created")


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize(value) -> str:
    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .upper()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )


def clean_text(value) -> str:
    if value is None:
        return ""

    return str(value).strip().lower()


# ============================================================
# LOAD DATABASE
# ============================================================

def load_videos():
    if supabase is None:
        init_supabase()

    all_rows = []
    page_size = 1000
    start = 0

    while True:
        response = (
            supabase
            .table("videos")
            .select("*")
            .range(start, start + page_size - 1)
            .execute()
        )

        rows = response.data or []

        if not rows:
            break

        all_rows.extend(rows)

        if len(rows) < page_size:
            break

        start += page_size

    logger.info("DATABASE ROWS = %s", len(all_rows))

    return all_rows


# ============================================================
# SEARCH DATABASE
# ============================================================

def search_database(query: str):
    query_original = query.strip()
    query_norm = normalize(query_original)
    query_text = clean_text(query_original)

    rows = load_videos()

    exact_matches = []
    partial_matches = []
    text_matches = []

    for row in rows:
        code = row.get("code", "")
        name = row.get("name", "")
        description = row.get("description", "")

        code_norm = normalize(code)
        name_text = clean_text(name)
        description_text = clean_text(description)

        # Exact code
        if query_norm and code_norm == query_norm:
            exact_matches.append(row)
            continue

        # Partial code
        if query_norm and query_norm in code_norm:
            partial_matches.append(row)
            continue

        # Name / description search
        if query_text:
            if query_text in name_text or query_text in description_text:
                text_matches.append(row)

    if exact_matches:
        return exact_matches

    if partial_matches:
        return partial_matches

    return text_matches


# ============================================================
# CHANNEL ACCESS CHECK
# ============================================================

async def user_has_access(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    channel_id: str,
) -> bool:

    try:
        member = await context.bot.get_chat_member(
            chat_id=int(channel_id),
            user_id=user_id,
        )

        status = member.status

        return status in (
            "creator",
            "administrator",
            "member",
        )

    except Exception as e:
        logger.warning(
            "Membership check failed | channel=%s | user=%s | error=%s",
            channel_id,
            user_id,
            e,
        )

        return False


# ============================================================
# OPEN POST BUTTON
# ============================================================

def make_post_url(channel_id: str, message_id: int) -> str:
    clean_channel_id = str(channel_id)

    if clean_channel_id.startswith("-100"):
        clean_channel_id = clean_channel_id[4:]

    return f"https://t.me/c/{clean_channel_id}/{message_id}"


# ============================================================
# START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message is None:
        return

    text = (
        "🔎 TSB Search Bot\n\n"
        "Apna Code ya Video Name search karo.\n\n"
        "Examples:\n"
        "1P-234\n"
        "2P-001\n"
        "3P-125\n"
        "4P-500"
    )

    await update.message.reply_text(text)


# ============================================================
# HELP
# ============================================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message is None:
        return

    text = (
        "🔎 TSB Search Help\n\n"
        "Code ya video ka naam bhejo.\n\n"
        "Example:\n"
        "1P-444\n\n"
        "Bot database se matching video search karega."
    )

    await update.message.reply_text(text)


# ============================================================
# SEARCH MESSAGE
# ============================================================

async def search_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if update.message is None:
        return

    query = update.message.text.strip()

    if not query:
        return

    if query.startswith("/"):
        return

    waiting = await update.message.reply_text(
        "🔎 Searching..."
    )

    try:
        results = await asyncio.to_thread(
            search_database,
            query,
        )

    except Exception as e:
        logger.exception("SEARCH ERROR")

        await waiting.edit_text(
            "⚠️ Database search error.\n\n"
            "Please try again."
        )

        return

    if not results:
        await waiting.edit_text(
            "❌ No result found.\n\n"
            "Example:\n"
            "1P-234\n"
            "2P-001"
        )

        return

    await waiting.delete()

    user_id = update.effective_user.id

    # Limit results to 10
    results = results[:10]

    for index, row in enumerate(results):

        code = str(row.get("code") or "Unknown Code")
        name = str(row.get("name") or "Untitled")
        description = str(row.get("description") or "")
        photo = row.get("photo")
        channel_id = str(row.get("channel_id") or "")
        message_id = row.get("message_id")

        if not channel_id or not message_id:
            continue

        access = await user_has_access(
            context,
            user_id,
            channel_id,
        )

        if access:
            post_url = make_post_url(
                channel_id,
                int(message_id),
            )

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📂 Open Post",
                            url=post_url,
                        )
                    ]
                ]
            )

            caption = (
                f"🎬 {name}\n\n"
                f"🔢 Code: {code}"
            )

            if description:
                caption += f"\n\n📄 {description}"

            try:
                if photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption=caption,
                        reply_markup=keyboard,
                    )
                else:
                    await update.message.reply_text(
                        caption,
                        reply_markup=keyboard,
                    )

            except Exception as e:
                logger.warning(
                    "Photo send failed: %s",
                    e,
                )

                await update.message.reply_text(
                    caption,
                    reply_markup=keyboard,
                )

        else:
            channel_name = CHANNELS.get(
                channel_id,
                "Private Channel",
            )

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "💳 Subscribe & Access",
                            callback_data=f"subscribe:{channel_id}",
                        )
                    ]
                ]
            )

            caption = (
                f"🔒 {name}\n\n"
                f"🔢 Code: {code}\n\n"
                f"📢 {channel_name}\n\n"
                "Access required to open this post."
            )

            if description:
                caption += f"\n\n📄 {description}"

            try:
                if photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption=caption,
                        reply_markup=keyboard,
                    )
                else:
                    await update.message.reply_text(
                        caption,
                        reply_markup=keyboard,
                    )

            except Exception as e:
                logger.warning(
                    "Restricted result send failed: %s",
                    e,
                )

    logger.info(
        "SEARCH | user=%s | query=%s | results=%s",
        user_id,
        query,
        len(results),
    )


# ============================================================
# SUBSCRIBE BUTTON
# ============================================================

async def subscribe_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if query is None:
        return

    await query.answer()

    data = query.data or ""

    if not data.startswith("subscribe:"):
        return

    channel_id = data.split(":", 1)[1]

    channel_name = CHANNELS.get(
        channel_id,
        "Private Channel",
    )

    text = (
        f"💳 Subscribe & Access\n\n"
        f"📢 {channel_name}\n\n"
        "Payment system will be connected here.\n\n"
        "After successful payment, access will be enabled."
    )

    await query.message.reply_text(text)


# ============================================================
# DATABASE TEST
# ============================================================

async def dbtest(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message is None:
        return

    try:
        rows = await asyncio.to_thread(
            load_videos
        )

        await update.message.reply_text(
            "✅ Supabase Connected\n\n"
            f"📦 Total database rows: {len(rows)}"
        )

    except Exception as e:

        logger.exception("DBTEST ERROR")

        await update.message.reply_text(
            "❌ Supabase connection failed.\n\n"
            f"Error: {str(e)[:500]}"
        )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    logger.exception(
        "BOT ERROR",
        exc_info=context.error,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN secret is missing"
        )

    init_supabase()

    logger.info("Testing Supabase...")

    rows = load_videos()

    logger.info(
        "SUPABASE OK | ROW COUNT = %s",
        len(rows),
    )

    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "dbtest",
            dbtest,
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            subscribe_callback,
            pattern=r"^subscribe:",
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            search_message,
        )
    )

    application.add_error_handler(
        error_handler
    )

    logger.info(
        "TSB SEARCH BOT STARTING..."
    )

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
