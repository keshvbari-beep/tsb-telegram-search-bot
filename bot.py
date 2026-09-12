import os
import re
import logging

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


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "").strip()

SUPPORT_URL = "https://t.me/RajanChauhan_club"


CHANNELS = {
    "-1004338671388": {
        "name": "Channel 1",
        "prefix": "1P-",
        "price": 299,
    },
    "-1004490954138": {
        "name": "Channel 2",
        "prefix": "2P-",
        "price": 299,
    },
    "-1003963263624": {
        "name": "Channel 3",
        "prefix": "3P-",
        "price": 299,
    },
    "-1003472229143": {
        "name": "Channel 4",
        "prefix": "4P-",
        "price": 299,
    },
}


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("TSB_SEARCH")


# =========================================================
# CHECK CONFIG
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing")

if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_KEY is missing")


# =========================================================
# SUPABASE
# =========================================================

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================================================
# NORMALIZE CODE
# =========================================================

def normalize_code(value):
    if value is None:
        return ""

    value = str(value)

    value = value.strip().upper()

    value = value.replace(" ", "")
    value = value.replace("_", "-")

    return value


# =========================================================
# NORMALIZE TEXT
# =========================================================

def normalize_text(value):
    if value is None:
        return ""

    return str(value).strip().lower()


# =========================================================
# LOAD ALL DATABASE ROWS
# =========================================================

def load_all_videos():

    all_rows = []

    page_size = 1000
    start = 0

    while True:

        logger.info(
            "Loading database rows %s - %s",
            start,
            start + page_size - 1
        )

        response = (
            supabase
            .table("videos")
            .select("*")
            .range(
                start,
                start + page_size - 1
            )
            .execute()
        )

        rows = response.data or []

        if not rows:
            break

        all_rows.extend(rows)

        if len(rows) < page_size:
            break

        start += page_size

    logger.info(
        "TOTAL DATABASE ROWS: %s",
        len(all_rows)
    )

    return all_rows


# =========================================================
# SEARCH DATABASE
# =========================================================

def search_database(search):

    search = str(search).strip()

    if not search:
        return []

    normalized_search = normalize_code(search)
    lower_search = search.lower()

    rows = load_all_videos()

    exact_results = []
    code_results = []
    text_results = []

    for row in rows:

        code = normalize_code(
            row.get("code")
        )

        name = normalize_text(
            row.get("name")
        )

        description = normalize_text(
            row.get("description")
        )

        # ---------------------------------------------
        # EXACT CODE
        # ---------------------------------------------

        if code == normalized_search:

            exact_results.append(row)

            continue

        # ---------------------------------------------
        # PARTIAL CODE
        # ---------------------------------------------

        if normalized_search and normalized_search in code:

            code_results.append(row)

            continue

        # ---------------------------------------------
        # NAME
        # ---------------------------------------------

        if lower_search in name:

            text_results.append(row)

            continue

        # ---------------------------------------------
        # DESCRIPTION
        # ---------------------------------------------

        if lower_search in description:

            text_results.append(row)

            continue

    if exact_results:
        return exact_results

    if code_results:
        return code_results

    return text_results


# =========================================================
# CHANNEL POST LINK
# =========================================================

def create_post_link(
    channel_id,
    message_id
):

    channel_id = str(channel_id)

    if channel_id.startswith("-100"):

        channel_number = channel_id[4:]

    else:

        channel_number = channel_id.lstrip("-")

    return (
        f"https://t.me/c/"
        f"{channel_number}/"
        f"{message_id}"
    )


# =========================================================
# MEMBERSHIP CHECK
# =========================================================

async def check_membership(
    bot,
    user_id,
    channel_id
):

    try:

        member = await bot.get_chat_member(
            chat_id=int(channel_id),
            user_id=user_id
        )

        return member.status in (
            "member",
            "administrator",
            "creator"
        )

    except Exception as error:

        logger.warning(
            "Membership check failed: %s",
            error
        )

        return False


# =========================================================
# SEND VIDEO RESULT
# =========================================================

