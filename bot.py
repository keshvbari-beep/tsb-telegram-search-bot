import os
import re
import html
import logging

from supabase import create_client

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

SUPPORT_URL = "https://t.me/RajanChauhan_club"


# =========================================================
# CHANNEL CONFIG
# =========================================================

CHANNELS = {
    -1004338671388: {
        "name": "Channel 1",
        "prefix": "1P",
        "price": 299,
    },

    -1004490954138: {
        "name": "Channel 2",
        "prefix": "2P",
        "price": 299,
    },

    -1003963263624: {
        "name": "Channel 3",
        "prefix": "3P",
        "price": 299,
    },

    -1003472229143: {
        "name": "Channel 4",
        "prefix": "4P",
        "price": 299,
    },
}


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("TSB_SEARCH_BOT")


# =========================================================
# ENV CHECK
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

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)


# =========================================================
# CODE NORMALIZATION
# =========================================================

def normalize_code(value):
    """
    Converts codes into a common format.

    Examples:
        1P-555  -> 1P555
        1p-555  -> 1P555
        1P 555  -> 1P555
        1P_555  -> 1P555
    """

    if value is None:
        return ""

    value = str(value).upper().strip()

    # Remove all spaces
    value = re.sub(r"\s+", "", value)

    # Remove separators
    value = value.replace("-", "")
    value = value.replace("_", "")

    return value


# =========================================================
# DISPLAY CODE
# =========================================================

def clean_display_code(value):
    if not value:
        return "Unknown"

    return str(value).strip()


# =========================================================
# EXTRACT CODE FROM SEARCH
# =========================================================

def extract_code(text):

    if not text:
        return None

    text = str(text).strip().upper()

    # Remove spaces around hyphen
    text = re.sub(
        r"\s*-\s*",
        "-",
        text,
    )

    # Direct format
    match = re.fullmatch(
        r"[1-4]P-[A-Z0-9]+",
        text,
    )

    if match:
        return match.group(0)

    # Without hyphen
    match = re.fullmatch(
        r"[1-4]P[A-Z0-9]+",
        text,
    )

    if match:
        value = match.group(0)

        return (
            value[:2]
            + "-"
            + value[2:]
        )

    # Code inside text
    match = re.search(
        r"\b([1-4]P)\s*[-_]?\s*([A-Z0-9]+)\b",
        text,
    )

    if match:

        return (
            match.group(1)
            + "-"
            + match.group(2)
        )

    return None


# =========================================================
# TELEGRAM POST LINK
# =========================================================

def make_post_link(
    channel_id,
    message_id,
):

    channel_id = str(channel_id)
    message_id = str(message_id)

    if channel_id.startswith("-100"):
        channel_id = channel_id[4:]

    return (
        f"https://t.me/c/{channel_id}/{message_id}"
    )


# =========================================================
# LOAD DATABASE
# =========================================================

def load_all_videos():

    all_rows = []

    page_size = 1000
    start = 0

    while True:

        end = start + page_size - 1

        logger.info(
            "Loading database rows %s - %s",
            start,
            end,
        )

        response = (
            supabase
            .table("videos")
            .select(
                "id,created_at,code,channel_id,"
                "message_id,name,description,photo"
            )
            .range(start, end)
            .execute()
        )

        rows = response.data or []

        all_rows.extend(rows)

        if len(rows) < page_size:
            break

        start += page_size

    logger.info(
        "Total database rows loaded: %s",
        len(all_rows),
    )

    return all_rows


# =========================================================
# SEARCH DATABASE
# =========================================================

def search_items(search_text):

    search_text = str(
        search_text or ""
    ).strip()

    if not search_text:
        return []

    logger.info(
        "===================================="
    )

    logger.info(
        "SEARCH: %s",
        search_text,
    )

    # =====================================================
    # LOAD ALL RECORDS
    # =====================================================

    rows = load_all_videos()

    if not rows:

        logger.warning(
            "No rows found in videos table"
        )

        return []

    # =====================================================
    # 1. EXACT NORMALIZED CODE SEARCH
    # =====================================================

    requested_code = extract_code(
        search_text
    )

    if requested_code:

        wanted_code = normalize_code(
            requested_code
        )

        logger.info(
            "Normalized search code: %s",
            wanted_code,
        )

        exact_results = []

        for row in rows:

            saved_code = normalize_code(
                row.get("code")
            )

            if saved_code == wanted_code:

                exact_results.append(row)

                logger.info(
                    "CODE MATCH: %s | message=%s",
                    row.get("code"),
                    row.get("message_id"),
                )

        if exact_results:

            logger.info(
                "Exact code results: %s",
                len(exact_results),
            )

            return exact_results

    # =====================================================
    # 2. PARTIAL NORMALIZED CODE SEARCH
    # =====================================================

    normalized_query = normalize_code(
        search_text
    )

    if normalized_query:

        partial_results = []

        for row in rows:

            saved_code = normalize_code(
                row.get("code")
            )

            if (
                normalized_query
                in saved_code
            ):

                partial_results.append(row)

        if partial_results:

            logger.info(
                "Partial code results: %s",
                len(partial_results),
            )

            return partial_results

    # =====================================================
    # 3. NAME SEARCH
    # =====================================================

    query_lower = search_text.lower()

    name_results = []

    for row in rows:

        name = str(
            row.get("name") or ""
        ).lower()

        if query_lower in name:

            name_results.append(row)

    if name_results:

        logger.info(
            "Name results: %s",
            len(name_results),
        )

        return name_results

    # =====================================================
    # 4. DESCRIPTION SEARCH
    # =====================================================

    description_results = []

    for row in rows:

        description = str(
            row.get("description") or ""
        ).lower()

        if query_lower in description:

            description_results.append(row)

    if description_results:

        logger.info(
            "Description results: %s",
            len(description_results),
        )

        return description_results

    # =====================================================
    # NO RESULT
    # =====================================================

    logger.info(
        "NO RESULT FOUND"
    )

    return []


