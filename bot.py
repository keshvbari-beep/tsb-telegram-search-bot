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
# SETTINGS
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


# =========================================================
# CHANNELS
# =========================================================

CHANNELS = {
    -1004338671388: {
        "prefix": "1",
        "price": 299,
    },

    -1004490954138: {
        "prefix": "2",
        "price": 299,
    },

    -1003963263624: {
        "prefix": "3",
        "price": 299,
    },

    -1003472229143: {
        "prefix": "4",
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

logger = logging.getLogger(__name__)


# =========================================================
# CHECK SETTINGS
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL missing")

if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_KEY missing")


# =========================================================
# SUPABASE
# =========================================================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)


# =========================================================
# LINKS
# =========================================================

SUPPORT_URL = "https://t.me/RajanChauhan_club"

SEARCH_BOT_URL = "https://t.me/TSB_Video_Search_Bot"


# =========================================================
# NORMALIZE CODE
# =========================================================

def normalize_code(value):

    if value is None:
        return ""

    value = str(value).strip().upper()

    # Remove all spaces
    value = re.sub(
        r"\s+",
        "",
        value,
    )

    # Make hyphen format consistent
    value = value.replace("_", "-")

    return value


# =========================================================
# EXTRACT CODE
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

    # Direct exact code
    match = re.fullmatch(
        r"[1-4]P-[A-Z0-9_-]+",
        text,
        re.IGNORECASE,
    )

    if match:
        return normalize_code(text)

    # Code inside a sentence
    match = re.search(
        r"\b([1-4]P)\s*-\s*([A-Z0-9_-]+)\b",
        text,
        re.IGNORECASE,
    )

    if match:
        return normalize_code(
            f"{match.group(1)}-{match.group(2)}"
        )

    return None


# =========================================================
# TELEGRAM POST LINK
# =========================================================

def make_post_link(
    channel_id,
    message_id,
):

    clean_id = str(channel_id)

    if clean_id.startswith("-100"):
        clean_id = clean_id[4:]

    return (
        f"https://t.me/c/{clean_id}/{message_id}"
    )


# =========================================================
# LOAD ALL DATABASE ROWS
# =========================================================

def load_all_videos():

    all_rows = []

    page_size = 1000
    start = 0

    while True:

        end = start + page_size - 1

        logger.info(
            "Loading database rows %s-%s",
            start,
            end,
        )

        response = (
            supabase
            .table("videos")
            .select("*")
            .range(start, end)
            .execute()
        )

        rows = response.data or []

        all_rows.extend(rows)

        logger.info(
            "Loaded %s rows",
            len(rows),
        )

        if len(rows) < page_size:
            break

        start += page_size

    logger.info(
        "TOTAL DATABASE ROWS: %s",
        len(all_rows),
    )

    return all_rows


# =========================================================
# DATABASE SEARCH
# =========================================================

def search_items(query):

    query = str(query).strip()

    if not query:
        return []

    # Load all saved videos
    rows = load_all_videos()

    if not rows:
        logger.info(
            "DATABASE IS EMPTY"
        )
        return []

    # =====================================================
    # CODE SEARCH
    # =====================================================

    requested_code = extract_code(query)

    logger.info(
        "SEARCH QUERY: %s",
        query,
    )

    logger.info(
        "REQUESTED CODE: %s",
        requested_code,
    )

    if requested_code:

        wanted = normalize_code(
            requested_code
        )

        matched = []

        for row in rows:

            saved_code = normalize_code(
                row.get("code")
            )

            if saved_code == wanted:
                matched.append(row)

        logger.info(
            "CODE MATCHES: %s",
            len(matched),
        )

        if matched:
            return matched

    # =====================================================
    # NAME SEARCH
    # =====================================================

    search_text = query.lower()

    name_results = []

    for row in rows:

        name = str(
            row.get("name") or ""
        ).lower()

        if search_text in name:
            name_results.append(row)

    if name_results:

        logger.info(
            "NAME MATCHES: %s",
            len(name_results),
        )

        return name_results

    # =====================================================
    # DESCRIPTION SEARCH
    # =====================================================

    description_results = []

    for row in rows:

        description = str(
            row.get("description") or ""
        ).lower()

        if search_text in description:
            description_results.append(row)

    logger.info(
        "DESCRIPTION MATCHES: %s",
        len(description_results),
    )

    return description_results


# =========================================================
# START
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
# CHECK CHANNEL MEMBERSHIP
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

    except Exception as e:

        logger.warning(
            "MEMBERSHIP CHECK ERROR: %s",
            e,
        )

    return False


# =========================================================
# CREATE PAYMENT LINK
# =========================================================

async def create_paid_link(
    bot,
    channel_id,
):

    channel = CHANNELS[channel_id]

    result = (
        await bot.create_chat_subscription_invite_link(
            chat_id=channel_id,
            name=f"TSB Channel {channel['prefix']}",
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
            item["channel_id"]
        )

        message_id = int(
            item["message_id"]
        )

    except Exception:

        logger.exception(
            "INVALID POST DATA: %s",
            item,
        )

        await message.reply_text(
            "❌ Post information गलत है."
        )

        return

    # =====================================================
    # EXACT TELEGRAM POST
    # =====================================================

    post_link = make_post_link(
        channel_id,
        message_id,
    )

    code = html.escape(
        str(
            item.get("code")
            or "Unknown"
        )
    )

    name = html.escape(
        str(
            item.get("name")
            or "Video"
        )
    )

    description = html.escape(
        str(
            item.get("description")
            or "No description available."
        )
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
    # PHOTO RESULT
    # =====================================================

    if item.get("photo"):

        try:

            await message.reply_photo(
                photo=item["photo"],
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )

            return

        except Exception as e:

            logger.warning(
                "PHOTO SEND ERROR: %s",
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
            item["channel_id"]
        )

    except Exception:

        await message.reply_text(
            "❌ Channel information गलत है."
        )

        return

    # =====================================================
    # CHANNEL VALIDATION
    # =====================================================

    if channel_id not in CHANNELS:

        logger.error(
            "UNKNOWN CHANNEL ID: %s",
            channel_id,
        )

        await message.reply_text(
            "❌ Channel configured नहीं है."
        )

        return

    # =====================================================
    # CHECK USER ACCESS
    # =====================================================

    if await is_member(
        bot,
        user_id,
        channel_id,
    ):

        await send_open_post(
            message,
            item,
        )

        return

    # =====================================================
    # PAYMENT LINK
    # =====================================================

    try:

        paid_link = await create_paid_link(
            bot,
            channel_id,
        )

    except Exception as e:

        logger.exception(
            "PAYMENT LINK ERROR: %s",
            e,
        )

        await message.reply_text(
            "❌ Payment link create nahi ho saka.\n\n"
            "Please try again later."
        )

        return

    prefix = CHANNELS[channel_id]["prefix"]

    price = CHANNELS[channel_id]["price"]

    text = (
        "🔒 <b>Premium Access Required</b>\n\n"
        f"Ye video Channel {prefix} me hai.\n\n"
        f"💰 Monthly Access: <b>{price} Stars</b>\n\n"
        "Payment ke baad Telegram automatically "
        "channel access dega."
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
# SEARCH HANDLER
# =========================================================

async def search_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    query = (
        update.message.text
        or ""
    ).strip()

    if len(query) < 2:

        await update.message.reply_text(
            "🔎 Code ya video name type karo."
        )

        return

    logger.info(
        "USER SEARCH: %s",
        query,
    )

    # =====================================================
    # SEARCH DATABASE
    # =====================================================

    try:

        results = search_items(
            query
        )

    except Exception as e:

        logger.exception(
            "SEARCH DATABASE ERROR: %s",
            e,
        )

        await update.message.reply_text(
            "⚠️ Database search error.\n\n"
            "Please try again later."
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

    for index, item in enumerate(results):

        code = str(
            item.get("code")
            or "Unknown"
        )

        name = str(
            item.get("name")
            or "Video"
        )

        label = (
            f"📂 {code} — {name}"
        )

        # Telegram callback data limit
        # Keep callback short.
        callback_code = normalize_code(
            code
        )

        if len(callback_code) > 50:
            callback_code = callback_code[:50]

        buttons.append(
            [
                InlineKeyboardButton(
                    label[:60],
                    callback_data=(
                        f"open:{callback_code}"
                    ),
                )
            ]
        )

    await update.message.reply_text(
        f"🔎 {len(results)} results found:",
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )


# =========================================================
# RESULT BUTTON
# =========================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    if not query.data:
        return

    code = (
        query.data
        .split(
            "open:",
            1,
        )[1]
    )

    code = normalize_code(
        code
    )

    logger.info(
        "BUTTON CODE: %s",
        code,
    )

    # =====================================================
    # LOAD DATABASE
    # =====================================================

    try:

        rows = load_all_videos()

    except Exception:

        logger.exception(
            "BUTTON DATABASE ERROR"
        )

        await query.message.reply_text(
            "⚠️ Database error. Please try again later."
        )

        return

    # =====================================================
    # FIND EXACT ROW
    # =====================================================

    results = []

    for row in rows:

        saved_code = normalize_code(
            row.get("code")
        )

        if saved_code == code:

            results.append(row)

    if not results:

        await query.message.reply_text(
            "❌ Result available nahi hai."
        )

        return

    # =====================================================
    # OPEN FIRST EXACT MATCH
    # =====================================================

    await send_result(
        query.message,
        context.bot,
        query.from_user.id,
        results[0],
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update,
    context,
):

    logger.exception(
        "TELEGRAM ERROR: %s",
        context.error,
    )


# =========================================================
# MAIN
# =========================================================

def main():

    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # =====================================================
    # START
    # =====================================================

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    # =====================================================
    # HELP
    # =====================================================

    application.add_handler(
        CommandHandler(
            "help",
            start,
        )
    )

    # =====================================================
    # RESULT BUTTON
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern=r"^open:",
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

    logger.info(
        "======================================"
    )

    logger.info(
        "TSB VIDEO SEARCH BOT STARTED"
    )

    logger.info(
        "SUPABASE URL: %s",
        SUPABASE_URL,
    )

    logger.info(
        "======================================"
    )

    # =====================================================
    # RUN
    # =====================================================

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# START PROGRAM
# =========================================================

if __name__ == "__main__":
    main()
