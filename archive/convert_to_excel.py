from pathlib import Path

import pandas as pd

from config import ARCHIVE_ROOT


MAX_DATA_ROWS = 1_048_575


def convert_parquet_to_excel(parquet_file):

    print()
    print("=" * 60)
    print(f"Reading: {parquet_file}")

    df = pd.read_parquet(parquet_file)

    print(f"Rows: {len(df):,}")

    if "time" in df.columns:

        df["time"] = pd.to_datetime(df["time"])

        if df["time"].dt.tz is not None:
            df["time"] = df["time"].dt.tz_localize(None)

    excel_file = parquet_file.with_suffix(".xlsx")

    print(f"Creating: {excel_file.name}")

    if len(df) <= MAX_DATA_ROWS:

        df.to_excel(
            excel_file,
            index=False,
            engine="openpyxl"
        )

        print("Worksheets: 1")

    else:

        with pd.ExcelWriter(
            excel_file,
            engine="openpyxl"
        ) as writer:

            start = 0
            sheet_number = 1

            while start < len(df):

                end = min(
                    start + MAX_DATA_ROWS,
                    len(df)
                )

                chunk = df.iloc[start:end]

                sheet_name = f"Measurements_{sheet_number}"

                print(
                    f"Writing {sheet_name}: "
                    f"{start + 1:,} to {end:,}"
                )

                chunk.to_excel(
                    writer,
                    sheet_name=sheet_name,
                    index=False
                )

                start = end
                sheet_number += 1

        print(
            f"Worksheets: {sheet_number - 1}"
        )

    print(f"Saved: {excel_file}")


def main():

    print()
    print("=" * 60)
    print("PARQUET TO EXCEL CONVERTER")
    print("=" * 60)

    print("Archive root:")
    print(ARCHIVE_ROOT)

    parquet_files = sorted(
        ARCHIVE_ROOT.rglob("*.parquet")
    )

    if not parquet_files:

        print()
        print("No Parquet files found.")
        return

    print()
    print(
        f"Found {len(parquet_files)} Parquet files."
    )

    for parquet_file in parquet_files:

        convert_parquet_to_excel(
            parquet_file
        )

    print()
    print("=" * 60)
    print("CONVERSION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()