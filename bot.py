import json
import os
import re
import logging
from pathlib import Path

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# 1. BOT TOKEN
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "8908632279:AAF-Glydyj_2ETCYkeswpwRuNKztWOql110")


# =========================================================
# 2. YOUR 4 PRIVATE CHANNEL IDs
# =========================================================

CHANNELS = {
    "1": -1004338671388,
    "2": -1004490954138,
    "3": -1003963263624,
    "4": -1003472229143,
}


# =========================================================
# 3. DATABASE FILE
# =========================================================

DATA_FILE = Path("search_data.json")


# =========================================================
# 4. LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# 5. LOAD / SAVE DATA
# =========================================================

def load_data():
    if not DATA_FILE.exists():
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data

    except Exception as e:
        logger.error("Database load error: %s", e)

    return {}


DATA = load_data()


def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(
                DATA,
                f,
                ensure_ascii=False,
                indent=2
            )
    except Exception as e:
        logger.error("Database save error: %s", e)


# =========================================================
# 6. CHANNEL ID -> PREFIX
# =========================================================

CHANNEL_PREFIX = {
    -1004338671388: "1",
    -1004490954138: "2",
    -1003963263624: "3",
    -1003472229143: "4",
}


# =========================================================
# 7. EXTRACT CODE
# =========================================================

def extract_code(text):
    if not text:
        return None

    pattern = r"\b([1-4]P-[A-Za-z0-9_-]+)\b"

    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        return match.group(1).upper()

    return None


# =========================================================
# 8. CLEAN TEXT
# =========================================================

def clean_text(text):
    if not text:
        return ""

    return text.strip()


# =========================================================
# 9. MAKE PRIVATE CHANNEL POST LINK
# =========================================================

def make_post_link(chat_id, message_id):
    """
    Telegram private channel:
    -1004338671388
    becomes:
    https://t.me/c/4338671388/message_id
    """

    chat_number = str(chat_id).replace("-100", "", 1)

    return f"https://t.me/c/{chat_number}/{message_id}"


# =========================================================
# 10. SAVE CHANNEL POST
# =========================================================

async def save_channel_post(message):
    if not message:
        return

    chat_id = message.chat.id

    if chat_id not in CHANNEL_PREFIX:
        return

    prefix_number = CHANNEL_PREFIX[chat_id]

    # Text / caption
    text = message.text or message.caption or ""

    text = clean_text(text)

    if not text:
        return

    code = extract_code(text)

    # Only save posts that contain our P-code
    if not code:
        return

    # Make sure code belongs to correct channel
    if not code.upper().startswith(prefix_number + "P-"):
        return

    # =====================================================
    # Determine media
    # =====================================================

    photo_file_id = None

    if message.photo:
        photo_file_id = message.photo[-1].file_id

    # =====================================================
    # Title / description
    # =====================================================

    lines = [x.strip() for x in text.splitlines() if x.strip()]

    name = ""
    description = ""

    for line in lines:
        low = line.lower()

        if (
            "🎬" in line
            or "name" in low
            or "title" in low
        ):
            name = re.sub(
                r"^(🎬\s*|name\s*:\s*|title\s*:\s*)",
                "",
                line,
                flags=re.IGNORECASE
            ).strip()

        if (
            "📝" in line
            or "description" in low
            or "desc" in low
        ):
            description = re.sub(
                r"^(📝\s*|description\s*:\s*|desc\s*:\s*)",
                "",
                line,
                flags=re.IGNORECASE
            ).strip()

    # If no explicit name was found, use second line
    if not name:
        for line in lines:
            if line.upper() != code.upper():
                if not line.startswith("🔗"):
                    name = line
                    break

    # =====================================================
    # Save
    # =====================================================

    DATA[code.upper()] = {
        "code": code.upper(),
        "channel_id": chat_id,
        "message_id": message.message_id,
        "name": name,
        "description": description,
        "text": text,
        "photo_file_id": photo_file_id,
        "post_link": make_post_link(
            chat_id,
            message.message_id
        ),
    }

    save_data()

    logger.info(
        "Indexed: %s | Channel: %s | Message: %s",
        code,
        chat_id,
        message.message_id
    )


