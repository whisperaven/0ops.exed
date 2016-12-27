# -*- coding: utf-8 -*-

import sys
import logging

from exe.exc import ConfigError


## Consts ##
LOG_LEVEL_MAPPER = dict(
    DEBUG=logging.DEBUG,
    INFO=logging.INFO,
    WARNING=logging.WARNING,
    ERROR=logging.ERROR,
    CRITICAL=logging.CRITICAL)
LOG_LEVEL_DEFAULT = logging.INFO
LOG_FORMAT_DEFAULT = '%(asctime)-15s [%(levelname)s] %(message)s'


def logger_bootstrap():
    """ Init stream logger before the real logger really. """
    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(LOG_FORMAT_DEFAULT)

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(LOG_LEVEL_DEFAULT)


def logger_init(log_path="", log_level="", log_format=None):
    """ Open and config the root logger. """
    if not log_level:
        log_level = LOG_LEVEL_DEFAULT
    else:
        for name, level in LOG_LEVEL_MAPPER.iteritems():
            if name == log_level.upper():
                log_level = level
                break

    if log_format == None:
        log_format = LOG_FORMAT_DEFAULT
    formatter = logging.Formatter(log_format)

    if not log_path:
        handler = logging.StreamHandler(sys.stdout)
    else:
        handler = open_logfile(log_path)

    logger = logging.getLogger()
    for _handler in logger.handlers:
        logger.removeHandler(_handler)

    logger.addHandler(handler)
    logger.setLevel(log_level)
    handler.setFormatter(formatter)


def open_logfile(log_path=""):
    """ Return log handler by open log file. """
    if not log_path:
        handler = logging.StreamHandler(sys.stdout) 
    else:
        handler = logging.FileHandler(log_path, 'a', 'utf-8')
    handler.setLevel(logging.DEBUG)

    return handler
