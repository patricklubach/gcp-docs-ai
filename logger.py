import logging

# ANSI color codes
RESET = "\033[0m"
COLORS = {
    "DEBUG":    "\033[94m",   # Blue
    "INFO":     "\033[92m",   # Green
    "WARNING":  "\033[93m",   # Yellow
    "ERROR":    "\033[31m",   # Red
    "CRITICAL": "\033[91m",   # Bright Red (bold)
}

class ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord):
        color = COLORS.get(record.levelname, RESET)
        record.levelname = f"{color}{record.levelname}{RESET}"
        record.msg = f"{color}{record.msg}{RESET}"
        return super().format(record)


def get_logger(name: str = __name__) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = ColorFormatter(
            fmt="%(asctime)s | %(levelname)s |  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

logger = get_logger()

# --- Usage ---
# if __name__ == "__main__":
#     log = get_logger("myapp")

#     log.debug("Starting up...")
#     log.info("Server is running on port 8080")
#     log.warning("Config file not found, using defaults")
#     log.error("Failed to connect to database")
#     log.critical("Out of memory — shutting down")
