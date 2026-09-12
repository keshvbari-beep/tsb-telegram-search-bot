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

# =========================
# SETTINGS
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "")

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

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# =========================
# SUPABASE
# =========================

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================
# NORMALIZE
# =========================

def normalize_code(text):
    if not text:
        return ""

    text = str(text).strip().upper()

    text = text.replace(" ", "")
    text = text.replace("_", "-")

    return text


# =========================
# LOAD ALL VIDEOS
# =========================

def load_all_videos():
    all_rows = []
    start = 0
    page_size = 1000

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

    logger.info("Loaded %s videos from Supabase", len(all_rows))

    return all_rows


# =========================
# SEARCH
# =========================

def search_videos(query):
    query = query.strip()

    if not query:
        return []

    normalized_query = normalize_code(query)

    rows = load_all_videos()

    exact = []
    partial = []
    text_matches = []

    for row in rows:

        code = normalize_code(row.get("code", ""))

        name = str(row.get("name", "") or "")
        description = str(row.get("description", "") or "")

        name_lower = name.lower()
        description_lower = description.lower()

        # EXACT CODE
        if code == normalized_query:
            exact.append(row)
            continue

        # PARTIAL CODE
        if normalized_query and normalized_query in code:
            partial.append(row)
            continue

        # NAME / DESCRIPTION
        q_lower = query.lower()

        if q_lower in name_lower or q_lower in description_lower:
            text_matches.append(row)

    if exact:
        return exact

    if partial:
        return partial

    return text_matches


# =========================
# POST LINK
# =========================

def make_post_link(channel_id, message_id):

    channel_id = str(channel_id)

    if channel_id.startswith("-100"):
        public_part = channel_id[4:]
    else:
        public_part = channel_id.lstrip("-")

    return f"https://t.me/c/{public_part}/{message_id}"


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = (
        "🔍 *TSB video Search*\n\n"
        "अपना Video Code या Name भेजें।\n\n"
        "Example:\n"
        "`1P-234`\n"
        "`2P-001`\n"
        "`3P-125`\n"
        "`4P-500`\n\n"
        "आप Video का नाम भी search कर सकते हैं।"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "💬 Support",
                url=SUPPORT_URL
            )
        ]
    ]

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# =========================
# HELP
# =========================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🔍 Search करने के लिए Video Code या Video Name भेजें।\n\n"
        "Example:\n"
        "1P-234\n"
        "2P-001\n"
        "3P-125\n"
        "4P-500"
    )


# =========================
# DB TEST
# =========================

