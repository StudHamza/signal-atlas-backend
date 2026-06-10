import os
import select
import sys
import time

import psycopg2
import psycopg2.extensions

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.coverage_processor import process_pending_readings

DATABASE_URL = os.getenv("DATABASE_URL")
LISTEN_TIMEOUT = 30


def run_worker():
    print("Coverage worker started (LISTEN/NOTIFY mode)...")

    conn = _connect_and_listen()

    while True:
        try:
            process_pending_readings()

            if select.select([conn], [], [], LISTEN_TIMEOUT) == ([], [], []):
                continue

            conn.poll()
            while conn.notifies:
                conn.notifies.pop(0)

        except Exception as e:
            print(f"[WORKER ERROR] {e}")
            conn = _reconnect_and_listen(conn)


def _connect_and_listen():
    conn = psycopg2.connect(DATABASE_URL)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    with conn.cursor() as cur:
        cur.execute("LISTEN new_readings")
    print("Listening on 'new_readings' channel...")
    return conn


def _reconnect_and_listen(old_conn):
    try:
        if not old_conn.closed:
            old_conn.close()
    except Exception:
        pass

    time.sleep(1)
    return _connect_and_listen()


if __name__ == "__main__":
    run_worker()
