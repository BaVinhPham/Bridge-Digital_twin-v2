"""Opt-in read-only checks: set V2_TEST_URL=http://localhost:8001 after provisioning."""
import json
import os
import unittest
from datetime import datetime, timezone
from urllib.request import urlopen
from urllib.error import HTTPError


@unittest.skipUnless(os.getenv('V2_TEST_URL'), 'Set V2_TEST_URL after provisioning Azure SQL')
class PrototypeChecks(unittest.TestCase):
    def request(self, path):
        try:
            with urlopen(os.environ['V2_TEST_URL'].rstrip('/') + path, timeout=45) as response:
                return response.status, response.read()
        except HTTPError as error:
            return error.code, error.read()

    def test_dashboard_and_health(self):
        status, body = self.request('/dashboard')
        self.assertEqual(status, 200)
        self.assertIn(b'serverNow()', body)
        self.assertEqual(self.request('/health')[0], 200)

    def test_sensors_and_summary(self):
        status, body = self.request('/sensors')
        self.assertEqual(status, 200)
        ids = {item['sensor_id'] for item in json.loads(body)}
        self.assertTrue({'ACC_01', 'SG_01', 'TEMP_01', 'DISP_01', 'TEST_001', 'TEST_200'} <= ids)
        status, body = self.request('/sensors/summary')
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)), len(ids))

    def test_latest_history_and_stats(self):
        status, body = self.request('/sensors/TEST_001/latest')
        self.assertEqual(status, 200, 'Start the demo and wait for readings')
        self.assertEqual(datetime.fromisoformat(json.loads(body)['timestamp']).tzinfo, timezone.utc)
        status, body = self.request('/sensors/TEST_001/history?limit=3&minutes=10')
        self.assertEqual(status, 200)
        rows = json.loads(body)
        self.assertTrue(1 <= len(rows) <= 3)
        times = [datetime.fromisoformat(row['timestamp']) for row in rows]
        self.assertEqual(times, sorted(times, reverse=True))
        status, body = self.request('/sensors/TEST_001/stats?minutes=10')
        self.assertEqual(status, 200)
        self.assertGreater(json.loads(body)['count'], 0)

    def test_missing_sensor(self):
        self.assertEqual(self.request('/sensors/DOES_NOT_EXIST/latest')[0], 404)
        self.assertEqual(json.loads(self.request('/sensors/DOES_NOT_EXIST/history')[1]), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
