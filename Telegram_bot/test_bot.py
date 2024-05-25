"""This module contains the unit tests for the telegram bot module."""


import unittest
from unittest.mock import patch, Mock
from Germes_theBot import check_openai_connection

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

if __name__ == '__main__':
    unittest.main()
