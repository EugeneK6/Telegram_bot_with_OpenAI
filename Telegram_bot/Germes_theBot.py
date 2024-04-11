import logging
import os
import asyncio
import base64
from io import BytesIO
import asyncpg
from openai import OpenAI
from logfmter import Logfmter
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)

# Enable logging
formatter = Logfmter(
    keys=["at", "logger", "level", "msg"],
    mapping={"at": "asctime", "logger": "name", "level": "levelname", "msg": "message"},
    datefmt='%H:%M:%S %d/%m/%Y'
)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
file_handler = logging.FileHandler("./logs/bot.log")
file_handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[stream_handler, file_handler]
)

# Set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

"""Environments"""
client = OpenAI(api_key=os.getenv("OPENAI_API"))
SUPER_USER_ID = int(os.getenv("SUPER_USER_ID"))
IMAGE_PRICE = float(os.getenv("IMAGE_PRICE"))


# Modes dictionary to store the mode for each chat
modes = {}  # chat_id -> mode ("text" or "image")


async def db_connect():
    return await asyncpg.connect(
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        database=os.getenv("POSTGRES_DB"),
        host=os.getenv("DB_HOST"),
    )

# function saves new user's data to database
async def save_user_to_db(conn, user_id, username, first_name=None, last_name=None):
    try:
        # Проверяем, есть ли пользователь уже в базе данных
        existing_user = await conn.fetchrow("SELECT user_id FROM identified_user WHERE user_id = $1", user_id)
        if existing_user:
            return
        await conn.execute(
            "INSERT INTO identified_user (user_id, username, first_name, last_name) VALUES ($1, $2, $3, $4)",
            user_id, username, first_name, last_name
        )
    except Exception as e:
        logger.error(f"Error saving user to database: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"User: {user}, Chat: {chat_id} started using bot")

    conn = await db_connect()
    await save_user_to_db(conn, user.id, user.username, user.first_name, user.last_name)
    await conn.close()

    modes[chat_id] = "text"  # Default mode is text
    keyboard = [[InlineKeyboardButton("Switch to Image Mode", callback_data='switch_to_image')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await update.message.reply_html(
        rf"Ah, greetings, {user.mention_html()}! You currently find yourself in the realm of text. "
        f"If you seek visual splendor, simply press the button to transition into the enchanting world of images.",
        reply_markup=reply_markup,
        )
    # Pinning the message
    try:
        await context.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)
    except Exception as e:
        logger.error(f"Error pinning the message: {e}")


async def switch_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switch the mode between text and image."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    if modes.get(chat_id) == "text":
        modes[chat_id] = "image"
        text = ("The realm has shifted to Image mode. Show me your vision, "
                "and I shall conjure forth a response of visual delight, mortal.")
        button_text = "Switch to Text Mode"
    else:
        modes[chat_id] = "text"
        text = "The realm has shifted to Text mode. Speak your thoughts, and I shall weave a response for you, mortal."
        button_text = "Switch to Image Mode"
    keyboard = [[InlineKeyboardButton(button_text, callback_data='switch_to_image' if modes[chat_id] == "text" else 'switch_to_text')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=text, reply_markup=reply_markup)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = await db_connect()
    try:

        chat_id = update.effective_chat.id
        user_message = update.message.text

        if modes.get(chat_id) == "image":

            user = update.effective_user
            allowed_users_dict = await conn.fetch("SELECT user_id FROM allowed_users ORDER BY user_id")
            user_ids = [int(user['user_id']) for user in allowed_users_dict]
            is_admin_user = user.id == SUPER_USER_ID
            if user.id not in user_ids:
                await update.message.reply_text(
                    "Alas, you are not permitted to access image mod functions at this time.")
                logger.info(f"{user.id} ({user.username}) tried to use image mod but is not allowed")
                return

            logger.info(f"User {user.id} ({user.username}) requested an image with prompt: '{user_message}'")

            if not is_admin_user:
                # Check user's credit balance
                user_data = await conn.fetchrow("SELECT * FROM user_credit WHERE user_id = $1", user.id)
                if user_data is None:
                    # Create user's credit record if not exists
                    await conn.execute("INSERT INTO user_credit (user_id, balance, images_generated) VALUES ($1, 0.00, 0)",
                                       user.id)
                    user_data = {"balance": 0.00, "images_generated": 0}
                balance = user_data["balance"]
                images_generated = user_data["images_generated"]

                # Check if user has enough balance for the image
                balance = float(balance)  # Преобразование в тип float
                if balance + IMAGE_PRICE > 10.00:
                    await update.message.reply_text(
                        "You have exceeded your credit limit. Please contact support for assistance."
                    )
                    logger.info(f"User {user.id} ({user.username}) exceeded credit limit")
                    return

                async with conn.transaction():
                    await conn.execute(
                        "UPDATE user_credit SET balance = balance + $1, images_generated = images_generated + 1 "
                        "WHERE user_id = $2",
                        IMAGE_PRICE, user.id
                    )

            # Generate and send the image
            async def keep_posting():
                while keep_posting.is_posting:
                    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='upload_photo')
                    await asyncio.sleep(5)

            keep_posting.is_posting = True

            posting_task = asyncio.create_task(keep_posting())

            try:
                response = await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: client.images.generate(
                        model="dall-e-3",
                        prompt=user_message,
                        n=1,
                        size="1024x1024",
                        response_format="b64_json"
                    )
                )

                keep_posting.is_posting = False
                await posting_task

                if hasattr(response, 'data') and len(response.data) > 0:
                    await update.message.reply_photo(photo=BytesIO(base64.b64decode(response.data[0].b64_json)))
                    logging.info(f"Successfully generated an image for prompt: '{user_message}'")
                else:
                    await update.message.reply_text("Sorry, the image generation did not succeed.")
                    logging.error(f"Failed to generate image for prompt: '{user_message}'")

            except Exception as e:
                keep_posting.is_posting = False
                await posting_task
                logging.error(f"Error generating image for prompt: '{user_message}': {e}")
                await update.message.reply_text("Sorry, there was an error generating your image.")
        else:
            async def keep_typing():
                while keep_typing.is_typing:
                    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
                    await asyncio.sleep(1)

            keep_typing.is_typing = True

            typing_task = asyncio.create_task(keep_typing())

            # Handle text generation
            try:
                response = await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: client.chat.completions.create(
                        model="gpt-4-turbo-preview",
                        messages=[
                            {"role": "system", "content": "You are a useful assistant for solving mathematics and cryptographic problems."},
                            {"role": "user", "content": user_message}
                        ]
                    )
                )

                keep_typing.is_typing = False
                await typing_task

                ai_response = response.choices[0].message.content
                await update.message.reply_text(ai_response.strip())
            except Exception as e:

                keep_typing.is_typing = False
                await typing_task
                error_message = f"Error generating AI response: {e}"
                logger.error(error_message)
                await update.message.reply_text(
                    "My apologies, mortal. At this moment, I am unable to decipher your message. "
                    "Could you provide more clarity in your inquiry?")
    finally:
        await conn.close()