async def send_video_result(
    message,
    bot,
    user_id,
    row
):

    db_id = row.get("id")

    channel_id = str(
        row.get("channel_id", "")
    )

    message_id = row.get("message_id")

    code = row.get("code") or "N/A"
    name = row.get("name") or "Untitled"
    description = row.get("description") or ""
    photo = row.get("photo")

    channel = CHANNELS.get(
        channel_id
    )

    if not channel:

        await message.reply_text(
            "❌ Channel configuration नहीं मिला।"
        )

        return

    # -----------------------------------------------------
    # CHECK ACCESS
    # -----------------------------------------------------

    has_access = await check_membership(
        bot,
        user_id,
        channel_id
    )

    # -----------------------------------------------------
    # USER HAS ACCESS
    # -----------------------------------------------------

    if has_access:

        post_link = create_post_link(
            channel_id,
            message_id
        )

        caption = (
            f"🎬 *{name}*\n\n"
            f"🔢 Code: `{code}`\n\n"
            f"📄 {description}"
        )

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📂 Open Post",
                        url=post_link
                    )
                ]
            ]
        )

        if photo:

            try:

                await message.reply_photo(
                    photo=photo,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )

                return

            except Exception as error:

                logger.warning(
                    "Photo send failed: %s",
                    error
                )

        await message.reply_text(
            caption,
            parse_mode="Markdown",
            reply_markup=keyboard
        )

        return

    # -----------------------------------------------------
    # USER DOES NOT HAVE ACCESS
    # -----------------------------------------------------

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💳 Subscribe & Access",
                    callback_data=f"PAY:{db_id}"
                )
            ]
        ]
    )

    await message.reply_text(
        "🔒 *Access Required*\n\n"
        f"🎬 {name}\n"
        f"🔢 Code: `{code}`\n\n"
        f"📢 {channel['name']}\n"
        f"💰 {channel['price']} ⭐ / month",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


# =========================================================
# START
# =========================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = (
        "🔎 *TSB Search Bot*\n\n"
        "Apna Code ya Video Name search karo.\n\n"
        "Examples:\n"
        "`1P-234`\n"
        "`2P-001`\n"
        "`3P-125`\n"
        "`4P-500`"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💬 Support",
                    url=SUPPORT_URL
                )
            ]
        ]
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )


# =========================================================
# HELP
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🔎 Code या Video Name भेजकर search करें।\n\n"
        "Example:\n"
        "1P-234\n"
        "2P-001\n"
        "3P-125\n"
        "4P-500"
    )


# =========================================================
# DATABASE TEST
# =========================================================

async def dbtest_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = str(
        update.effective_user.id
    )

    if not ADMIN_USER_ID:
        return

    if user_id != ADMIN_USER_ID:
        return

    try:

        rows = load_all_videos()

        if not rows:

            await update.message.reply_text(
                "⚠️ Supabase connected.\n\n"
                "videos table में कोई record नहीं मिला।"
            )

            return

        text = (
            "✅ SUPABASE CONNECTED\n\n"
            f"📦 Total records: {len(rows)}\n\n"
            "Records:\n"
        )

        for row in rows[-10:]:

            text += (
                f"\n🔢 Code: {row.get('code')}"
                f"\n🆔 Message ID: {row.get('message_id')}"
                f"\n📢 Channel: {row.get('channel_id')}"
                f"\n"
            )

        await update.message.reply_text(
            text
        )

    except Exception as error:

        logger.exception(
            "DBTEST ERROR"
        )

        await update.message.reply_text(
            "❌ SUPABASE ERROR\n\n"
            f"{type(error).__name__}\n"
            f"{error}"
        )


# =========================================================
# SEARCH HANDLER
# =========================================================

async def search_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    search = update.message.text.strip()

    if not search:
        return

    logger.info(
        "SEARCH REQUEST: %s",
        search
    )

    try:

        results = search_database(
            search
        )

    except Exception as error:

        logger.exception(
            "SEARCH DATABASE ERROR"
        )

        await update.message.reply_text(
            "❌ Database search error.\n\n"
            f"{type(error).__name__}: {error}"
        )

        return

    # -----------------------------------------------------
    # NO RESULT
    # -----------------------------------------------------

    if not results:

        await update.message.reply_text(
            "❌ No result found.\n\n"
            "Example:\n"
            "1P-234\n"
            "2P-001\n"
            "3P-125\n"
            "4P-500"
        )

        return

    # -----------------------------------------------------
    # ONE RESULT
    # -----------------------------------------------------

    if len(results) == 1:

        await send_video_result(
            update.message,
            context.bot,
            update.effective_user.id,
            results[0]
        )

        return

    # -----------------------------------------------------
    # MULTIPLE RESULTS
    # -----------------------------------------------------

    buttons = []

    for row in results[:20]:

        db_id = row.get("id")

        code = row.get("code") or ""
        name = row.get("name") or ""

        label = (
            f"{code} - {name}"
        )

        if len(label) > 60:

            label = (
                label[:57] + "..."
            )

        buttons.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"RESULT:{db_id}"
                )
            ]
        )

    await update.message.reply_text(
        f"🔎 {len(results)} results found.\n\n"
        "अपना result चुनें:",
        reply_markup=InlineKeyboardMarkup(
            buttons
        )
    )


