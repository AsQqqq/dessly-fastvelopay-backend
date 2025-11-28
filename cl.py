import logging
import os
import inspect
from logging.handlers import RotatingFileHandler
from colorama import Fore, Style, init

# colorama init
init(autoreset=True)


level_map = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

DEFAULT_COLORS = {
    logging.DEBUG: Fore.CYAN,
    logging.INFO: Fore.GREEN,
    logging.WARNING: Fore.YELLOW,
    logging.ERROR: Fore.RED,
    logging.CRITICAL: Fore.MAGENTA,
}


class MyLogger:
    def __init__(
        self,
        name,
        level=["debug", "info", "warning", "error", "critical"],
        colors=None,
        path_print=True,
        log_to_file=True,
        log_dir="logs",
        log_file="log.log",
        console_level=logging.DEBUG,
        max_file_size_mb=10,
        backup_count=10,
    ):
        self.logger = logging.getLogger(name)

        # Уровни
        level_values = [level_map[l] for l in level if l in level_map]
        if not level_values:
            level_values = [logging.DEBUG]

        min_level = min(level_values)
        self.logger.setLevel(min_level)
        self.path_print = path_print

        self.colors = colors or DEFAULT_COLORS

        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

        # Файловое логирование
        if log_to_file:
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)

            file_path = os.path.join(log_dir, log_file)

            file_handler = RotatingFileHandler(
                file_path,
                maxBytes=max_file_size_mb * 1024 * 1024,
                backupCount=backup_count,
                encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(min_level)
            self.logger.addHandler(file_handler)

        # Консоль
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(console_level)
        self.logger.addHandler(console_handler)

    def _log(self, level, message, *args, **kwargs):
        # определяем место вызова
        frame = inspect.currentframe().f_back
        info = inspect.getframeinfo(frame)

        if self.path_print:
            message = f"{message} (в {info.filename}, строка {info.lineno})"

        color = self.colors.get(level, "")
        colored_msg = color + message + Style.RESET_ALL

        self.logger.log(level, colored_msg, *args, **kwargs)

    def debug(self, msg, *a, **kw):
        self._log(logging.DEBUG, msg, *a, **kw)

    def info(self, msg, *a, **kw):
        self._log(logging.INFO, msg, *a, **kw)

    def warning(self, msg, *a, **kw):
        self._log(logging.WARNING, msg, *a, **kw)

    def error(self, msg, *a, **kw):
        self._log(logging.ERROR, msg, *a, **kw)

    def critical(self, msg, *a, **kw):
        self._log(logging.CRITICAL, msg, *a, **kw)


logger = MyLogger(
    __name__,
    path_print=False,
    log_to_file=True,
    log_dir="logs",
    console_level=logging.DEBUG,
    max_file_size_mb=15,
    backup_count=20
)