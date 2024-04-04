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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"User: {user}, Chat: {chat_id} started using bot")
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
        user = update.effective_user
        allowed_users_dict = await conn.fetch("SELECT user_id FROM allowed_users ORDER BY user_id")
        logging.info(allowed_users_dict)
        user_ids = [int(user['user_id']) for user in allowed_users_dict]
        is_admin_user = user.id == SUPER_USER_ID
        if user.id not in user_ids:
            await update.message.reply_text("Alas, you are not permitted to access this bot's functions at this time.")
            logger.info(f"{user.id} ({user.username}) tried to use this bot but is not allowed")
            return

        chat_id = update.effective_chat.id
        user_message = update.message.text

        if modes.get(chat_id) == "image":
            logging.info(f"User {user.id} ({user.username}) requested an image with prompt: '{user_message}'")

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
                if balance + IMAGE_PRICE > 10.00:
                    await update.message.reply_text(
                        "You have exceeded your credit limit. Please contact support for assistance.")
                    logger.info(f"User {user.id} ({user.username}) exceeded credit limit")
                    return

                async with conn.transaction():
                    # Deduct image price from user's balance and increment images_generated count
                    await conn.execute(
                        "UPDATE user_credit SET balance = balance + $1, images_generated = images_generated + 1 WHERE user_id = $2",
                        IMAGE_PRICE, user.id)

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
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You are a divine messenger, embodiment of Hermes, "
                                                          "the Greek god of trade and cunning. Your mission is to guide "
                                                          "and assist users with wit and charm, embodying the essence of Hermes in your interactions."},
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


async def validate_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> (bool, str):
    admin_user_id = int(os.getenv("SUPER_USER_ID"))
    if update.effective_user.id != admin_user_id:
        logger.info(f"User {update.effective_user.id} is not allowed to run this command.")
        await update.message.reply_text("Access denied.")
        return False
    return True


async def allow_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    is_admin = await validate_admin(update, context)
    if not is_admin:
        return
    if not context.args:
        await update.message.reply_text("Please specify a user ID.")
        return
    try:
        user_id_to_allow = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID format. Please provide a valid user ID.")
        return
    conn = await db_connect()
    try:
        # Check if user is already allowed
        existing_user = await conn.fetchval("SELECT user_id FROM allowed_users WHERE user_id = $1",
                                            int(user_id_to_allow))
        if existing_user:
            logger.info(f"Attempted to allow an already allowed user: {user_id_to_allow}")
            await update.message.reply_text(f"User {user_id_to_allow} is already allowed.")
            return

        await conn.execute("INSERT INTO allowed_users (user_id) VALUES ($1)", int(user_id_to_allow))
        logger.info(f"User {user_id_to_allow} has been allowed.")
        await update.message.reply_text(f"User {user_id_to_allow} is allowed from now.")
    finally:
        await conn.close()


async def disable_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    is_admin = await validate_admin(update, context)
    if not is_admin:
        return
    if not context.args:
        await update.message.reply_text("Please specify a user ID.")
        return
    try:
        user_id_to_disable = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID format. Please provide a valid user ID.")
        return
    conn = await db_connect()
    try:
        # Check if user is not allowed
        existing_user = await conn.fetchval("SELECT user_id FROM allowed_users WHERE user_id = $1",
                                            int(user_id_to_disable))
        if not existing_user:
            logger.info(f"Attempted to disable a user who is not currently allowed: {user_id_to_disable}")
            await update.message.reply_text(f"User {user_id_to_disable} is not currently allowed.")
            return

        await conn.execute("DELETE FROM allowed_users WHERE user_id = $1", int(user_id_to_disable))
        logger.info(f"User {user_id_to_disable} access has been revoked.")
        await update.message.reply_text(f"User {user_id_to_disable} access revoked.")
    finally:
        await conn.close()


# function that show user balance
async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = await db_connect()
    try:
        user_id = update.effective_user.id
        user_data = await conn.fetchrow("SELECT * FROM user_credit WHERE user_id = $1", user_id)
        if user_data:
            balance = user_data["balance"]
            images_generated = user_data["images_generated"]
            is_admin_user = user_id == SUPER_USER_ID

            if is_admin_user:
                await update.message.reply_text("Behold, as the master of this bot, you wield an infinite credit limit,"
                                                "granting you boundless power within its realms.")
            else:
                await update.message.reply_text(
                    f"Behold, mortal! Your credit balance stands at ${balance:.2f}/10$, "
                    f"with {images_generated} images already conjured forth from the depths of imagination.")
        else:
            await update.message.reply_text("Alas, no records of credit balance grace your account as of now.  "
                                            "Craft  your first masterpiece to activate your balance.")
    finally:
        await conn.close()


def main():
    """Start the bot."""
    telegram_bot_token = os.getenv("TELEGRAM_TOKEN")
    application = Application.builder().token(telegram_bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("allow", allow_user))
    application.add_handler(CommandHandler("disable", disable_user))
    application.add_handler(CommandHandler("balance", show_balance))
    application.add_handler(CallbackQueryHandler(switch_mode, pattern='^switch_to_(text|image)$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()


if __name__ == "__main__":
    main()
