import os
import re
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
# CODE EXTRACTION
# =========================================================

def extract_code(text):

    if not text:
        return None

    text = text.strip()

    match = re.search(
        r"(?:^|\s)([1-4]P-[A-Za-z0-9_-]+)(?:\s|$)",
        text,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).upper()

    match = re.search(
        r"([1-4]P-[A-Za-z0-9_-]+)",
        text,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).upper()

    return None


# =========================================================
# POST LINK
# =========================================================

def make_post_link(channel_id, message_id):

    clean_id = str(channel_id)

    if clean_id.startswith("-100"):
        clean_id = clean_id[4:]

    return f"https://t.me/c/{clean_id}/{message_id}"


# =========================================================
# DATABASE SEARCH
# =========================================================

def search_items(query):

    query = query.strip()

    if not query:
        return []

    try:

        code = extract_code(query)

        logger.info("SEARCH QUERY: %s", query)
        logger.info("EXTRACTED CODE: %s", code)

        # =================================================
        # DATABASE CONNECTION TEST
        # =================================================

        test = (
            supabase
            .table("videos")
            .select("id,code,name")
            .limit(5)
            .execute()
        )

        logger.info(
            "DATABASE TEST SUCCESS: %s",
            test.data
        )

        # =================================================
        # EXACT CODE SEARCH
        # =================================================

        if code:

            logger.info(
                "EXACT CODE SEARCH: %s",
                code
            )

            response = (
                supabase
                .table("videos")
                .select("*")
                .eq("code", code)
                .limit(10)
                .execute()
            )

            logger.info(
                "EXACT SEARCH RESULT: %s",
                response.data
            )

            if response.data:
                return response.data

        # =================================================
        # PARTIAL CODE SEARCH
        # =================================================

        response = (
            supabase
            .table("videos")
            .select("*")
            .ilike(
                "code",
                f"%{query}%"
            )
            .limit(10)
            .execute()
        )

        logger.info(
            "PARTIAL CODE RESULT: %s",
            response.data
        )

        if response.data:
            return response.data

        # =================================================
        # NAME SEARCH
        # =================================================

        response = (
            supabase
            .table("videos")
            .select("*")
            .ilike(
                "name",
                f"%{query}%"
            )
            .limit(10)
            .execute()
        )

        logger.info(
            "NAME SEARCH RESULT: %s",
            response.data
        )

        if response.data:
            return response.data

        # =================================================
        # DESCRIPTION SEARCH
        # =================================================

        response = (
            supabase
            .table("videos")
            .select("*")
            .ilike(
                "description",
                f"%{query}%"
            )
            .limit(10)
            .execute()
        )

        logger.info(
            "DESCRIPTION SEARCH RESULT: %s",
            response.data
        )

        return response.data or []

    except Exception as e:

        logger.exception(
            "DATABASE SEARCH ERROR: %s",
            e
        )

        # IMPORTANT:
        # Error ko hide nahi karna.
        # GitHub Actions log me exact error dikhega.
        raise


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
# MEMBER CHECK
# =========================================================

async def is_member(
    bot,
    user_id,
    channel_id,
):

    try:

        member = await bot.get_chat_member(
            channel_id,
            user_id,
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
            "Membership check error: %s",
            e,
        )

    return False


# =========================================================
# PAYMENT LINK
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
# OPEN POST
# =========================================================

async def send_open_post(
    message,
    item,
):

    channel_id = int(
        item["channel_id"]
    )

    message_id = int(
        item["message_id"]
    )

    post_link = make_post_link(
        channel_id,
        message_id,
    )

    code = (
        item.get("code")
        or "Unknown"
    )

    name = (
        item.get("name")
        or "Video"
    )

    description = (
        item.get("description")
        or "No description available."
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
                "Photo send failed: %s",
                e,
            )

    # =====================================================
    # TEXT RESULT
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
            "❌ Channel information गलत है।"
        )

        return

    if channel_id not in CHANNELS:

        await message.reply_text(
            "❌ Channel configured नहीं है।"
        )

        return

    # =====================================================
    # CHECK ACCESS
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
    # PAYMENT
    # =====================================================

    try:

        paid_link = await create_paid_link(
            bot,
            channel_id,
        )

    except Exception:

        logger.exception(
            "PAYMENT LINK ERROR"
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
    # DATABASE SEARCH
    # =====================================================

    try:

        results = search_items(query)

    except Exception as e:

        logger.exception(
            "SEARCH HANDLER DATABASE ERROR: %s",
            e
        )

        await update.message.reply_text(
            "⚠️ Database connection/search error.\n\n"
            "Admin ko GitHub Actions log check karna hoga."
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

    for item in results:

        code = item.get(
            "code",
            "Unknown",
        )

        name = item.get(
            "name",
            "Video",
        )

        label = (
            f"📂 {code} — {name}"
        )

        buttons.append(
            [
                InlineKeyboardButton(
                    label[:60],
                    callback_data=f"open:{code}",
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

    code = (
        query.data
        .split(
            "open:",
            1,
        )[1]
        .upper()
    )

    try:

        response = (
            supabase
            .table("videos")
            .select("*")
            .eq("code", code)
            .limit(1)
            .execute()
        )

        results = response.data or []

    except Exception:

        logger.exception(
            "BUTTON DATABASE ERROR"
        )

        await query.message.reply_text(
            "⚠️ Database error. Please try again later."
        )

        return

    if not results:

        await query.message.reply_text(
            "❌ Result available nahi hai."
        )

        return

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
        "TSB VIDEO SEARCH BOT STARTED"
    )

    # =====================================================
    # RUN BOT
    # =====================================================

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# START PROGRAM
# =========================================================

if __name__ == "__main__":
    main()
