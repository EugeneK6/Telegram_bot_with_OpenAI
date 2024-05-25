"""This module contains the unit tests for the user_manager module."""

import unittest
from sqlite3 import OperationalError
from unittest.mock import patch
from WebAdmin import get_db_connection

class TestGetDBConnection(unittest.TestCase):
    """This class contains the unit tests for the `get_db_connection` function."""

    @patch('WebAdmin.psycopg2.connect')
    def test_get_db_connection_success(self, mock_connect):
        """This test case tests the successful connection to the database."""
        mock_conn = mock_connect.return_value
        conn = get_db_connection()
        self.assertEqual(conn, mock_conn)
        conn.close()

    @patch('WebAdmin.psycopg2.connect', side_effect=OperationalError("Connection failed"))
    def test_get_db_connection_failure(self, mock_connect):
        """This test case tests the failure of the connection to the database with an invalid host."""
        with self.assertRaises(OperationalError):
            get_db_connection(host='invalid_host')

if __name__ == '__main__':
    unittest.main()
