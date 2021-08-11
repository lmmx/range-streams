import logging

__all__ = ["log", "set_up_logging"]

log = logging.getLogger()  # Provided for ease of access in other modules


def set_up_logging(quiet: bool = True):
    """
    Initialise the log

    Args:
      quiet : Change this flag to True/False to turn off/on console logging
    """
    log.setLevel(logging.DEBUG)
    log_format = logging.Formatter("[%(asctime)s] [%(levelname)s] - %(message)s")
    if not quiet:
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console.setFormatter(log_format)
        log.addHandler(console)
