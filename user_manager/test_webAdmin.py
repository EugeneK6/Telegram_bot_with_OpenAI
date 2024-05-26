"""This module contains the unit tests for the user_manager module."""

import unittest
from psycopg2.extensions import connection
from psycopg2 import OperationalError
from WebAdmin import get_db_connection


class TestGetDBConnection(unittest.TestCase):
    """This class contains the unit tests for the `get_db_connection` function."""

    def test_get_db_connection_success(self):
        """This test case tests the successful connection to the database."""
        conn = get_db_connection()
        self.assertIsInstance(conn, connection)
        conn.close()

    def test_get_db_connection_failure(self):
        """This test case tests the failure of the connection to the database with an invalid host."""
        with self.assertRaises(OperationalError):
            get_db_connection(host='invalid_host')


if __name__ == '__main__':
    unittest.main()
