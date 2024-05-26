"""This module contains the unit tests for the telegram bot module."""

import unittest
from unittest.mock import AsyncMock, patch
from Germes_theBot import check_openai_connection, save_user_to_db, switch_mode, show_balance, modes
from telegram import Update, User, Message, Chat, CallbackQuery
from telegram.ext import ContextTypes

class TestOpenAIConnection(unittest.TestCase):
    """Unit tests for checking the OpenAI connection."""

    def test_check_openai_connection_success(self):
        """Test case for successful OpenAI connection."""
        result = check_openai_connection()
        self.assertTrue(result)

    def test_check_openai_connection_failure(self):
        """Test case for failed OpenAI connection with an invalid API key."""
        result = check_openai_connection(api_key='invalid_key')
        self.assertFalse(result)

class TestSaveUserToDB(unittest.TestCase):
    """Unit tests for saving user to database."""

    @patch('Germes_theBot.db_connect', new_callable=AsyncMock)
    async def test_save_user_to_db(self, mock_db_connect):
        mock_conn = AsyncMock()
        mock_db_connect.return_value = mock_conn

        user_id = 123456
        username = 'test_user'
        first_name = 'Test'
        last_name = 'User'

        await save_user_to_db(mock_conn, user_id, username, first_name, last_name)
        mock_conn.execute.assert_called_once_with(
            "INSERT INTO identified_user (user_id, username, first_name, last_name) VALUES ($1, $2, $3, $4)",
            user_id, username, first_name, last_name
        )

class TestSwitchMode(unittest.TestCase):
    """Unit tests for switching modes."""

    @patch('Germes_theBot.modes', {})
    async def test_switch_mode_to_image(self):
        update = Update(
            update_id=1,
            callback_query=CallbackQuery(
                id="1",
                from_user=User(id=123456, first_name="Test", is_bot=False),
                chat_instance="1",
                data="switch_to_image",
                message=Message(
                    message_id=1,
                    date=None,
                    chat=Chat(id=123456, type="private"),
                    text="test"
                )
            )
        )
        context = ContextTypes.DEFAULT_TYPE()

        await switch_mode(update, context)
        self.assertEqual(modes[123456], "image")

    async def test_switch_mode_to_text(self):
        modes[123456] = "image"
        update = Update(
            update_id=1,
            callback_query=CallbackQuery(
                id="1",
                from_user=User(id=123456, first_name="Test", is_bot=False),
                chat_instance="1",
                data="switch_to_text",
                message=Message(
                    message_id=1,
                    date=None,
                    chat=Chat(id=123456, type="private"),
                    text="test"
                )
            )
        )
        context = ContextTypes.DEFAULT_TYPE()

        await switch_mode(update, context)
        self.assertEqual(modes[123456], "text")

class TestShowBalance(unittest.TestCase):
    """Unit tests for showing user balance."""

    @patch('Germes_theBot.db_connect', new_callable=AsyncMock)
    async def test_show_balance(self, mock_db_connect):
        mock_conn = AsyncMock()
        mock_db_connect.return_value = mock_conn
        mock_conn.fetchrow.return_value = {
            "user_id": 123456,
            "balance": 5.0,
            "images_generated": 3
        }

        update = Update(
            update_id=1,
            message=Message(
                message_id=1,
                date=None,
                chat=Chat(id=123456, type="private"),
                from_user=User(id=123456, first_name="Test", is_bot=False),
                text="/balance"
            )
        )
        context = ContextTypes.DEFAULT_TYPE()

        await show_balance(update, context)
        update.message.reply_text.assert_called_once_with(
            f"Behold, mortal! Your credit balance stands at $5.00/10$, "
            f"with 3 images already conjured forth from the depths of imagination."
        )

if __name__ == '__main__':
    unittest.main()