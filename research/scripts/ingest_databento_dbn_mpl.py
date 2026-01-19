"""
Ingest Databento DBN files for MPL (Micro Platinum futures) into DuckDB
========================================================================

Reads local .dbn.zst files and creates:
  - bars_1m_mpl (1-minute OHLCV bars)
  - bars_5m_mpl (5-minute aggregated bars)

NO LOOKAHEAD: All timestamps converted to UTC+10 (Brisbane) consistently
Contract handling: Selects most liquid front contract (highest volume, no spreads)

Usage:
  python scripts/ingest_databento_dbn_mpl.py <path_to_dbn_folder>

  Example:
  python scripts/ingest_databento_dbn_mpl.py MPL
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import List, Tuple, Dict, Optional
import json

import databento as db
import duckdb


# Configuration
DB_PATH = "gold.db"
SYMBOL = "MPL"  # Logical continuous symbol
TZ_LOCAL = ZoneInfo("Australia/Brisbane")  # UTC+10, no DST
TZ_UTC = timezone.utc


def log(msg: str):
    """Print timestamped log message (ASCII only)"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def ts_event_to_datetime(ts_event: int) -> datetime:
    """
    Convert Databento ts_event (nanoseconds since epoch) to datetime UTC
    """
    return datetime.fromtimestamp(ts_event / 1e9, tz=TZ_UTC)


def ts_to_local(dt_utc: datetime) -> datetime:
    """Convert UTC datetime to Brisbane local"""
    return dt_utc.astimezone(TZ_LOCAL)


def load_symbology_mapping(dbn_folder: Path) -> Dict[int, str]:
    """
    Load symbology mapping from symbology.json

    Returns:
        Dict of instrument_id (int) -> symbol (str)
    """
    symbology_path = dbn_folder / "symbology.json"

    if not symbology_path.exists():
        log("  WARNING: symbology.json not found - symbols will be missing")
        return {}

    log(f"  Loading symbology from {symbology_path.name}...")

    with open(symbology_path, 'r') as f:
        data = json.load(f)

    # Build instrument_id -> symbol mapping
    # Format: {"symbol": [{"d0": "date", "d1": "date", "s": "instrument_id"}, ...], ...}
    id_to_symbol = {}

    if 'result' in data:
        for symbol, periods in data['result'].items():
            if isinstance(periods, list):
                for period in periods:
                    if isinstance(period, dict) and 's' in period:
                        instrument_id = int(period['s'])
                        id_to_symbol[instrument_id] = symbol

    log(f"  Loaded {len(id_to_symbol):,} instrument_id mappings")

    return id_to_symbol


def init_mpl_tables(con: duckdb.DuckDBPyConnection):
    """Create MPL-specific tables if they don't exist"""
    log("Initializing MPL tables...")

    # Create bars_1m_mpl
    con.execute("""
        CREATE TABLE IF NOT EXISTS bars_1m_mpl (
          ts_utc        TIMESTAMPTZ NOT NULL,
          symbol        TEXT NOT NULL,          -- logical symbol 'MPL'
          source_symbol TEXT,                   -- actual contract 'MPLF5', 'MPLJ5', etc
          open          DOUBLE NOT NULL,
          high          DOUBLE NOT NULL,
          low           DOUBLE NOT NULL,
          close         DOUBLE NOT NULL,
          volume        BIGINT NOT NULL,
          PRIMARY KEY (symbol, ts_utc)
        );
    """)

    # Create bars_5m_mpl
    con.execute("""
        CREATE TABLE IF NOT EXISTS bars_5m_mpl (
          ts_utc        TIMESTAMPTZ NOT NULL,
          symbol        TEXT NOT NULL,
          source_symbol TEXT,
          open          DOUBLE NOT NULL,
          high          DOUBLE NOT NULL,
          low           DOUBLE NOT NULL,
          close         DOUBLE NOT NULL,
          volume        BIGINT NOT NULL,
          PRIMARY KEY (symbol, ts_utc)
        );
    """)

    log("MPL tables ready")


