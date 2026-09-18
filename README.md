# Bridge Digital Twin v2 — Azure SQL preparation

V2 stores sensor metadata and measurements in **Azure SQL Database**, outside
Docker. The API, MQTT broker and optional simulator remain in Docker. The existing
dashboard and model viewer are retained. This is a separate project from v1.

```
Simulator / sensors -> MQTT -> FastAPI -> Azure SQL Database
                                |
                          Dashboard and model viewer
```

## Current status

The code is prepared for Azure SQL; no Azure database has been purchased or
connected yet. Offline tests cover API responses, query parameters, UTC conversion,
connection cleanup and error handling. Actual SQL execution and the Docker image
must be checked against your provisioned database before deployment.

This is Microsoft SQL Server SQL, not PostgreSQL/TimescaleDB. PostgreSQL backups
cannot be restored directly into Azure SQL. Do not run the v1 initialization SQL.

## When you create the database

1. Create an Azure SQL logical server and database, preferably near the application
   VM (Australia East for the current deployment).
2. Choose SQL authentication for this initial implementation. Entra-only servers
   require a different connection implementation; managed identity is not yet wired in.
3. Allow the application VM to reach the database using an appropriate Azure SQL
   firewall rule or private endpoint. Use the logical server's DNS hostname, even
   with a private endpoint. Avoid enabling access from all Azure services merely
   to make a connection work.
4. Keep the database administrator credentials for setup. Use a separate contained
   database user for the running API, granted SELECT on dbo.sensors and SELECT,
   INSERT on dbo.measurements. Create that user in the target database using your
   administrator account after schema initialization; the API does not need DDL rights.

Connections require ODBC Driver 18, encryption and certificate validation. The
Dockerfile installs the driver using Microsoft's Debian 12 package repository.

## Configure and initialize

The copied `.env` still contains v1 PostgreSQL settings. It is deliberately left
unchanged. Replace those settings when ready, using `.env.example` as the template.
Never commit `.env` or paste credentials into source files.

Required values:

```dotenv
AZURE_SQL_SERVER=your-server.database.windows.net
AZURE_SQL_DATABASE=bridge-digital-twin-v2
AZURE_SQL_USER=your-setup-user
AZURE_SQL_PASSWORD='your-password'
API_PORT=8001
```

From this v2 directory:

```bash
docker compose build
docker compose run --rm --no-deps api python -m app.init_db
```

The setup command creates tables and a sensor/time index and registers the four
bridge sensors plus TEST_001 through TEST_200. It is repeatable and does not clear
existing rows. Run it once at a time with an account that can create tables and indexes.
It initializes an empty database; it is not an upgrade tool for incompatible tables.

After creating your limited database user, change AZURE_SQL_USER and
AZURE_SQL_PASSWORD to that user's credentials, then run:

```bash
docker compose up -d
```

Open http://localhost:8001/dashboard and http://localhost:8001/health. Without a
publisher, "Waiting for data" is expected. To generate demo readings deliberately:

```bash
docker compose --profile demo up -d
docker compose logs --tail=20 simulator
```

Stop generating test readings with `docker compose stop simulator`. With all 204
sensors publishing every two seconds, the simulator creates about **8.8 million
measurement rows per day**. Set a paid usage budget and retention plan before
continuous use. A free database that pauses at its allowance limit will interrupt
ingestion. Health checks and dashboard polling also use database compute.

## Separate deployment from v1

Compose uses project name `bridge-digital-twin-v2`, port 8001 and a separate model
volume, so v1 can keep running on port 8000. MQTT is internal to the v2 Docker
network. No database container, PostgreSQL port or database Docker volume is created.
Uploaded v1 model versions are not automatically copied into the v2 model volume;
bundled model assets remain available.

For public access on the VM without a reverse proxy, set `API_BIND_ADDRESS=0.0.0.0`
and `API_PORT=8000` only after v1 is stopped, then start v2. This preserves the
existing public URL. A reverse proxy running inside another container must use a
shared network/service address instead of its own localhost. This preparation does
not modify the live v1 site until that deliberate cutover.

The copied folder also contains v1's `.git` metadata. Check `git remote -v` before
pushing; use a separate v2 repository or a deliberate v2 branch. No push or remote
change is performed by this preparation.

## Historical data migration

Migration is a separate cutover step after database provisioning. Keep the v1
database and backups until row counts and timestamps are verified. Export sensor
metadata first, then measurement rows from PostgreSQL in bounded time ranges;
normalize timestamps to UTC and import with parameterized Azure SQL inserts.
Preserve custom sensors as well as the 204 defaults. Import into a clean target
or track completed batches to avoid duplicate rows on a retry. Stop ingestion for
the final delta, validate counts/latest timestamps, then switch the application.
No existing records have been moved or deleted and no migration script is supplied yet.

The current prototype ingestion uses an in-memory queue and drops a failed batch
after logging an error, as v1 did. A durable queue with retries and deduplication
is required before relying on it for lossless real-sensor ingestion or database pauses.

## Tests

With Python 3.12 and an isolated virtual environment:

```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests -p test_azure_sql.py -v
python -m unittest discover -s tests -p test_models.py -v
```

Run all offline checks with `python -m unittest discover -s tests -v`. Four live
checks are skipped unless `V2_TEST_URL` is set to the v2 base URL. Set it only after
initializing Azure SQL and starting the demo; the live tests require recent readings.

After provisioning, initialize the database twice to verify repeatability, start
the demo, and check `/sensors`, `/sensors/summary`, `/sensors/TEST_001/latest`,
`/sensors/TEST_001/history?limit=5&minutes=10` and
`/sensors/TEST_001/stats?minutes=10`. Timestamps should include `+00:00`, readings
should advance, and the dashboard should show live sensors. Stop the simulator
and confirm the status becomes stale after the 10-second window and next refresh.

## References

- [Python/ODBC connectivity](https://learn.microsoft.com/en-us/sql/connect/python/pyodbc/python-sql-driver-pyodbc)
- [Microsoft ODBC Linux installation](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server)
- [Azure SQL free-offer limits](https://learn.microsoft.com/en-us/azure/azure-sql/database/free-offer)

The original model documentation remains in `README-v1-reference.md` for asset
provenance only. Its PostgreSQL, simulator and deployment commands do not apply to v2.
