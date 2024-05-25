"""This module contains the unit tests for the telegram bot module."""


import unittest
from unittest.mock import patch, Mock
from Germes_theBot import check_openai_connection, handle_message, start, db_connect, save_user_to_db

class TestOpenAIConnection(unittest.TestCase):
    """Unit tests for checking the OpenAI connection."""

    @patch('Germes_theBot.OpenAI')
    def test_check_openai_connection_success(self, MockOpenAI):
        """Test case for successful OpenAI connection."""
        # Mock the OpenAI client and its response
        mock_client = Mock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create.return_value = Mock(choices=[Mock(message=Mock(content='Hello!'))])

        result = check_openai_connection()
        self.assertTrue(result)
        MockOpenAI.assert_called_once()

    @patch('Germes_theBot.OpenAI')
    def test_check_openai_connection_failure(self, MockOpenAI):
        """Test case for failed OpenAI connection with an invalid API key."""
        # Mock the OpenAI client to raise an exception
        mock_client = Mock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception('Invalid API key')

        result = check_openai_connection(api_key='invalid_key')
        self.assertFalse(result)
        MockOpenAI.assert_called_once_with(api_key='invalid_key')

class TestChatModeSwitch(unittest.TestCase):
    """Unit tests for checking the chat mode switching."""

    @patch('Germes_theBot.db_connect')
    def test_switch_to_image_mode(self, mock_db_connect):
        """Test switching to image mode."""
        # Mock the database connection
        mock_conn = Mock()
        mock_db_connect.return_value = mock_conn

        # Simulate user sending command to switch mode
        update = Mock()
        update.effective_chat.id = 'test_chat_id'
        query = Mock()
        query.data = 'switch_to_image'
        update.callback_query = query

        # Call the handler function
        handle_message(update, None)

        # Check if the mode has switched correctly
        self.assertEqual(modes['test_chat_id'], 'image')

class TestUserDatabase(unittest.TestCase):
    """Unit tests for checking user data saving to the database."""

    @patch('Germes_theBot.asyncpg.connect')
    async def test_save_user_to_db(self, mock_db_connect):
        """Test saving user data to the database."""
        # Mock the database connection
        mock_conn = Mock()
        mock_db_connect.return_value = mock_conn

        # Simulate user starting interaction with the bot
        update = Mock()
        user = Mock()
        user.id = 'test_user_id'
        user.username = 'test_username'
        user.first_name = 'Test'
        user.last_name = 'User'
        update.effective_user = user

        # Call the handler function
        await start(update, None)

        # Check if user data is saved to the database
        mock_conn.execute.assert_called_once()

class TestImageGeneration(unittest.TestCase):
    """Unit tests for checking image generation."""

    @patch('Germes_theBot.client.images.generate')
    @patch('Germes_theBot.asyncio.get_running_loop')
    @patch('Germes_theBot.asyncio.sleep')
    async def test_image_generation(self, mock_get_running_loop, mock_sleep, mock_generate):
        """Test image generation."""
        # Mock the image generation response
        mock_response = Mock()
        mock_response.data = [{'b64_json': 'base64_encoded_image_data'}]
        mock_generate.return_value = mock_response

        # Simulate user sending a message to generate image
        update = Mock()
        update.effective_chat.id = 'test_chat_id'
        update.message.text = 'Test prompt'

        # Call the handler function
        await handle_message(update, None)

        # Check if image is sent to the user
        update.message.reply_photo.assert_called_once()

if __name__ == '__main__':
    unittest.main()
