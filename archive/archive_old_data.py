from datetime import datetime, timedelta, timezone

import psycopg2
import pyarrow as pa
import pyarrow.parquet as pq

from config import (
    DATABASE_URL,
    ARCHIVE_AFTER_DAYS,
    FETCH_SIZE,
    ARCHIVE_ROOT,
)


def connect_database():
    return psycopg2.connect(DATABASE_URL)


def find_archive_days(conn):
    cutoff = datetime.now(timezone.utc) - timedelta(days=ARCHIVE_AFTER_DAYS)

    sql = """
        SELECT DISTINCT DATE(time AT TIME ZONE 'UTC')
        FROM measurements
        WHERE time < %s
        ORDER BY 1;
    """

    with conn.cursor() as cur:
        cur.execute(sql, (cutoff,))
        rows = cur.fetchall()

    return [row[0] for row in rows]


def count_rows_for_day(conn, archive_day):
    start_time = datetime(
        archive_day.year,
        archive_day.month,
        archive_day.day,
        tzinfo=timezone.utc,
    )

    end_time = start_time + timedelta(days=1)

    sql = """
        SELECT COUNT(*)
        FROM measurements
        WHERE time >= %s
          AND time < %s;
    """

    with conn.cursor() as cur:
        cur.execute(sql, (start_time, end_time))
        return cur.fetchone()[0]


def build_archive_path(archive_day):
    folder = (
        ARCHIVE_ROOT
        / str(archive_day.year)
        / f"{archive_day.month:02d}"
    )

    folder.mkdir(parents=True, exist_ok=True)

    return folder / (
        f"measurements_{archive_day.isoformat()}.parquet"
    )


def parquet_row_count(path):
    if not path.exists():
        return None

    return pq.read_metadata(path).num_rows


def export_day(conn, archive_day):
    start_time = datetime(
        archive_day.year,
        archive_day.month,
        archive_day.day,
        tzinfo=timezone.utc,
    )

    end_time = start_time + timedelta(days=1)

    expected_rows = count_rows_for_day(conn, archive_day)

    print()
    print("=" * 60)
    print(f"Archiving day: {archive_day}")
    print(f"Database rows: {expected_rows:,}")

    if expected_rows == 0:
        print("No data. Skipping.")
        return

    output_path = build_archive_path(archive_day)

    existing_rows = parquet_row_count(output_path)

    if existing_rows == expected_rows:
        print("Archive already exists and matches the database.")
        print(output_path)
        return

    if output_path.exists():
        print("Existing archive is incomplete. Recreating it.")
        output_path.unlink()

    cursor_name = f"archive_{archive_day.strftime('%Y%m%d')}"

    cur = conn.cursor(name=cursor_name)
    cur.itersize = FETCH_SIZE

    sql = """
        SELECT
            time,
            sensor_id,
            value,
            quality
        FROM measurements
        WHERE time >= %s
          AND time < %s
        ORDER BY time;
    """

    cur.execute(sql, (start_time, end_time))

    writer = None
    written_rows = 0

    try:
        while True:
            rows = cur.fetchmany(FETCH_SIZE)

            if not rows:
                break

            table = pa.table({
                "time": [row[0] for row in rows],
                "sensor_id": [row[1] for row in rows],
                "value": [row[2] for row in rows],
                "quality": [row[3] for row in rows],
            })

            if writer is None:
                writer = pq.ParquetWriter(
                    output_path,
                    table.schema,
                    compression="snappy",
                )

            writer.write_table(table)

            written_rows += len(rows)

            print(
                f"\rWritten: {written_rows:,} / {expected_rows:,}",
                end=""
            )

    finally:
        cur.close()

        if writer is not None:
            writer.close()

    print()

    archived_rows = parquet_row_count(output_path)

    print(f"Parquet rows: {archived_rows:,}")

    if archived_rows != expected_rows:
        raise RuntimeError(
            f"Archive verification failed: "
            f"database={expected_rows:,}, "
            f"parquet={archived_rows:,}"
        )

    size_mb = output_path.stat().st_size / 1024 / 1024

    print("Verification successful.")
    print(f"File size: {size_mb:.2f} MB")
    print(f"Saved to: {output_path}")


def main():
    print("=" * 60)
    print("BRIDGE DIGITAL TWIN ARCHIVER")
    print("=" * 60)

    print(f"Archive after: {ARCHIVE_AFTER_DAYS} days")
    print(f"Archive folder: {ARCHIVE_ROOT}")

    conn = connect_database()

    try:
        archive_days = find_archive_days(conn)

        if not archive_days:
            print()
            print(
                f"No measurements are older than "
                f"{ARCHIVE_AFTER_DAYS} days."
            )
            print("Nothing was archived.")
            return

        print()
        print(f"Days to archive: {len(archive_days)}")

        for archive_day in archive_days:
            export_day(conn, archive_day)

        print()
        print("=" * 60)
        print("ARCHIVE COMPLETE")
        print("=" * 60)
        print("No rows were deleted from TimescaleDB.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()