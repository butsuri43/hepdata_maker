# bautify logging

import logging
from rich.logging import RichHandler
import rich.traceback
rich.traceback.install()

def set_default_logger(log_level="INFO"):
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
        force=True
    )
