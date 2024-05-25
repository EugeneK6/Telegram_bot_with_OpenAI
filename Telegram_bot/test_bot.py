"""This module contains the unit tests for the telegram bot module."""

import unittest
from Germes_theBot import check_openai_connection

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

if __name__ == '__main__':
    unittest.main()