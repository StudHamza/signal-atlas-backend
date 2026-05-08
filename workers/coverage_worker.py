import time
from services.coverage_processor import process_pending_readings

POLL_INTERVAL_SECONDS = 5

def run_worker():
    print("Coverage worker started...")

    while True:
        try:
            process_pending_readings()
        except Exception as e:
            print(f"[WORKER ERROR] {e}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_worker()
