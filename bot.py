import os
import re
import logging
from typing import Optional, List, Dict, Any

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ChatMemberStatus
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
# TSB VIDEO SEARCH BOT
# SEARCH + SUPABASE + CHANNEL ACCESS + TELEGRAM STARS
# =========================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("TSB_SEARCH_BOT")


# =========================================================
# ENVIRONMENT
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "").strip()


# =========================================================
# PAYMENT SETTINGS
# =========================================================

SUBSCRIPTION_DAYS = 30
SUBSCRIPTION_SECONDS = 2592000
SUBSCRIPTION_STARS = 299


# =========================================================
# CHANNEL SETTINGS
# =========================================================

CHANNELS = {
    "-1004338671388": {
        "name": "Channel 1",
        "prefix": "1P-",
        "price": SUBSCRIPTION_STARS,
    },

    "-1004490954138": {
        "name": "Channel 2",
        "prefix": "2P-",
        "price": SUBSCRIPTION_STARS,
    },

    "-1003963263624": {
        "name": "Channel 3",
        "prefix": "3P-",
        "price": SUBSCRIPTION_STARS,
    },

    "-1003472229143": {
        "name": "Channel 4",
        "prefix": "4P-",
        "price": SUBSCRIPTION_STARS,
    },
}


# =========================================================
# STARTUP CHECKS
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
    SUPABASE_KEY,
)


# =========================================================
# HELPERS
# =========================================================

def normalize(value: Any) -> str:
    if value is None:
        return ""

    value = str(value).strip().upper()

    value = value.replace("_", "-")

    value = re.sub(r"\s+", "", value)

    return value


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def get_channel(channel_id: Any) -> Optional[Dict[str, Any]]:
    return CHANNELS.get(str(channel_id))


def channel_from_code(code: str) -> Optional[str]:
    normalized = normalize(code)

    for channel_id, info in CHANNELS.items():
        prefix = normalize(info["prefix"])

        if normalized.startswith(prefix):
            return channel_id

    return None


def make_post_link(channel_id: str, message_id: Any) -> Optional[str]:
    try:
        channel_number = str(channel_id).replace("-100", "", 1)
        return f"https://t.me/c/{channel_number}/{int(message_id)}"
    except Exception:
        return None


# =========================================================
# DATABASE
# =========================================================

def load_all_videos() -> List[Dict[str, Any]]:
    """
    Loads all video records from Supabase in pages.
    Works with thousands of videos.
    """

    all_rows: List[Dict[str, Any]] = []

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

    return all_rows


def search_database(search_text: str) -> List[Dict[str, Any]]:
    """
    Searches:
    1. Exact code
    2. Partial code
    3. Name
    4. Description

    No hardcoded video list.
    Future 1,000 / 2,000 / 3,000+ videos per channel
    can be searched automatically.
    """

    query = normalize(search_text)

    if not query:
        return []

    videos = load_all_videos()

    exact_matches = []
    partial_matches = []

    for row in videos:

        code = normalize(row.get("code"))
        name = normalize(row.get("name"))
        description = normalize(row.get("description"))

        # Exact code
        if code == query:
            exact_matches.append(row)
            continue

        # Partial / name / description
        if (
            query in code
            or query in name
            or query in description
        ):
            partial_matches.append(row)

    return exact_matches + partial_matches


# =========================================================
# CHANNEL MEMBERSHIP
# =========================================================

async def is_user_member(
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

        if status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.MEMBER,
        ):
            return True

        # Telegram may return restricted users who are still members.
        if status == ChatMemberStatus.RESTRICTED:
            return bool(getattr(member, "is_member", False))

        return False

    except Exception as error:
        logger.warning(
            "Membership check failed | user=%s | channel=%s | error=%s",
            user_id,
            channel_id,
            error,
        )

        return False


# =========================================================
# CREATE TELEGRAM STARS SUBSCRIPTION LINK
# =========================================================

async def create_subscription_link(
    context: ContextTypes.DEFAULT_TYPE,
    channel_id: str,
) -> Optional[str]:

    channel = get_channel(channel_id)

    if not channel:
        return None

    try:
        result = await context.bot.create_chat_subscription_invite_link(
            chat_id=int(channel_id),
            name=f"TSB {channel['name']} - {SUBSCRIPTION_STARS} Stars",
            subscription_period=SUBSCRIPTION_SECONDS,
            subscription_price=SUBSCRIPTION_STARS,
        )

        return result.invite_link

    except Exception as error:

        logger.exception(
            "Subscription link creation failed | channel=%s",
            channel_id,
        )

        return None