# =========================================================
# START COMMAND
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    await update.message.reply_text(
        "🔎 TSB video Search\n\n"
        "Apna Code ya Video Name search karo.\n\n"
        "Example:\n"
        "1P-234\n"
        "2P-001\n"
        "3P-125\n"
        "4P-500"
    )


# =========================================================
# HELP COMMAND
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    await update.message.reply_text(
        "🔎 TSB video Search\n\n"
        "Video Code ya Name bhejo.\n\n"
        "Example:\n"
        "1P-234\n"
        "2P-001\n"
        "3P-125\n"
        "4P-500"
    )


# =========================================================
# CHECK MEMBERSHIP
# =========================================================

async def is_member(
    bot,
    user_id,
    channel_id,
):

    try:

        member = await bot.get_chat_member(
            chat_id=channel_id,
            user_id=user_id,
        )

        if member.status in (
            "creator",
            "administrator",
            "member",
        ):
            return True

        if member.status == "restricted":

            return bool(
                getattr(
                    member,
                    "is_member",
                    False,
                )
            )

        return False

    except Exception as e:

        logger.warning(
            "Membership check failed: %s",
            e,
        )

        return False


# =========================================================
# CREATE SUBSCRIPTION LINK
# =========================================================

async def create_paid_link(
    bot,
    channel_id,
):

    channel = CHANNELS.get(
        channel_id
    )

    if not channel:
        raise ValueError(
            "Unknown channel"
        )

    result = (
        await bot.create_chat_subscription_invite_link(
            chat_id=channel_id,
            name=(
                f"TSB {channel['name']}"
            ),
            subscription_period=2592000,
            subscription_price=channel["price"],
        )
    )

    return result.invite_link


# =========================================================
# SEND OPEN POST
# =========================================================

async def send_open_post(
    message,
    item,
):

    try:

        channel_id = int(
            item.get("channel_id")
        )

        message_id = int(
            item.get("message_id")
        )

    except Exception:

        logger.exception(
            "Invalid channel/message data"
        )

        await message.reply_text(
            "❌ Post information invalid hai."
        )

        return

    # =====================================================
    # POST LINK
    # =====================================================

    post_link = make_post_link(
        channel_id,
        message_id,
    )

    # =====================================================
    # DATA
    # =====================================================

    code = html.escape(
        clean_display_code(
            item.get("code")
        )
    )

    name = html.escape(
        str(
            item.get("name")
            or "Video"
        ).strip()
    )

    description = html.escape(
        str(
            item.get("description")
            or "No description available."
        ).strip()
    )

    caption = (
        f"🏷️ <b>{code}</b>\n\n"
        f"🎬 <b>{name}</b>\n\n"
        f"📝 {description}"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📂 Open Post",
                    url=post_link,
                )
            ]
        ]
    )

    # =====================================================
    # PHOTO
    # =====================================================

    photo = item.get("photo")

    if photo:

        try:

            await message.reply_photo(
                photo=photo,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )

            return

        except Exception as e:

            logger.warning(
                "Photo send failed: %s",
                e,
            )

    # =====================================================
    # TEXT FALLBACK
    # =====================================================

    await message.reply_text(
        caption,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# =========================================================
# SEND RESULT
# =========================================================

async def send_result(
    message,
    bot,
    user_id,
    item,
):

    try:

        channel_id = int(
            item.get("channel_id")
        )

    except Exception:

        await message.reply_text(
            "❌ Channel information invalid hai."
        )

        return

    # =====================================================
    # CHECK CHANNEL
    # =====================================================

    channel = CHANNELS.get(
        channel_id
    )

    if not channel:

        logger.error(
            "Unknown channel ID: %s",
            channel_id,
        )

        await message.reply_text(
            "❌ Channel configured nahi hai."
        )

        return

    # =====================================================
    # MEMBER CHECK
    # =====================================================

    member = await is_member(
        bot,
        user_id,
        channel_id,
    )

    if member:

        await send_open_post(
            message,
            item,
        )

        return

    # =====================================================
    # PAYMENT
    # =====================================================

    try:

        paid_link = await create_paid_link(
            bot,
            channel_id,
        )

    except Exception as e:

        logger.exception(
            "Subscription link error: %s",
            e,
        )

        await message.reply_text(
            "❌ Subscription link create nahi ho saka.\n\n"
            "Please try again later."
        )

        return

    text = (
        "🔒 <b>Premium Access Required</b>\n\n"
        f"Ye video <b>{channel['name']}</b> me hai.\n\n"
        f"💰 Monthly Access: "
        f"<b>{channel['price']} Stars</b>\n\n"
        "Payment ke baad channel access mil jayega."
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💳 Subscribe & Access",
                    url=paid_link,
                )
            ],
            [
                InlineKeyboardButton(
                    "💬 Support",
                    url=SUPPORT_URL,
                )
            ],
        ]
    )

    await message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# =========================================================
