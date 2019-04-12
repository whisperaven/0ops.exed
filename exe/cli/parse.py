# (c) 2016, Hao Feng <whisperaven@gmail.com>

import os
import os.path
import argparse

from exe.exc import ConfigError
from exe.utils.err import excinst
from exe.utils.cfg import CONF, ModuleOpts, cfgread
from exe.utils.log import initialize_logger, open_logfile

from .consts import *


## Consts ##
DEFAULT_LOG_CONF = {
    'log_level': "INFO",
    'error_log': "",
    'access_log': "",
}


def exe_argparse():
    parser = argparse.ArgumentParser(
        description='EXEd - remote execution service of 0ops')
    parser.add_argument('-v',
                        "--version",
                        dest="show_version",
                        action="store_true",
                        required=False, default=False,
                        help="show current version and exit")
    parser.add_argument('-c',
                        "--conf",
                        dest="conf",
                        action="store", 
                        required=False,
                        default=os.path.join(os.getcwd(), DEFAULT_CONFIG_FILE),
                        help="path to config file (default: $cwd/{0}".format(DEFAULT_CONFIG_FILE))
    parser.add_argument('-d',
                        "--daemon",
                        dest="daemon",
                        action="store_true",
                        required=False, default=False,
                        help="run api server as daemon (default: run frontground)")
    return parser.parse_args()


def exe_cfgparse(config_file):
    return cfgread(config_file)


def exe_logger_cfgparse():
    try:
        _cfg = CONF.log
        _cfg.merge(DEFAULT_LOG_CONF)
    except ConfigError:
        _cfg = ModuleOpts("", DEFAULT_LOG_CONF)
    return _cfg


def exe_logger_initialize(logcf):
    try:
        initialize_logger(logcf.error_log, logcf.log_level)
        return open_logfile(logcf.access_log)
    except IOError:
        raise ConfigError(
            "cannot open logfile for write, \"{0}\"".format(excinst()))
    except ValueError:
        raise ConfigError("invalid log level")