# =========================================================
# PAYMENT BUTTON
# =========================================================

async def send_subscription_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    channel_id: str,
    code: str,
):

    channel = get_channel(channel_id)

    if not channel:
        await update.effective_message.reply_text(
            "❌ Channel configuration not found."
        )
        return

    link = await create_subscription_link(
        context,
        channel_id,
    )

    if not link:
        await update.effective_message.reply_text(
            "❌ Payment link अभी create नहीं हो पाया।\n\n"
            "कृपया थोड़ी देर बाद फिर कोशिश करें।"
        )
        return

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"⭐ Subscribe {SUBSCRIPTION_STARS} Stars / 30 Days",
                    url=link,
                )
            ],
            [
                InlineKeyboardButton(
                    "🔄 Check Access",
                    callback_data=f"check:{channel_id}:{code}",
                )
            ],
        ]
    )

    text = (
        "🔒 Access Required\n\n"
        f"📢 {channel['name']}\n"
        f"🔢 Code: {code}\n\n"
        f"⭐ Price: {SUBSCRIPTION_STARS} Stars\n"
        f"📅 Duration: {SUBSCRIPTION_DAYS} Days\n\n"
        "Subscribe करने के बाद आपको इस channel का access मिलेगा.\n"
        "दूसरे channels का access अलग रहेगा."
    )

    await update.effective_message.reply_text(
        text,
        reply_markup=keyboard,
    )


# =========================================================
# VIDEO RESULT
# =========================================================

async def send_video_result(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    row: Dict[str, Any],
):

    user = update.effective_user

    if not user:
        return

    channel_id = str(row.get("channel_id", ""))

    channel = get_channel(channel_id)

    if not channel:
        await update.effective_message.reply_text(
            "❌ Channel information not found."
        )
        return

    code = clean_text(row.get("code"))
    name = clean_text(row.get("name"))
    description = clean_text(row.get("description"))
    photo = clean_text(row.get("photo"))
    message_id = row.get("message_id")

    # -----------------------------------------------------
    # CHECK ACCESS
    # -----------------------------------------------------

    has_access = await is_user_member(
        context,
        user.id,
        channel_id,
    )

    if not has_access:

        await send_subscription_message(
            update,
            context,
            channel_id,
            code,
        )

        return

    # -----------------------------------------------------
    # USER HAS ACCESS
    # -----------------------------------------------------

    post_link = make_post_link(
        channel_id,
        message_id,
    )

    caption_parts = []

    if name:
        caption_parts.append(f"🎬 {name}")

    if code:
        caption_parts.append(f"🔢 Code: {code}")

    if description:
        caption_parts.append(
            f"\n📄 {description}"
        )

    caption = "\n".join(caption_parts).strip()

    keyboard_rows = []

    if post_link:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    "📂 Open Post",
                    url=post_link,
                )
            ]
        )

    keyboard = InlineKeyboardMarkup(
        keyboard_rows
    ) if keyboard_rows else None

    try:

        if photo:

            await update.effective_message.reply_photo(
                photo=photo,
                caption=caption or "🎬 Video",
                reply_markup=keyboard,
            )

        else:

            await update.effective_message.reply_text(
                caption or "🎬 Video",
                reply_markup=keyboard,
            )

    except Exception as error:

        logger.exception(
            "Sending video result failed: %s",
            error,
        )

        await update.effective_message.reply_text(
            "❌ Result भेजने में समस्या हुई।"
        )


# =========================================================
# SEARCH COMMAND
# =========================================================

async def handle_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.effective_message:
        return

    text = update.effective_message.text or ""

    search_text = text.strip()

    if not search_text:
        await update.effective_message.reply_text(
            "🔍 Code या video name भेजें.\n\n"
            "Example:\n"
            "1P-444\n"
            "1P-555\n"
            "2P-001"
        )
        return

    # Ignore commands
    if search_text.startswith("/"):
        return

    try:

        results = search_database(
            search_text
        )

    except Exception as error:

        logger.exception(
            "Database search failed: %s",
            error,
        )

        await update.effective_message.reply_text(
            "❌ Database search में समस्या हुई।"
        )

        return

    if not results:

        await update.effective_message.reply_text(
            "❌ No result found.\n\n"
            "Example:\n"
            "1P-234\n"
            "2P-001\n"
            "3P-100"
        )

        return

    # -----------------------------------------------------
    # SEND RESULTS
    # -----------------------------------------------------

    # Avoid sending too many duplicate records.
    # Exact code normally returns one result.
    max_results = 20

    for row in results[:max_results]:

        await send_video_result(
            update,
            context,
            row,
        )


