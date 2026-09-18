# V2 Azure SQL preparation checks

Run: 18 September 2026, Python 3.12 isolated environment.

`python -m unittest discover -s tests -v`

- 15 tests passed: 10 Azure SQL adapter/API contract tests and 5 model tests.
- 4 live HTTP tests skipped: database not provisioned, V2_TEST_URL not set.
- Compose YAML parsed; expected services are API, MQTT and opt-in simulator.
- No local database service; separate v2 project name and host port.

Database operations in the unit tests are mocked. These results do not certify
T-SQL execution, cloud connectivity or performance. Docker image build, repeatable
schema initialization, real reads/writes and live dashboard verification remain
required once Azure SQL is provisioned. See README.md.
