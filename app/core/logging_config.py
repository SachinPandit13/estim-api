import logging

def _logger_level(log_level: str = "INFO") -> int:
    if log_level.upper() == "DEBUG":
        return logging.DEBUG
    elif log_level.upper() == "INFO":
        return logging.INFO
    elif log_level.upper() == "WARNING":
        return logging.WARNING
    elif log_level.upper() == "ERROR":
        return logging.ERROR
    elif log_level.upper() == "CRITICAL":
        return logging.CRITICAL
    else:
        return logging.INFO

def setup_logger(name: str, log_level: str = "INFO"):
    logger = logging.getLogger(name)
    logger.setLevel(_logger_level(log_level))

    #prevent 
    logger.propagate = False

    if getattr(logger, "_estim_configured", False):
        return logger

    #create console handler
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger._estim_configured = True

    return logger