def choose_front_contract(records_by_symbol: Dict[str, List], instrument_to_symbol: Dict[int, str]) -> Optional[str]:
    """
    Choose the most liquid front contract (highest volume, no spreads)

    Args:
        records_by_symbol: Dict of symbol -> list of records
        instrument_to_symbol: Mapping from instrument_id to symbol

    Returns:
        Symbol string of front contract, or None if no valid contracts
    """
    if not records_by_symbol:
        return None

    # Filter MPL contracts only, exclude spreads (contain '-')
    mpl_outrights = {}
    for sym, recs in records_by_symbol.items():
        if not sym:
            continue
        # MPL contracts: MPLF5, MPLJ5, MPLN5, MPLV5, MPLF6, etc
        if sym.startswith('MPL') and '-' not in sym and len(sym) <= 5:
            mpl_outrights[sym] = recs

    if not mpl_outrights:
        return None

    # Calculate total volume per contract
    volume_by_symbol = {}
    for sym, recs in mpl_outrights.items():
        total_vol = sum(rec.volume for rec in recs if hasattr(rec, 'volume'))
        volume_by_symbol[sym] = total_vol

    # Return contract with highest volume
    if not volume_by_symbol:
        return None

    front_symbol = max(volume_by_symbol.items(), key=lambda x: x[1])[0]
    log(f"  Chosen front contract: {front_symbol} (volume: {volume_by_symbol[front_symbol]:,})")

    return front_symbol


