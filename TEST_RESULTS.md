# Prototype checks — 13 September 2026

## Passed in this run

- Dashboard HTTP response and simulated-data label.
- Four registered sensors; three readings retrieved per sensor in descending timestamp order.
- Invalid history limits and time windows return HTTP 422, including negative, zero,
  excessive and non-integer limits. History limit is 1–1000; time window is 1–10080 minutes.
- Missing sensor: latest returns 404; history returns an empty list.
- Malformed measurements, Boolean values, NaN and infinity rejected before database access
  (mocked database check).
- Malformed JSON and topic/sensor mismatch do not reach the insert function (mocked check).
- Valid numeric value and UTC timestamp passed unchanged to the SQL insert (mocked check).
- Live API interruption: all four browser cards reported connection unavailable and retained
  their readings. Restarting the API restored all four streams without reloading the page.

Seven automated unittest methods passed. The interruption check was performed separately
against the running browser. API and continuous simulator were left running.

## Reproduce automated checks

With Docker available in PowerShell and the demo running, from the project folder:

```powershell
Get-Content tests/test_prototype.py -Raw | docker compose exec -T api python -
```

The tests expect at least three saved measurements for each of the four demo sensors.
HTTP checks are read-only. Invalid-input tests use mocks and do not insert bad data.

## Additional readiness and recovery checks

- Added `/health`: HTTP 200 only when the sensor table is queryable and the MQTT
  subscription is acknowledged; otherwise HTTP 503 with component status.
- Docker waits for database health before starting the API, and API health before
  starting the demo simulator. This startup sequence completed successfully.
- Database outage returned HTTP 503 from both `/health` and `/sensors`, with a
  generic error instead of database connection details. Restart restored readiness.
- MQTT outage returned HTTP 503 with `mqtt: false`; reconnect restored readiness.
- The seven automated regression checks passed again after these changes.

## Remaining before an external preview

- Full responsive layout and cross-browser verification, plus accessibility review.
- Data-loss/replay handling and longer interruption tests.
  The simulator currently sends best-effort MQTT messages; interruption recovery does not
  guarantee that readings during an outage are saved.
- Unit, quality and sensor-specific range validation; timestamp and duplicate policies.
- Authentication, private access, secrets configuration and hosting setup.
- Backup restoration, load testing and deployment monitoring.
- Real bridge geometry and surveyed sensor positions for an accurate 3D twin.

This is a local prototype check, not production certification or a bridge safety assessment.
