"""Run inside the API container; read-only HTTP checks and mocked bad-input checks."""
import json
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from urllib.request import urlopen
from urllib.error import HTTPError

from app import main


class PrototypeChecks(unittest.TestCase):
    def request(self, path):
        try:
            with urlopen('http://localhost:8000' + path, timeout=10) as response:
                return response.status, response.read()
        except HTTPError as error:
            return error.code, error.read()

    def test_dashboard_loads(self):
        status, body = self.request('/dashboard')
        self.assertEqual(status, 200)
        self.assertIn(b'simulated data', body.lower())
        self.assertIn(b'/model?embed=1', body)

    def test_four_sensor_histories(self):
        status, body = self.request('/sensors')
        self.assertEqual(status, 200)
        sensors = json.loads(body)
        self.assertEqual({s['sensor_id'] for s in sensors}, {'ACC_01','SG_01','TEMP_01','DISP_01'})
        for sensor in sensors:
            with self.subTest(sensor=sensor['sensor_id']):
                status, body = self.request('/sensors/' + sensor['sensor_id'] + '/history?limit=3')
                self.assertEqual(status, 200)
                rows = json.loads(body)
                self.assertEqual(len(rows), 3)
                times = [datetime.fromisoformat(row['timestamp']) for row in rows]
                self.assertEqual(times, sorted(times, reverse=True))

    def test_query_bounds(self):
        for query in ('limit=-1','limit=0','limit=1001','limit=oops','minutes=0','minutes=-1','minutes=10081'):
            with self.subTest(query=query):
                self.assertEqual(self.request('/sensors/ACC_01/history?' + query)[0], 422)
        self.assertEqual(self.request('/sensors/ACC_01/stats?minutes=-1')[0], 422)

    def test_missing_sensor(self):
        self.assertEqual(self.request('/sensors/DOES_NOT_EXIST/latest')[0], 404)
        self.assertEqual(json.loads(self.request('/sensors/DOES_NOT_EXIST/history')[1]), [])

    def test_reject_bad_measurements_before_database(self):
        valid = {'sensor_id':'ACC_01', 'timestamp':'2026-09-13T00:00:00Z', 'value':1.5}
        invalid = [None, [], {}, {**valid,'value':float('nan')}, {**valid,'value':float('inf')},
                   {**valid,'value':True}, {**valid,'value':'bad'}, {**valid,'timestamp':'bad'},
                   {**valid,'timestamp':None}, {**valid,'sensor_id':''}]
        with patch.object(main, 'get_conn') as connection:
            for payload in invalid:
                with self.subTest(payload=payload), self.assertRaises((ValueError, TypeError)):
                    main.insert_measurement(payload)
            connection.assert_not_called()

    def test_topic_mismatch_and_malformed_json_are_not_stored(self):
        with patch.object(main, 'insert_measurement') as insert:
            for body in (b'{bad', b'{"sensor_id":"SG_01"}', b'[]'):
                main.on_message(None, None, SimpleNamespace(topic='bridge/sensors/ACC_01/data',payload=body))
            insert.assert_not_called()

    def test_valid_measurement_preserves_value_and_utc(self):
        with patch.object(main, 'get_conn') as connection:
            main.insert_measurement({'sensor_id':'ACC_01','timestamp':'2026-09-13T00:00:00Z','value':1.25})
            cursor = connection.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            values = cursor.execute.call_args.args[1]
            self.assertEqual(values[1:], ('ACC_01', 1.25, 'GOOD'))
            self.assertEqual(values[0].isoformat(), '2026-09-13T00:00:00+00:00')


if __name__ == '__main__':
    unittest.main(verbosity=2)
