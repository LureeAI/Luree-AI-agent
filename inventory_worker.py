"""Run as a separate always-on service: python inventory_worker.py."""
import logging
import signal
from threading import Event
from inventory_monitor import scan_inventory

stop = Event()
def shutdown(*_):
    stop.set()

def main():
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    while not stop.is_set():
        try:
            scan_inventory()
        except Exception:
            # Do not print tokens, provider responses or connection URLs.
            logging.error('Inventory scan failed; retrying in 60 seconds')
        stop.wait(60)

if __name__ == '__main__':
    main()

