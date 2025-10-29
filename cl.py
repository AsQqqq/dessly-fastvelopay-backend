from cololog import cololog
import logging


logger = cololog(
    __name__,
    path_print=False,
    log_to_file=True,
    log_dir="logs",
    console_level=logging.DEBUG
)