async def dbtest(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = str(update.effective_user.id)

    if ADMIN_USER_ID and user_id != str(ADMIN_USER_ID):
        return

    try:

        rows = load_all_videos()

        if not rows:
            await update.message.reply_text(
                "⚠️ Supabase connected.\n"
                "लेकिन videos table में कोई row नहीं मिली।"
            )
            return

        latest = rows[-10:]

        text = (
            "✅ DATABASE CONNECTION OK\n\n"
            f"📦 Total videos: {len(rows)}\n\n"
            "Latest records:\n"
        )

        for row in latest:
            text += (
                f"\n🔢 {row.get('code')}"
                f"\n🆔 Message: {row.get('message_id')}"
                f"\n📢 Channel: {row.get('channel_id')}\n"
            )

        await update.message.reply_text(text)

    except Exception as e:

        logger.exception("Database test failed")

        await update.message.reply_text(
            "❌ DATABASE ERROR\n\n"
            f"{type(e).__name__}: {e}"
        )


# =========================
# SEND SINGLE RESULT
# =========================

async def send_result(
    update,
    context,
    row
):

    user_id = update.effective_user.id

    channel_id = str(row.get("channel_id"))
    message_id = row.get("message_id")

    code = row.get("code", "Unknown")
    name = row.get("name", "")
    description = row.get("description", "")
    photo = row.get("photo")

    channel_info = CHANNELS.get(channel_id)

    if not channel_info:

        await update.message.reply_text(
            "⚠️ Channel configuration not found."
        )
        return

    # =========================
    # CHECK MEMBERSHIP
    # =========================

    try:

        member = await context.bot.get_chat_member(
            chat_id=int(channel_id),
            user_id=user_id
        )

        status = member.status

        allowed = status in (
            "member",
            "administrator",
            "creator"
        )

    except Exception as e:

        logger.warning(
            "Membership check failed: %s",
            e
        )

        allowed = False

    # =========================
    # USER HAS ACCESS
    # =========================

    if allowed:

        post_link = make_post_link(
            channel_id,
            message_id
        )

        caption = (
            f"🎬 *{name}*\n\n"
            f"🔢 Code: `{code}`\n\n"
            f"📄 {description}"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "📂 Open Post",
                    url=post_link
                )
            ]
        ]

        if photo:

            try:

                await update.message.reply_photo(
                    photo=photo,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(
                        keyboard
                    )
                )

                return

            except Exception as e:

                logger.warning(
                    "Photo send failed: %s",
                    e
                )

        await update.message.reply_text(
            caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

        return

    # =========================
    # NO ACCESS
    # =========================

    keyboard = [
        [
            InlineKeyboardButton(
                "💳 Subscribe & Access",
                callback_data=f"pay:{row.get('id')}"
            )
        ]
    ]

    await update.message.reply_text(
        "🔒 *Access Required*\n\n"
        f"🎬 {name}\n"
        f"🔢 Code: `{code}`\n\n"
        f"📢 {channel_info['name']}\n"
        f"💰 Price: {channel_info['price']} ⭐ / month",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# SEARCH HANDLER
# =========================

async def search_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.message.text.strip()

    if query.startswith("/"):
        return

    try:

        results = search_videos(query)

    except Exception as e:

        logger.exception("Search failed")

        await update.message.reply_text(
            "❌ Search database error.\n\n"
            f"{type(e).__name__}: {e}"
        )

        return

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

    # =========================
    # ONE RESULT
    # =========================

    if len(results) == 1:

        await send_result(
            update,
            context,
            results[0]
        )

        return

    # =========================
    # MULTIPLE RESULTS
    # =========================

    buttons = []

    for row in results[:20]:

        db_id = row.get("id")

        code = row.get("code", "")
        name = row.get("name", "")

        label = f"{code} - {name}"

        if len(label) > 60:
            label = label[:57] + "..."

        buttons.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"result:{db_id}"
                )
            ]
        )

    await update.message.reply_text(
        f"🔎 {len(results)} results found.\n\n"
        "नीचे अपना result चुनें:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# =========================
# CALLBACK
# =========================

async def callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    data = query.data

    # =========================
    # RESULT BUTTON
    # =========================

    if data.startswith("result:"):

        db_id = data.split(":", 1)[1]

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
                    "❌ Result no longer available."
                )

                return

            row = rows[0]

            # create temporary update-like handling
            user_id = query.from_user.id

            channel_id = str(row.get("channel_id"))
            message_id = row.get("message_id")

            code = row.get("code", "")
            name = row.get("name", "")
            description = row.get("description", "")
            photo = row.get("photo")

            try:

                member = await context.bot.get_chat_member(
                    chat_id=int(channel_id),
                    user_id=user_id
                )

                allowed = member.status in (
                    "member",
                    "administrator",
                    "creator"
                )

            except Exception:

                allowed = False

            if allowed:

                post_link = make_post_link(
                    channel_id,
                    message_id
                )

                caption = (
                    f"🎬 *{name}*\n\n"
                    f"🔢 Code: `{code}`\n\n"
                    f"📄 {description}"
                )

                keyboard = [
                    [
                        InlineKeyboardButton(
                            "📂 Open Post",
                            url=post_link
                        )
                    ]
                ]

                if photo:

                    await query.message.reply_photo(
                        photo=photo,
                        caption=caption,
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(
                            keyboard
                        )
                    )

                else:

                    await query.message.reply_text(
                        caption,
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(
                            keyboard
                        )
                    )

            else:

                channel_info = CHANNELS.get(channel_id)

                price = (
                    channel_info["price"]
                    if channel_info
                    else 299
                )

                keyboard = [
                    [
                        InlineKeyboardButton(
                            "💳 Subscribe & Access",
                            callback_data=f"pay:{db_id}"
                        )
                    ]
                ]

                await query.message.reply_text(
                    "🔒 *Access Required*\n\n"
                    f"🎬 {name}\n"
                    f"🔢 Code: `{code}`\n\n"
                    f"💰 Price: {price} ⭐ / month",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(
                        keyboard
                    )
                )

        except Exception as e:

            logger.exception("Result callback failed")

            await query.message.reply_text(
                "❌ Result error.\n\n"
                f"{type(e).__name__}: {e}"
            )

        return

    # =========================
    # PAYMENT
    # =========================

    if data.startswith("pay:"):

        db_id = data.split(":", 1)[1]

        try:

            response = (
                supabase
                .table("videos")
                .select("channel_id")
                .eq("id", db_id)
                .limit(1)
                .execute()
            )

            rows = response.data or []

            if not rows:

                await query.message.reply_text(
                    "❌ Video record not found."
                )

                return

            channel_id = str(
                rows[0].get("channel_id")
            )

            channel_info = CHANNELS.get(
                channel_id
            )

            if not channel_info:

                await query.message.reply_text(
                    "❌ Channel configuration missing."
                )

                return

            try:

                invite = await context.bot.create_chat_subscription_invite_link(
                    chat_id=int(channel_id),
                    name=f"TSB {channel_info['name']}",
                    subscription_period=2592000,
                    subscription_price=channel_info["price"],
                )

                await query.message.reply_text(
                    "💳 *Subscription Access*\n\n"
                    f"📢 {channel_info['name']}\n"
                    f"💰 {channel_info['price']} ⭐ / month\n\n"
                    "नीचे payment करके channel access लें:",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "⭐ Pay & Subscribe",
                                    url=invite.invite_link
                                )
                            ]
                        ]
                    )
                )

            except Exception as e:

                logger.exception(
                    "Subscription creation failed"
                )

                await query.message.reply_text(
                    "⚠️ Payment link अभी create नहीं हो पाया।\n\n"
                    "Please contact Support."
                )

        except Exception as e:

            logger.exception(
                "Payment callback failed"
            )

            await query.message.reply_text(
                "❌ Payment error."
            )

        return


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

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN missing"
        )

    if not SUPABASE_URL:
        raise RuntimeError(
            "SUPABASE_URL missing"
        )

    if not SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_KEY missing"
        )

    logger.info("Starting TSB Search Bot...")

    # TEST DATABASE BEFORE STARTING
    try:

        response = (
            supabase
            .table("videos")
            .select("id", count="exact")
            .limit(1)
            .execute()
        )

        logger.info(
            "Supabase connection OK. Count: %s",
            response.count
        )

    except Exception as e:

        logger.exception(
            "SUPABASE CONNECTION FAILED"
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
            help_command
        )
    )

    app.add_handler(
        CommandHandler(
            "dbtest",
            dbtest
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            callback_handler
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

    logger.info(
        "TSB Search Bot is running..."
    )

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
