"""Run as a separate always-on service: python inventory_worker.py."""
import logging
import signal
from threading import Event
from inventory_monitor import scan_inventory
from video_service import process_one_video
import time

stop = Event()
def shutdown(*_):
    stop.set()

def main():
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    next_scan=0
    while not stop.is_set():
        try:
            if time.monotonic()>=next_scan:
                scan_inventory()
                next_scan=time.monotonic()+60
        except Exception:
            # Do not print tokens, provider responses or connection URLs.
            logging.error('Inventory scan failed; retrying in 60 seconds')
        try:
            had_video=process_one_video()
        except Exception:
            had_video=False
            logging.error('Video queue unavailable; retrying shortly')
        if not had_video:
            stop.wait(5)

if __name__ == '__main__':
    main()
