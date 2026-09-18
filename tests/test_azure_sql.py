"""Offline API/driver contract checks: python -m unittest discover -s tests -p test_azure_sql.py -v"""
import os
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import pyodbc
from fastapi.testclient import TestClient
from app import database, main


class AzureSQLTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)  # No startup: no broker needed for unit tests.
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.context = patch.object(main, "get_conn")
        self.context.start().return_value.__enter__.return_value = self.connection
        self.addCleanup(self.context.stop)

    def test_summary_preserves_missing_readings_and_utc(self):
        self.cursor.fetchall.return_value = [
            ("TEST_001", "Test sensor", "Test only", "unit", datetime(2026, 9, 18, 0, 0), 1.5, "GOOD"),
            ("TEST_002", "Test sensor", "Test only", "unit", None, None, None),
        ]
        response = self.client.get('/sensors/summary')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()[0]['timestamp'].endswith('+00:00'))
        self.assertIsNone(response.json()[1]['timestamp'])
        self.assertIn('OUTER APPLY', self.cursor.execute.call_args.args[0])

    def test_history_parameter_order_and_utc(self):
        self.cursor.fetchall.return_value = [(datetime(2026, 9, 18), 2, "GOOD")]
        for suffix, expected in [("?limit=7", (7, "TEST_001")), ("?limit=7&minutes=3", (7, "TEST_001", 3))]:
            with self.subTest(suffix=suffix):
                response = self.client.get('/sensors/TEST_001/history' + suffix)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.cursor.execute.call_args.args[1], expected)
                self.assertEqual(response.json()[0]['timestamp'], '2026-09-18T00:00:00+00:00')

    def test_latest_found_and_missing(self):
        self.cursor.fetchone.return_value = (datetime(2026, 9, 18), "TEST_001", 2, "unit", "GOOD")
        self.assertEqual(self.client.get('/sensors/TEST_001/latest').json()['timestamp'], '2026-09-18T00:00:00+00:00')
        self.cursor.fetchone.return_value = None
        self.assertEqual(self.client.get('/sensors/TEST_001/latest').status_code, 404)

    def test_stats_empty_and_parameterized_window(self):
        self.cursor.fetchone.return_value = (0, None, None, None, None)
        response = self.client.get('/sensors/TEST_001/stats?minutes=5')
        self.assertEqual(response.json()['count'], 0)
        self.assertIsNone(response.json()['rms'])
        self.assertEqual(self.cursor.execute.call_args.args[1], ('TEST_001', 5))
        self.assertIn('DATEADD', self.cursor.execute.call_args.args[0])

    def test_query_validation(self):
        for suffix in ('?limit=0', '?limit=1001', '?minutes=-1'):
            self.assertEqual(self.client.get('/sensors/TEST_001/history' + suffix).status_code, 422)

    def test_unavailable_database_is_503(self):
        with patch.object(main, 'get_conn', side_effect=pyodbc.OperationalError('08001', 'unreachable')):
            self.assertEqual(self.client.get('/sensors').status_code, 503)
            self.assertEqual(self.client.get('/health').status_code, 503)

    def test_input_offsets_normalized_before_insert(self):
        row = main.measurement_row({'sensor_id': 'TEST_001', 'timestamp': '2026-09-18T10:00:00+10:00', 'value': 3})
        self.assertEqual(row[0], datetime(2026, 9, 18, 0, 0))
        self.assertIsNone(row[0].tzinfo)
        main.store_measurements([row])
        self.assertEqual(self.cursor.executemany.call_args.args[1], [row])
        self.assertEqual(self.cursor.executemany.call_args.args[0].count('?'), 4)
        self.assertTrue(self.cursor.fast_executemany)

    def test_invalid_values_rejected(self):
        for value in (True, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                main.measurement_row({'sensor_id': 'TEST_001', 'timestamp': '2026-09-18T00:00:00Z', 'value': value})

    def test_connection_requires_settings_and_escapes_secrets(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(pyodbc.InterfaceError):
            database.connection_string()
        config = dict(AZURE_SQL_SERVER='example.database.windows.net', AZURE_SQL_DATABASE='bridge', AZURE_SQL_USER='user', AZURE_SQL_PASSWORD='a};PWD=bad')
        with patch.dict(os.environ, config):
            value = database.connection_string()
        self.assertIn('PWD={a}};PWD=bad}', value)
        self.assertIn('Encrypt=yes;TrustServerCertificate=no;', value)

    def test_connections_commit_or_rollback_and_close(self):
        for fail in (False, True):
            with self.subTest(fail=fail), patch.object(database, 'connection_string', return_value='test'), patch.object(database.pyodbc, 'connect') as connect:
                conn = connect.return_value
                try:
                    with database.get_conn():
                        if fail:
                            raise ValueError('test rollback')
                except ValueError:
                    pass
                conn.close.assert_called_once()
                if fail:
                    conn.rollback.assert_called_once()
                    conn.commit.assert_not_called()
                else:
                    conn.commit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
