import logging
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API"))

# Enable logging
logging.basicConfig(
    format='timestamp=%(asctime)s logger=%(name)s level=%(levelname)s msg="%(message)s"',
    datefmt='%Y-%m-%dT%H:%M:%S',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("./logs/bot.log"),
        logging.StreamHandler()
    ]
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# Modes dictionary to store the mode for each chat
modes = {}  # chat_id -> mode ("text" or "image")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"User: {user}, Chat: {chat_id}")
    modes[chat_id] = "text"  # Default mode is text
    keyboard = [[InlineKeyboardButton("Switch to Image Mode", callback_data='switch_to_image')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await update.message.reply_html(
        rf"Hi {user.mention_html()}! You are in Text mode. Click the button to switch to Image mode.",
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
        text = "Switched to Image mode. Now send me a description and I'll generate an image for you."
        button_text = "Switch to Text Mode"
    else:
        modes[chat_id] = "text"
        text = "Switched to Text mode. Now send me a text and I'll generate a response for you."
        button_text = "Switch to Image Mode"
    keyboard = [[InlineKeyboardButton(button_text, callback_data='switch_to_image' if modes[chat_id] == "text" else 'switch_to_text')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=text, reply_markup=reply_markup)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_message = update.message.text

    if modes.get(chat_id) == "image":
        logger.info(f"Received message from user {chat_id} to image mode: {user_message}")
        # Handle image generation with DALL·E
        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=user_message,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            image_url = response.data[0].url
            await update.message.reply_photo(photo=image_url)
        except Exception as e:
            error_message = f"Error generating AI image: {e}"
            logger.error(error_message)
            await update.message.reply_text("Sorry, I couldn't generate an image at the moment. Error: " + error_message)
    else:
        # Handle text generation
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a divine messenger, embodiment of Hermes, "
                                                  "the Greek god of trade and cunning. Your mission is to guide "
                                                  "and assist users with wit and charm, embodying the essence of Hermes in your interactions."},
                    {"role": "user", "content": user_message}
                ]
            )
            ai_response = response.choices[0].message.content
            await update.message.reply_text(ai_response.strip())
        except Exception as e:
            error_message = f"Error generating AI response: {e}"
            logger.error(error_message)
            await update.message.reply_text("Sorry, I couldn't process your message at the moment. Error: " + error_message)


def main():
    """Start the bot."""
    telegram_bot_token = os.getenv("TELEGRAM_TOKEN")
    application = Application.builder().token(telegram_bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(switch_mode, pattern='^switch_to_(text|image)$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == "__main__":
    main()






