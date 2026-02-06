import logging

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s|%(funcName)s: %(message)s"

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        datefmt="%d|%H:%M:%S"
    )
