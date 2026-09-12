import os
import re
import logging

from supabase import create_client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# =========================
# SETTINGS
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

CHANNELS = {
    -1004338671388: {"prefix": "1", "price": 299},
    -1004490954138: {"prefix": "2", "price": 299},
    -1003963263624: {"prefix": "3", "price": 299},
    -1003472229143: {"prefix": "4", "price": 299},
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# SUPABASE
# =========================

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase settings missing.")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================
# CODE
# =========================

def extract_code(text):
    if not text:
        return None

    match = re.search(
        r"\b([1-4]P-[A-Za-z0-9_-]+)\b",
        text,
        re.I
    )

    if match:
        return match.group(1).upper()

    return None


# =========================
# POST LINK
# =========================

def make_post_link(chat_id, message_id):
    return (
        "https://t.me/c/"
        + str(chat_id).replace("-100", "", 1)
        + "/"
        + str(message_id)
    )


# =========================
# SAVE VIDEO
# =========================

async def index_channel_post(message):

    chat_id = message.chat.id

    if chat_id not in CHANNELS:
        return

    text = (
        message.text
        or message.caption
        or ""
    ).strip()

    code = extract_code(text)

    if not code:
        return

    prefix = CHANNELS[chat_id]["prefix"]

    if not code.startswith(prefix + "P-"):
        return

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    name = ""
    description = ""

    for line in lines:

        low = line.lower()

        if (
            "🎬" in line
            or low.startswith("name:")
            or low.startswith("title:")
        ):
            name = re.sub(
                r"^(🎬\s*|name\s*:\s*|title\s*:\s*)",
                "",
                line,
                flags=re.I
            ).strip()

        elif (
            "📝" in line
            or low.startswith("description:")
            or low.startswith("desc:")
        ):
            description = re.sub(
                r"^(📝\s*|description\s*:\s*|desc\s*:\s*)",
                "",
                line,
                flags=re.I
            ).strip()

    if not name:

        for line in lines:

            if (
                line.upper() != code
                and not line.startswith("🔗")
                and not line.startswith("http")
            ):
                name = line
                break

    photo = None

    if message.photo:
        photo = message.photo[-1].file_id

    data = {
        "code": code,
        "channel_id": str(chat_id),
        "message_id": str(message.message_id),
        "name": name or "Video",
        "description": description or "No description available.",
        "photo": photo,
    }

    try:

        supabase.table("videos").upsert(
            data,
            on_conflict="code"
        ).execute()

        logger.info(
            "Saved permanently: %s",
            code
        )

    except Exception as e:

        logger.error(
            "Supabase save error: %s",
            e
        )


# =========================
# CHANNEL POSTS
# =========================

async def channel_post_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.channel_post:

        await index_channel_post(
            update.channel_post
        )


# =========================
# MEMBER CHECK
# =========================

async def is_member(
    bot,
    user_id,
    channel_id
):

    try:

        member = await bot.get_chat_member(
            channel_id,
            user_id
        )

        if member.status in (
            "creator",
            "administrator",
            "member"
        ):
            return True

        if member.status == "restricted":

            return bool(
                getattr(
                    member,
                    "is_member",
                    False
                )
            )

    except Exception as e:

        logger.warning(
            "Membership check failed: %s",
            e
        )

    return False


# =========================
# PAYMENT LINK
# =========================

async def create_paid_link(
    bot,
    channel_id
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


# =========================
# START
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🔎 TSB Search Bot\n\n"
        "Apna Code ya Video Name search karo.\n\n"
        "Examples:\n"
        "1P-234\n"
        "2P-001\n"
        "3P-125\n"
        "4P-500"
    )


# =========================
# SEARCH DATABASE
# =========================

def search_items(query):

    q = query.strip()

    if not q:
        return []

    try:

        response = (
            supabase
            .table("videos")
            .select("*")
            .ilike("code", f"%{q}%")
            .limit(10)
            .execute()
        )

        results = response.data or []

        if results:
            return results

        response = (
            supabase
            .table("videos")
            .select("*")
            .or_(
                f"name.ilike.%{q}%,"
                f"description.ilike.%{q}%"
            )
            .limit(10)
            .execute()
        )

        return response.data or []

    except Exception as e:

        logger.error(
            "Search error: %s",
            e
        )

        return []


# =========================
# SEND RESULT
# =========================

async def send_result(
    message,
    bot,
    user_id,
    item
):

    channel_id = int(
        item["channel_id"]
    )

    if await is_member(
        bot,
        user_id,
        channel_id
    ):

        await send_open_post(
            message,
            item
        )

        return

    try:

        paid_link = await create_paid_link(
            bot,
            channel_id
        )

    except Exception as e:

        logger.error(
            "Payment link error: %s",
            e
        )

        await message.reply_text(
            "❌ Payment link create nahi ho saka.\n\n"
            "Bot ko channel me Invite Users permission chahiye."
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

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "💳 Subscribe & Access",
                url=paid_link
            )
        ]
    ])

    await message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


# =========================
# OPEN POST
# =========================

async def send_open_post(
    message,
    item
):

    post_link = make_post_link(
        int(item["channel_id"]),
        int(item["message_id"])
    )

    caption = (
        f"🏷️ <b>{item['code']}</b>\n\n"
        f"🎬 <b>{item.get('name') or 'Video'}</b>\n\n"
        f"📝 {item.get('description') or 'No description available.'}"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📂 Open Post",
                url=post_link
            )
        ]
    ])

    if item.get("photo"):

        try:

            await message.reply_photo(
                photo=item["photo"],
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )

            return

        except Exception as e:

            logger.warning(
                "Photo send failed: %s",
                e
            )

    await message.reply_text(
        caption,
        parse_mode="HTML",
        reply_markup=keyboard
    )


# =========================
# SEARCH HANDLER
# =========================

async def search_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
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

    results = search_items(query)

    if not results:

        await update.message.reply_text(
            "❌ No result found.\n\n"
            "Example:\n"
            "1P-234\n"
            "2P-001"
        )

        return

    if len(results) == 1:

        await send_result(
            update.message,
            context.bot,
            update.effective_user.id,
            results[0]
        )

        return

    buttons = []

    for item in results:

        label = (
            f"📂 {item['code']} — "
            f"{item.get('name') or 'Video'}"
        )

        buttons.append([
            InlineKeyboardButton(
                label[:60],
                callback_data=f"open:{item['code']}"
            )
        ])

    await update.message.reply_text(
        f"🔎 {len(results)} results found:",
        reply_markup=InlineKeyboardMarkup(
            buttons
        )
    )


# =========================
# BUTTON
# =========================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    code = (
        query.data
        .split("open:", 1)[1]
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

    except Exception as e:

        logger.error(
            "Database error: %s",
            e
        )

        results = []

    if not results:

        await query.message.reply_text(
            "❌ Result available nahi hai."
        )

        return

    await send_result(
        query.message,
        context.bot,
        query.from_user.id,
        results[0]
    )


# =========================
# ERROR
# =========================

async def error_handler(
    update,
    context
):

    logger.exception(
        "Telegram error: %s",
        context.error
    )


# =========================
# MAIN
# =========================

def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN set nahi hai."
        )

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "help",
            start
        )
    )

    app.add_handler(
        MessageHandler(
            filters.UpdateType.CHANNEL_POST,
            channel_post_handler
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern=r"^open:"
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            search_handler
        )
    )

    app.add_error_handler(
        error_handler
    )

    print(
        "TSB Search Bot is running..."
    )

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