# SEARCH MESSAGE
# =========================================================

async def search_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    search_text = (
        update.message.text
        or ""
    ).strip()

    if len(search_text) < 2:

        await update.message.reply_text(
            "🔎 Code ya Video Name bhejo."
        )

        return

    try:

        results = search_items(
            search_text
        )

    except Exception as e:

        logger.exception(
            "DATABASE SEARCH ERROR"
        )

        await update.message.reply_text(
            "⚠️ Database search error.\n\n"
            "Please try again."
        )

        return

    # =====================================================
    # NO RESULT
    # =====================================================

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

    # =====================================================
    # ONE RESULT
    # =====================================================

    if len(results) == 1:

        await send_result(
            update.message,
            context.bot,
            update.effective_user.id,
            results[0],
        )

        return

    # =====================================================
    # MULTIPLE RESULTS
    # =====================================================

    buttons = []

    for index, item in enumerate(
        results
    ):

        code = clean_display_code(
            item.get("code")
        )

        name = str(
            item.get("name")
            or "Video"
        ).strip()

        # Callback uses database ID.
        # This is safer than putting the code
        # into callback_data.
        row_id = str(
            item.get("id")
            or ""
        )

        if not row_id:
            continue

        label = (
            f"📂 {code} — {name}"
        )

        buttons.append(
            [
                InlineKeyboardButton(
                    label[:60],
                    callback_data=(
                        f"video:{row_id}"
                    ),
                )
            ]
        )

    if not buttons:

        await update.message.reply_text(
            "❌ Result information invalid hai."
        )

        return

    await update.message.reply_text(
        f"🔎 {len(buttons)} results found:",
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )


# =========================================================
# MULTIPLE RESULT BUTTON
# =========================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if not query:
        return

    await query.answer()

    data = query.data or ""

    if not data.startswith(
        "video:"
    ):
        return

    row_id = data.split(
        "video:",
        1,
    )[1]

    logger.info(
        "Selected database ID: %s",
        row_id,
    )

    # =====================================================
    # FIND EXACT DATABASE ROW
    # =====================================================

    try:

        response = (
            supabase
            .table("videos")
            .select("*")
            .eq("id", row_id)
            .limit(1)
            .execute()
        )

        rows = response.data or []

    except Exception:

        logger.exception(
            "BUTTON DATABASE ERROR"
        )

        await query.message.reply_text(
            "⚠️ Database error."
        )

        return

    if not rows:

        await query.message.reply_text(
            "❌ Result available nahi hai."
        )

        return

    # =====================================================
    # SEND EXACT ROW
    # =====================================================

    await send_result(
        query.message,
        context.bot,
        query.from_user.id,
        rows[0],
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update,
    context,
):

    logger.error(
        "Telegram error: %s",
        context.error,
    )


# =========================================================
# MAIN
# =========================================================

def main():

    logger.info(
        "========================================"
    )

    logger.info(
        "TSB VIDEO SEARCH BOT STARTING"
    )

    logger.info(
        "========================================"
    )

    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # =====================================================
    # COMMANDS
    # =====================================================

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

    # =====================================================
    # RESULT BUTTON
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern=r"^video:",
        )
    )

    # =====================================================
    # SEARCH
    # =====================================================

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            search_handler,
        )
    )

    # =====================================================
    # ERROR
    # =====================================================

    application.add_error_handler(
        error_handler
    )

    # =====================================================
    # START POLLING
    # =====================================================

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