# function shows user's balance
async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = await db_connect()
    try:
        user_id = update.effective_user.id
        user_data = await conn.fetchrow("SELECT user_id, balance, images_generated FROM user_credit WHERE user_id = $1", user_id)
        if user_data:
            balance = user_data.get("balance")
            images_generated = user_data.get("images_generated")
            is_admin_user = user_id == SUPER_USER_ID

            if balance is not None:
                if is_admin_user:
                    await update.message.reply_text(
                        "Behold, as the master of this bot, you wield an infinite credit limit, "
                        "granting you boundless power within its realms."
                    )
                else:
                    await update.message.reply_text(
                        f"Behold, mortal! Your credit balance stands at ${balance:.2f}/10$, "
                        f"with {images_generated} images already conjured forth from the depths of imagination."
                    )
            else:
                await update.message.reply_text(
                    "Alas, no records of credit balance grace your account as of now. "
                    "Craft your first masterpiece to activate your balance."
                )
        else:
            await update.message.reply_text(
                "Alas, no records of credit balance grace your account as of now. "
                "Craft your first masterpiece to activate your balance."
            )
    finally:
        await conn.close()


def main():
    """Start the bot."""
    telegram_bot_token = os.getenv("TELEGRAM_TOKEN")
    application = Application.builder().token(telegram_bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", show_balance))
    application.add_handler(CallbackQueryHandler(switch_mode, pattern='^switch_to_(text|image)$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()


if __name__ == "__main__":
    main()