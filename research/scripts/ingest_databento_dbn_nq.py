"""
Ingest Databento DBN files for NQ (Nasdaq futures) into DuckDB
===============================================================

Reads local .dbn.zst files and creates:
  - bars_1m_nq (1-minute OHLCV bars)
  - bars_5m_nq (5-minute aggregated bars)

NO LOOKAHEAD: All timestamps converted to UTC+10 (Brisbane) consistently
Contract handling: Selects most liquid front contract (highest volume, no spreads)

Usage:
  python scripts/ingest_databento_dbn_nq.py <path_to_dbn_folder>

  Example:
  python scripts/ingest_databento_dbn_nq.py NQ
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
SYMBOL = "NQ"  # Logical continuous symbol
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


def init_nq_tables(con: duckdb.DuckDBPyConnection):
    """Create NQ-specific tables if they don't exist"""
    log("Initializing NQ tables...")

    # Create bars_1m_nq
    con.execute("""
        CREATE TABLE IF NOT EXISTS bars_1m_nq (
          ts_utc        TIMESTAMPTZ NOT NULL,
          symbol        TEXT NOT NULL,          -- logical symbol 'NQ'
          source_symbol TEXT,                   -- actual contract 'NQH5', 'NQM5', etc
          open          DOUBLE NOT NULL,
          high          DOUBLE NOT NULL,
          low           DOUBLE NOT NULL,
          close         DOUBLE NOT NULL,
          volume        BIGINT NOT NULL,
          PRIMARY KEY (symbol, ts_utc)
        );
    """)

    # Create bars_5m_nq
    con.execute("""
        CREATE TABLE IF NOT EXISTS bars_5m_nq (
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

    log("NQ tables ready")


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

    # Filter NQ contracts only, exclude spreads (contain '-')
    nq_outrights = {}
    for sym, recs in records_by_symbol.items():
        if not sym:
            continue
        # NQ contracts: NQH5, NQM5, NQU5, NQZ5, NQH6, etc
        if sym.startswith('NQ') and '-' not in sym and len(sym) <= 5:
            nq_outrights[sym] = recs

    if not nq_outrights:
        return None

    # Sum volume per symbol
    volume_by_symbol = {}
    for sym, recs in nq_outrights.items():
        total_vol = sum(getattr(rec, 'volume', 0) for rec in recs)
        volume_by_symbol[sym] = total_vol

    # Return symbol with highest volume
    if not volume_by_symbol:
        return None

    front_symbol = max(volume_by_symbol.items(), key=lambda x: x[1])[0]
    return front_symbol


def ingest_dbn_file(
    dbn_path: Path,
    con: duckdb.DuckDBPyConnection,
    instrument_to_symbol: Dict[int, str]
) -> Tuple[int, int]:
    """
    Ingest a single DBN file into bars_1m_nq

    Returns:
        (bars_inserted, unique_contracts)
    """
    log(f"Reading DBN: {dbn_path.name}")

    store = db.DBNStore.from_file(dbn_path)

    log(f"  Schema: {store.schema}")
    log(f"  Dataset: {store.dataset}")

    # Group records by 1-minute bucket and by symbol
    # We need to choose front contract per bucket
    buckets: Dict[datetime, Dict[str, List]] = {}  # timestamp -> symbol -> records

    log("  Parsing records...")
    record_count = 0
    unmapped_count = 0

    for rec in store:
        # Get timestamp (UTC)
        ts_utc = ts_event_to_datetime(rec.ts_event)

        # Bucket to 1-minute
        # Floor to minute: 2025-01-12 09:00:00, 09:01:00, etc
        ts_bucket = ts_utc.replace(second=0, microsecond=0)

        # Get symbol via instrument_id
        instrument_id = getattr(rec, 'instrument_id', None)
        if instrument_id is None:
            unmapped_count += 1
            continue

        symbol = instrument_to_symbol.get(instrument_id)
        if not symbol:
            unmapped_count += 1
            continue

        # Store record
        if ts_bucket not in buckets:
            buckets[ts_bucket] = {}
        if symbol not in buckets[ts_bucket]:
            buckets[ts_bucket][symbol] = []
        buckets[ts_bucket][symbol].append(rec)

        record_count += 1
        if record_count % 100000 == 0:
            log(f"    Processed {record_count:,} records...")

    log(f"  Total records: {record_count:,}")
    if unmapped_count > 0:
        log(f"  Unmapped records (no symbol): {unmapped_count:,}")
    log(f"  Unique 1-minute buckets: {len(buckets):,}")

    # For each bucket, choose front contract and aggregate
    log("  Aggregating and choosing front contracts...")
    rows_1m: List[Tuple] = []
    unique_contracts = set()

    for ts_bucket in sorted(buckets.keys()):
        records_by_symbol = buckets[ts_bucket]

        # Choose front contract for this minute
        front_symbol = choose_front_contract(records_by_symbol, instrument_to_symbol)
        if not front_symbol:
            continue

        unique_contracts.add(front_symbol)

        # Get records for front contract
        front_records = records_by_symbol[front_symbol]

        # Aggregate OHLCV for this minute
        # Databento OHLCV has prices in fixed-point (multiplied by 1e9 for NQ)
        # Need to divide by 1e9 to get actual price

        opens = [rec.open / 1e9 for rec in front_records]
        highs = [rec.high / 1e9 for rec in front_records]
        lows = [rec.low / 1e9 for rec in front_records]
        closes = [rec.close / 1e9 for rec in front_records]
        volumes = [getattr(rec, 'volume', 0) for rec in front_records]

        # Take first open, max high, min low, last close, sum volume
        bar_open = opens[0]
        bar_high = max(highs)
        bar_low = min(lows)
        bar_close = closes[-1]
        bar_volume = sum(volumes)

        rows_1m.append((
            ts_bucket,            # ts_utc
            SYMBOL,               # symbol (logical 'NQ')
            front_symbol,         # source_symbol (actual contract)
            float(bar_open),
            float(bar_high),
            float(bar_low),
            float(bar_close),
            int(bar_volume)
        ))

    log(f"  Aggregated {len(rows_1m):,} 1-minute bars")
    log(f"  Unique contracts: {len(unique_contracts)} - {sorted(unique_contracts)[:10]}")

    # Sample a few bars to verify data looks reasonable
    if rows_1m:
        log(f"  Sample bar (first): ts={rows_1m[0][0]}, O={rows_1m[0][3]:.2f}, H={rows_1m[0][4]:.2f}, L={rows_1m[0][5]:.2f}, C={rows_1m[0][6]:.2f}, V={rows_1m[0][7]}")
        if len(rows_1m) > 1:
            log(f"  Sample bar (last):  ts={rows_1m[-1][0]}, O={rows_1m[-1][3]:.2f}, H={rows_1m[-1][4]:.2f}, L={rows_1m[-1][5]:.2f}, C={rows_1m[-1][6]:.2f}, V={rows_1m[-1][7]}")

    # Insert into bars_1m_nq
    if rows_1m:
        log("  Inserting into bars_1m_nq...")
        con.executemany("""
            INSERT OR REPLACE INTO bars_1m_nq
            (ts_utc, symbol, source_symbol, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, rows_1m)
        log(f"  Inserted {len(rows_1m):,} rows into bars_1m_nq")

    return len(rows_1m), len(unique_contracts)


def build_5m_from_1m(
    con: duckdb.DuckDBPyConnection,
    start_ts: Optional[datetime] = None,
    end_ts: Optional[datetime] = None
):
    """
    Build bars_5m_nq from bars_1m_nq deterministically

    Args:
        con: Database connection
        start_ts: Optional start timestamp (UTC) - if None, rebuild all
        end_ts: Optional end timestamp (UTC) - if None, rebuild all
    """
    log("Building bars_5m_nq from bars_1m_nq...")

    # Delete existing 5m bars in range if specified
    if start_ts and end_ts:
        con.execute("""
            DELETE FROM bars_5m_nq
            WHERE symbol = ?
              AND ts_utc >= ?
              AND ts_utc < ?
        """, [SYMBOL, start_ts, end_ts])
        log(f"  Deleted existing 5m bars in range")
    else:
        # Rebuild all - delete everything
        con.execute("DELETE FROM bars_5m_nq WHERE symbol = ?", [SYMBOL])
        log(f"  Deleted all existing 5m bars for NQ")

    # Aggregate 1m -> 5m
    # Bucket: floor(epoch(ts)/300)*300
    where_clause = "WHERE symbol = ?"
    params = [SYMBOL]

    if start_ts and end_ts:
        where_clause += " AND ts_utc >= ? AND ts_utc < ?"
        params.extend([start_ts, end_ts])

    result = con.execute(f"""
        INSERT INTO bars_5m_nq (ts_utc, symbol, source_symbol, open, high, low, close, volume)
        SELECT
            CAST(to_timestamp(floor(epoch(ts_utc) / 300) * 300) AS TIMESTAMPTZ) AS ts_5m,
            symbol,
            NULL AS source_symbol,
            arg_min(open, ts_utc)  AS open,
            max(high)              AS high,
            min(low)               AS low,
            arg_max(close, ts_utc) AS close,
            sum(volume)            AS volume
        FROM bars_1m_nq
        {where_clause}
        GROUP BY 1, 2
        ORDER BY 1
    """, params)

    rows_5m = con.execute("SELECT COUNT(*) FROM bars_5m_nq WHERE symbol = ?", [SYMBOL]).fetchone()[0]
    log(f"  bars_5m_nq now has {rows_5m:,} rows")


def ingest_folder(dbn_folder: Path, con: duckdb.DuckDBPyConnection):
    """
    Ingest all .dbn or .dbn.zst files in folder
    """
    # Load symbology mapping first
    instrument_to_symbol = load_symbology_mapping(dbn_folder)

    if not instrument_to_symbol:
        log("ERROR: No symbology mappings loaded - cannot ingest")
        return

    dbn_files = list(dbn_folder.glob("*.dbn")) + list(dbn_folder.glob("*.dbn.zst"))

    if not dbn_files:
        log(f"ERROR: No .dbn or .dbn.zst files found in {dbn_folder}")
        return

    log(f"Found {len(dbn_files)} DBN file(s) to ingest")

    total_bars = 0
    all_contracts = set()

    for dbn_file in sorted(dbn_files):
        bars, contracts = ingest_dbn_file(dbn_file, con, instrument_to_symbol)
        total_bars += bars

    log(f"\nIngestion complete:")
    log(f"  Total 1-minute bars: {total_bars:,}")

    # Build 5-minute bars
    if total_bars > 0:
        build_5m_from_1m(con)

    # Final counts
    count_1m = con.execute("SELECT COUNT(*) FROM bars_1m_nq WHERE symbol = ?", [SYMBOL]).fetchone()[0]
    count_5m = con.execute("SELECT COUNT(*) FROM bars_5m_nq WHERE symbol = ?", [SYMBOL]).fetchone()[0]

    log(f"\nFinal database counts:")
    log(f"  bars_1m_nq: {count_1m:,}")
    log(f"  bars_5m_nq: {count_5m:,}")

    # Date range
    date_range = con.execute("""
        SELECT MIN(ts_utc), MAX(ts_utc)
        FROM bars_1m_nq
        WHERE symbol = ?
    """, [SYMBOL]).fetchone()

    if date_range[0]:
        log(f"\nDate range (UTC):")
        log(f"  Start: {date_range[0]}")
        log(f"  End:   {date_range[1]}")

        # Convert to local
        start_local = ts_to_local(date_range[0])
        end_local = ts_to_local(date_range[1])
        log(f"\nDate range (Brisbane UTC+10):")
        log(f"  Start: {start_local}")
        log(f"  End:   {end_local}")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    dbn_folder = Path(sys.argv[1])

    if not dbn_folder.exists():
        log(f"ERROR: Folder not found: {dbn_folder}")
        sys.exit(1)

    if not dbn_folder.is_dir():
        log(f"ERROR: Not a directory: {dbn_folder}")
        sys.exit(1)

    log(f"NQ DBN Ingestion Started")
    log(f"  DBN folder: {dbn_folder.absolute()}")
    log(f"  Database: {DB_PATH}")
    log(f"  Timezone: {TZ_LOCAL}")
    log("")

    # Connect to database
    con = duckdb.connect(DB_PATH)

    try:
        # Initialize tables
        init_nq_tables(con)

        # Ingest DBN files
        ingest_folder(dbn_folder, con)

        log("\n[OK] Ingestion complete!")

    except Exception as e:
        log(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        con.close()


if __name__ == "__main__":
    main()