# =========================================================
# /START
# =========================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.effective_message:
        return

    text = (
        "🔍 TSB Video Search\n\n"
        "अपने video का code या name भेजें.\n\n"
        "Example:\n"
        "1P-444\n"
        "1P-555\n"
        "2P-001\n\n"
        "अगर आपके पास channel access है तो "
        "आपको Open Post मिलेगा.\n\n"
        "Access नहीं होने पर ⭐ Subscription option मिलेगा."
    )

    await update.effective_message.reply_text(
        text
    )


# =========================================================
# /HELP
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.effective_message:
        return

    await update.effective_message.reply_text(
        "🔍 Search करने के लिए video code या name भेजें.\n\n"
        "Examples:\n"
        "1P-444\n"
        "1P-555\n"
        "2P-123\n"
        "movie name"
    )


# =========================================================
# /DBTEST
# =========================================================

async def dbtest_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.effective_message:
        return

    user = update.effective_user

    if not user:
        return

    if ADMIN_USER_ID:
        if str(user.id) != ADMIN_USER_ID:
            await update.effective_message.reply_text(
                "❌ Admin only."
            )
            return

    try:

        response = (
            supabase
            .table("videos")
            .select("id", count="exact")
            .limit(1)
            .execute()
        )

        count = response.count

        await update.effective_message.reply_text(
            f"✅ Supabase OK\n\n"
            f"📊 Total records: {count}"
        )

    except Exception as error:

        logger.exception(
            "DB test failed: %s",
            error,
        )

        await update.effective_message.reply_text(
            f"❌ Supabase Error\n\n{error}"
        )


# =========================================================
# CHECK ACCESS BUTTON
# =========================================================

async def check_access_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    if not query:
        return

    await query.answer()

    data = query.data or ""

    parts = data.split(":", 2)

    if len(parts) != 3:
        return

    action = parts[0]
    channel_id = parts[1]
    code = parts[2]

    if action != "check":
        return

    user = query.from_user

    has_access = await is_user_member(
        context,
        user.id,
        channel_id,
    )

    if has_access:

        await query.edit_message_text(
            "✅ Access confirmed!\n\n"
            f"🔢 Code: {code}\n\n"
            "अब वही code फिर से भेजें "
            "और आपको Open Post मिल जाएगा."
        )

    else:

        channel = get_channel(channel_id)

        channel_name = (
            channel["name"]
            if channel
            else "Channel"
        )

        await query.edit_message_text(
            "🔒 Access अभी नहीं मिला.\n\n"
            f"📢 {channel_name}\n"
            f"⭐ {SUBSCRIPTION_STARS} Stars / 30 Days\n\n"
            "पहले Subscribe करें, फिर "
            "Check Access दबाएँ."
        )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    logger.exception(
        "Unhandled error:",
        exc_info=context.error,
    )


# =========================================================
# STARTUP TEST
# =========================================================

async def post_init(
    application: Application,
):

    try:

        me = await application.bot.get_me()

        logger.info(
            "BOT STARTED | @%s | id=%s",
            me.username,
            me.id,
        )

    except Exception as error:

        logger.exception(
            "Bot startup check failed: %s",
            error,
        )

    try:

        response = (
            supabase
            .table("videos")
            .select("id", count="exact")
            .limit(1)
            .execute()
        )

        logger.info(
            "SUPABASE OK | ROW COUNT = %s",
            response.count,
        )

    except Exception as error:

        logger.exception(
            "SUPABASE CHECK FAILED: %s",
            error,
        )


# =========================================================
# MAIN
# =========================================================

def main():

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler(
            "start",
            start_command,
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
            dbtest_command,
        )
    )

    # Payment/access callback
    application.add_handler(
        CallbackQueryHandler(
            check_access_callback,
            pattern=r"^check:",
        )
    )

    # Search
    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            handle_search,
        )
    )

    # Errors
    application.add_error_handler(
        error_handler
    )

    logger.info(
        "TSB Search Bot starting..."
    )

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