# =========================================================
# 11. CHANNEL POST HANDLER
# =========================================================

async def channel_post_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    try:
        if update.channel_post:
            await save_channel_post(update.channel_post)

    except Exception as e:
        logger.exception(
            "Channel post handler error: %s",
            e
        )


# =========================================================
# 12. MEMBERSHIP CHECK
# =========================================================

async def is_member(
    bot,
    user_id,
    channel_id
):
    try:
        member = await bot.get_chat_member(
            chat_id=channel_id,
            user_id=user_id
        )

        status = member.status

        # Active members
        if status in (
            "creator",
            "administrator",
            "member",
        ):
            return True

        # Restricted member can still have access
        if status == "restricted":
            return bool(
                getattr(member, "is_member", False)
            )

        return False

    except Exception as e:
        logger.warning(
            "Membership check failed: %s",
            e
        )

        return False


# =========================================================
# 13. START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = (
        "🔎 <b>TSB Search Bot</b>\n\n"
        "Apna code ya video name search karo.\n\n"
        "Examples:\n"
        "• <code>1P-234</code>\n"
        "• <code>2P-001</code>\n"
        "• <code>3P-125</code>\n"
        "• <code>4P-500</code>\n\n"
        "Aap video ka naam ya keyword bhi search kar sakte ho."
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# =========================================================
# 14. HELP
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = (
        "🔎 <b>Search kaise karein?</b>\n\n"
        "Code ke saath:\n"
        "<code>1P-234</code>\n"
        "<code>2P-234</code>\n"
        "<code>3P-234</code>\n"
        "<code>4P-234</code>\n\n"
        "Ya video ka naam / keyword type karo."
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML"
    )


# =========================================================
# 15. SEARCH DATA
# =========================================================

def search_items(query):

    query = query.strip().lower()

    if not query:
        return []

    results = []

    # -----------------------------------------------------
    # Exact code
    # -----------------------------------------------------

    if query.upper() in DATA:
        return [DATA[query.upper()]]

    # -----------------------------------------------------
    # Prefix search
    # -----------------------------------------------------

    prefix_match = re.match(
        r"^([1-4])p(?:-|$)",
        query,
        re.IGNORECASE
    )

    selected_prefix = None

    if prefix_match:
        selected_prefix = prefix_match.group(1)

    # -----------------------------------------------------
    # Keyword search
    # -----------------------------------------------------

    for item in DATA.values():

        code = str(item.get("code", ""))
        name = str(item.get("name", ""))
        description = str(item.get("description", ""))
        full_text = str(item.get("text", ""))

        if selected_prefix:
            if not code.upper().startswith(
                selected_prefix + "P-"
            ):
                continue

        searchable = (
            code + " " +
            name + " " +
            description + " " +
            full_text
        ).lower()

        if query in searchable:
            results.append(item)

    # Newest / latest message first
    results.sort(
        key=lambda x: int(
            x.get("message_id", 0)
        ),
        reverse=True
    )

    return results[:10]


# =========================================================
# 16. SEND RESULT
# =========================================================

async def send_result(
    update,
    item
):

    user_id = update.effective_user.id

    channel_id = int(
        item["channel_id"]
    )

    # -----------------------------------------------------
    # Membership check
    # -----------------------------------------------------

    member = await is_member(
        update.get_bot(),
        user_id,
        channel_id
    )

    if not member:

        keyboard = [
            [
                InlineKeyboardButton(
                    "🔐 Join / Get Access",
                    url=item["post_link"]
                )
            ]
        ]

        await update.message.reply_text(
            "🔒 <b>Access Required</b>\n\n"
            "Is result ko open karne ke liye "
            "corresponding private channel ka active "
            "access hona chahiye.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

        return

    # -----------------------------------------------------
    # Result details
    # -----------------------------------------------------

    code = item.get("code", "")
    name = item.get("name", "")
    description = item.get(
        "description",
        ""
    )

    if not name:
        name = "Video"

    if not description:
        description = "No description available."

    caption = (
        f"🏷️ <b>{code}</b>\n\n"
        f"🎬 <b>{name}</b>\n\n"
        f"📝 {description}"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "📂 Open Post",
                url=item["post_link"]
            )
        ]
    ]

    # -----------------------------------------------------
    # Photo / Thumbnail
    # -----------------------------------------------------

    photo_file_id = item.get(
        "photo_file_id"
    )

    if photo_file_id:

        try:
            await update.message.reply_photo(
                photo=photo_file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    keyboard
                )
            )

            return

        except Exception as e:
            logger.warning(
                "Photo send error: %s",
                e
            )

    # -----------------------------------------------------
    # Text fallback
    # -----------------------------------------------------

    await update.message.reply_text(
        caption,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )


# =========================================================
# 17. SEARCH COMMAND / MESSAGE
# =========================================================

async def search_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.message.text.strip()

    if query.startswith("/"):
        return

    if len(query) < 2:
        await update.message.reply_text(
            "🔎 Code ya video name type karo."
        )
        return

    results = search_items(query)

    if not results:

        await update.message.reply_text(
            "❌ <b>No result found.</b>\n\n"
            "Example:\n"
            "<code>1P-234</code>\n"
            "<code>2P-001</code>",
            parse_mode="HTML"
        )

        return

    # Exact result
    if len(results) == 1:

        await send_result(
            update,
            results[0]
        )

        return

    # Multiple results
    text = (
        f"🔎 <b>{len(results)} results found</b>\n\n"
        "Neeche se select karo:"
    )

    keyboard = []

    for item in results:

        code = item.get(
            "code",
            "Unknown"
        )

        name = item.get(
            "name",
            "Video"
        )

        label = f"📂 {code} — {name}"

        if len(label) > 60:
            label = label[:57] + "..."

        keyboard.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"open:{code}"
                )
            ]
        )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )


# =========================================================
# 18. BUTTON CLICK
# =========================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    data = query.data

    if not data.startswith("open:"):
        return

    code = data.split(
        "open:",
        1
    )[1].upper()

    item = DATA.get(code)

    if not item:
        await query.message.reply_text(
            "❌ Result available nahi hai."
        )
        return

    user_id = query.from_user.id

    channel_id = int(
        item["channel_id"]
    )

    # -----------------------------------------------------
    # Membership
    # -----------------------------------------------------

    member = await is_member(
        context.bot,
        user_id,
        channel_id
    )

    if not member:

        await query.message.reply_text(
            "🔒 Is result ko open karne ke liye "
            "corresponding private channel ka "
            "active access chahiye."
        )

        return

    keyboard = [
        [
            InlineKeyboardButton(
                "📂 Open Post",
                url=item["post_link"]
            )
        ]
    ]

    await query.message.reply_text(
        f"🏷️ <b>{item.get('code')}</b>\n\n"
        f"🎬 <b>{item.get('name') or 'Video'}</b>\n\n"
        f"📝 {item.get('description') or 'No description'}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )


# =========================================================
# 19. ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.exception(
        "Telegram error: %s",
        context.error
    )


# =========================================================
# 20. MAIN
# =========================================================

def main():

    if (
        not BOT_TOKEN
        or BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE"
    ):
        raise RuntimeError(
            "BOT_TOKEN set nahi hai."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # -----------------------------------------------------
    # Commands
    # -----------------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    # -----------------------------------------------------
    # Channel posts
    # -----------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.UpdateType.CHANNEL_POST,
            channel_post_handler
        )
    )

    # -----------------------------------------------------
    # User search
    # -----------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            search_handler
        )
    )

    # -----------------------------------------------------
    # Buttons
    # -----------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.ALL,
            lambda update, context: None
        )
    )

    # CallbackQuery handler
    from telegram.ext import CallbackQueryHandler

    application.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern=r"^open:"
        )
    )

    application.add_error_handler(
        error_handler
    )

    print("===================================")
    print("TSB Telegram Search Bot")
    print("Bot is starting...")
    print("Indexed items:", len(DATA))
    print("===================================")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()
