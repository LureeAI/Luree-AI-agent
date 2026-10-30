"""Portable worker: python advertising_worker.py. No paid model calls or ad writes."""
import logging
import signal
from threading import Event
from advertising_sync import process_one_sync
from marketing_manager import schedule_monitoring
import time


def main():
    stop=Event()
    signal.signal(signal.SIGTERM,lambda *_:stop.set())
    signal.signal(signal.SIGINT,lambda *_:stop.set())
    logging.basicConfig(level=logging.INFO)
    next_monitor=0
    while not stop.is_set():
        if time.monotonic()>=next_monitor:
            try:schedule_monitoring()
            except Exception:logging.error('Marketing monitor unavailable')
            next_monitor=time.monotonic()+60
        try:
            worked=process_one_sync()
        except Exception:
            logging.error('Advertising database unavailable; retrying shortly')
            worked=False
        if not worked:
            stop.wait(10)


if __name__=='__main__':
    main()
