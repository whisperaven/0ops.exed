# -*- coding: utf-8 -*-

import sys
import logging
import logging.handlers

from exe.exc import ConfigError
from exe.utils.err import errno

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


def logger_init(log_path="", log_level=LOG_LEVEL_DEFAULT, log_format=None):
    """ Open and config the root logger. """

    if log_format == None:
        log_format = LOG_FORMAT_DEFAULT

    level = None
    for name, _level in LOG_LEVEL_MAPPER.iteritems():
        if name == log_level.upper():
            level = _level
    if level == None:
        raise ConfigError("bad log level {0}".format(log_level))

    logger = logging.getLogger()
    formatter = logging.Formatter(log_format)

    if not log_path:
        handler = logging.StreamHandler(sys.stdout)
    else:
        handler = open_logfile(log_path)

    logger.addHandler(handler)
    logger.setLevel(LOG_LEVEL_DEFAULT)
    handler.setFormatter(formatter)


def open_logfile(log_path):
    """ Return log handler by open log file. """

    try:
        if not log_path:
            handler = logging.StreamHandler(sys.stdout) 
        else:
            handler = logging.handlers.WatchedFileHandler(log_path, 'a', 'utf-8')
    except IOError:
        raise ConfigError("cannot open log file, {0}".format(errno()))
    handler.setLevel(logging.DEBUG)

    return handler