def upsert_bars_1m(con: duckdb.DuckDBPyConnection, rows: List[Tuple]) -> int:
    """Insert or replace 1-minute bars"""
    if not rows:
        return 0

    con.executemany(
        """
        INSERT OR REPLACE INTO bars_1m_mpl
        (ts_utc, symbol, source_symbol, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )

    return len(rows)


def rebuild_5m_from_1m(con: duckdb.DuckDBPyConnection, start_utc: datetime, end_utc: datetime):
    """
    Rebuild 5-minute bars from 1-minute bars for the given time range

    Deterministic bucketing:
      ts_5m = floor(epoch(ts_utc) / 300) * 300
    """
    log(f"  Rebuilding 5m bars: {start_utc} -> {end_utc}")

    # Delete existing 5m bars in range
    con.execute(
        """
        DELETE FROM bars_5m_mpl
        WHERE symbol = ?
          AND ts_utc >= CAST(? AS TIMESTAMPTZ)
          AND ts_utc <  CAST(? AS TIMESTAMPTZ)
        """,
        [SYMBOL, start_utc, end_utc],
    )

    # Aggregate from 1m bars
    con.execute(
        """
        INSERT INTO bars_5m_mpl (ts_utc, symbol, source_symbol, open, high, low, close, volume)
        SELECT
            CAST(to_timestamp(floor(epoch(ts_utc) / 300) * 300) AS TIMESTAMPTZ) AS ts_5m,
            symbol,
            NULL AS source_symbol,
            arg_min(open, ts_utc)  AS open,
            max(high)              AS high,
            min(low)               AS low,
            arg_max(close, ts_utc) AS close,
            sum(volume)            AS volume
        FROM bars_1m_mpl
        WHERE symbol = ?
          AND ts_utc >= CAST(? AS TIMESTAMPTZ)
          AND ts_utc <  CAST(? AS TIMESTAMPTZ)
        GROUP BY 1, 2
        ORDER BY 1
        """,
        [SYMBOL, start_utc, end_utc],
    )

    log("  5m bars rebuilt")


def process_dbn_file(dbn_path: Path, con: duckdb.DuckDBPyConnection, instrument_to_symbol: Dict[int, str]) -> int:
    """
    Process a single DBN file and insert bars into database

    Returns:
        Number of bars inserted
    """
    log(f"Processing: {dbn_path.name}")

    # Read DBN file using databento-python
    try:
        store = db.DBNStore.from_file(str(dbn_path))
    except Exception as e:
        log(f"  ERROR reading DBN file: {e}")
        return 0

    df = store.to_df()

    if df is None or len(df) == 0:
        log("  No data in file")
        return 0

    log(f"  Loaded {len(df):,} records from DBN")

    # Group records by symbol (instrument_id -> symbol from symbology)
    records_by_symbol: Dict[str, List] = {}

    for idx, row in df.iterrows():
        instrument_id = int(row.get('instrument_id', 0))
        symbol = instrument_to_symbol.get(instrument_id)

        if not symbol:
            continue

        if symbol not in records_by_symbol:
            records_by_symbol[symbol] = []

        records_by_symbol[symbol].append(row)

    # Choose front contract
    front_symbol = choose_front_contract(records_by_symbol, instrument_to_symbol)

    if not front_symbol:
        log("  No valid front contract found")
        return 0

    # Filter to front contract only
    df_front = df[df.index.map(lambda idx: instrument_to_symbol.get(int(df.loc[idx, 'instrument_id']), '') == front_symbol)]

    if len(df_front) == 0:
        log(f"  No bars for front contract {front_symbol}")
        return 0

    log(f"  Front contract {front_symbol}: {len(df_front):,} bars")

    # Convert to 1-minute bars
    rows_1m: List[Tuple] = []

    for ts_event, row in df_front.iterrows():
        # ts_event is already a pandas Timestamp (UTC)
        ts_utc = ts_event.to_pydatetime()
        ts_iso = ts_utc.isoformat()

        rows_1m.append((
            ts_iso,                  # ts_utc
            SYMBOL,                  # logical symbol (continuous)
            front_symbol,            # source_symbol (actual contract)
            float(row['open']),
            float(row['high']),
            float(row['low']),
            float(row['close']),
            int(row['volume']),
        ))

    # Insert bars
    inserted = upsert_bars_1m(con, rows_1m)
    log(f"  Inserted/replaced {inserted:,} bars")

    # Rebuild 5m bars (use first/last ts for range)
    if rows_1m:
        first_ts = datetime.fromisoformat(rows_1m[0][0])
        last_ts = datetime.fromisoformat(rows_1m[-1][0])

        # Expand range to cover full 5m buckets
        start_bucket = datetime.fromtimestamp((first_ts.timestamp() // 300) * 300, tz=TZ_UTC)
        end_bucket = datetime.fromtimestamp(((last_ts.timestamp() // 300) + 1) * 300, tz=TZ_UTC)

        rebuild_5m_from_1m(con, start_bucket, end_bucket)

    return inserted


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_databento_dbn_mpl.py <path_to_dbn_folder>")
        print("Example: python scripts/ingest_databento_dbn_mpl.py MPL")
        sys.exit(1)

    dbn_folder = Path(sys.argv[1])

    if not dbn_folder.exists() or not dbn_folder.is_dir():
        print(f"ERROR: Folder not found: {dbn_folder}")
        sys.exit(1)

    log(f"MPL Databento Ingestion - Folder: {dbn_folder}")

    # Connect to database
    con = duckdb.connect(DB_PATH)

    try:
        # Initialize tables
        init_mpl_tables(con)

        # Load symbology mapping
        instrument_to_symbol = load_symbology_mapping(dbn_folder)

        # Find all DBN files
        dbn_files = sorted(dbn_folder.glob("*.dbn*"))

        if not dbn_files:
            log("ERROR: No DBN files found")
            sys.exit(1)

        log(f"Found {len(dbn_files)} DBN files")

        # Process each file
        total_bars = 0
        for dbn_path in dbn_files:
            bars = process_dbn_file(dbn_path, con, instrument_to_symbol)
            total_bars += bars

        log(f"DONE: Total bars inserted: {total_bars:,}")

        # Show summary
        result = con.execute("SELECT COUNT(*) FROM bars_1m_mpl WHERE symbol = ?", [SYMBOL]).fetchone()
        log(f"Database now contains {result[0]:,} MPL 1m bars")

        result = con.execute("SELECT COUNT(*) FROM bars_5m_mpl WHERE symbol = ?", [SYMBOL]).fetchone()
        log(f"Database now contains {result[0]:,} MPL 5m bars")

    finally:
        con.close()


if __name__ == "__main__":
    main()