# =========================================================
# CALLBACK HANDLER
# =========================================================

async def callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    data = query.data or ""

    # =====================================================
    # RESULT
    # =====================================================

    if data.startswith("RESULT:"):

        db_id = data.split(
            ":",
            1
        )[1]

        try:

            response = (
                supabase
                .table("videos")
                .select("*")
                .eq("id", db_id)
                .limit(1)
                .execute()
            )

            rows = response.data or []

            if not rows:

                await query.message.reply_text(
                    "❌ Result नहीं मिला।"
                )

                return

            await send_video_result(
                query.message,
                context.bot,
                query.from_user.id,
                rows[0]
            )

        except Exception as error:

            logger.exception(
                "RESULT ERROR"
            )

            await query.message.reply_text(
                "❌ Result error.\n\n"
                f"{type(error).__name__}: {error}"
            )

        return

    # =====================================================
    # PAYMENT
    # =====================================================

    if data.startswith("PAY:"):

        db_id = data.split(
            ":",
            1
        )[1]

        try:

            response = (
                supabase
                .table("videos")
                .select(
                    "channel_id"
                )
                .eq("id", db_id)
                .limit(1)
                .execute()
            )

            rows = response.data or []

            if not rows:

                await query.message.reply_text(
                    "❌ Video record नहीं मिला।"
                )

                return

            channel_id = str(
                rows[0].get(
                    "channel_id",
                    ""
                )
            )

            channel = CHANNELS.get(
                channel_id
            )

            if not channel:

                await query.message.reply_text(
                    "❌ Channel configuration नहीं मिला।"
                )

                return

            try:

                invite = (
                    await context.bot
                    .create_chat_subscription_invite_link(
                        chat_id=int(
                            channel_id
                        ),
                        name=(
                            f"TSB "
                            f"{channel['name']}"
                        ),
                        subscription_period=2592000,
                        subscription_price=channel[
                            "price"
                        ],
                    )
                )

                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "⭐ Pay & Subscribe",
                                url=invite.invite_link
                            )
                        ]
                    ]
                )

                await query.message.reply_text(
                    "💳 *Subscription Access*\n\n"
                    f"📢 {channel['name']}\n"
                    f"💰 {channel['price']} ⭐ / month\n\n"
                    "नीचे payment करके access लें:",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )

            except Exception as error:

                logger.exception(
                    "PAYMENT LINK ERROR"
                )

                await query.message.reply_text(
                    "⚠️ Payment link अभी create नहीं हो पाया।\n\n"
                    "💬 Support से संपर्क करें।"
                )

        except Exception as error:

            logger.exception(
                "PAYMENT ERROR"
            )

            await query.message.reply_text(
                "❌ Payment error."
            )

        return


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.error(
        "BOT ERROR: %s",
        context.error
    )


# =========================================================
# MAIN
# =========================================================

def main():

    logger.info(
        "===================================="
    )

    logger.info(
        "TSB SEARCH BOT STARTING"
    )

    logger.info(
        "Supabase URL: %s",
        SUPABASE_URL
    )

    # -----------------------------------------------------
    # DATABASE STARTUP TEST
    # -----------------------------------------------------

    try:

        response = (
            supabase
            .table("videos")
            .select(
                "id",
                count="exact"
            )
            .limit(1)
            .execute()
        )

        logger.info(
            "SUPABASE OK | ROW COUNT = %s",
            response.count
        )

    except Exception as error:

        logger.exception(
            "SUPABASE STARTUP TEST FAILED"
        )

    # -----------------------------------------------------
    # TELEGRAM APPLICATION
    # -----------------------------------------------------

    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # -----------------------------------------------------
    # COMMANDS
    # -----------------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start_command
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    application.add_handler(
        CommandHandler(
            "dbtest",
            dbtest_command
        )
    )

    # -----------------------------------------------------
    # CALLBACKS
    # -----------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            search_handler
        )
    )

    application.add_error_handler(
        error_handler
    )

    logger.info(
        "BOT POLLING STARTING..."
    )

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
