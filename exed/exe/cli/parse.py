# -*- coding: utf-8 -*-

import os
import os.path
import argparse

try:
    from ConfigParser import ConfigParser
except ImportError:
    from configparser import ConfigParser

from exe.cfg import CONF, ModuleOpts
from exe.exc import ConfigError
from exe.utils.err import errno
from exe.utils.log import logger_init, open_logfile

from .consts import *


## Consts ##
DEFAULT_CONF = {
    'log_level': "INFO",
    'error_log': "",
    'access_log': "",
    'worker_log': "",
}


def exe_argparse():

    parser = argparse.ArgumentParser(description='Zerops.Exed - ApiServer & Worker')
    parser.add_argument('-c', "--conf", dest="conf", action="store", 
            required=False, default=os.path.join(os.getcwd(), DEFAULT_CONFIG_FILE),
            help="path to config file (default: $cwd/{0}".format(DEFAULT_CONFIG_FILE))
    parser.add_argument('-d', "--daemon", dest="daemon", action="store_true", 
            required=False, default=False,
            help="run as daemon (default: run frontground)")
    parser.add_argument('run_as', action="store", choices=(API_SERVER, WORKER),
            help="run as {0} or {1}.".format(API_SERVER, WORKER))
    return parser.parse_args()


def exe_cfgparse(config_file):

    cfg = ConfigParser()
    if not hasattr(cfg, 'read_file'):
        cfg.read_file = cfg.readfp

    try:
        cfp = open(config_file)
        cfg.read_file(cfp)
        cfp.close()
    except:
        raise ConfigError("cannot open/read configfile, {0}".format(errno()))

    for _cs in cfg.sections():
        CONF.regisiter_opts(_cs, dict(zip(
            [ c[0] for c in cfg.items(_cs) ],
            [ c[1].strip('\'').strip('"') for c in cfg.items(_cs) ])))


def exe_logprepare():

    try:
        _cfg = CONF.log
    except ConfigError:
        _cfg = ModuleOpts("", DEFAULT_CONF)
    _cfg.merge(DEFAULT_CONF)

    logger_init(_cfg.error_log, _cfg.log_level)


def exe_accesslog():

    try:
        _cfg = CONF.log
    except ConfigError:
        _cfg = ModuleOpts("", DEFAULT_CONF)
    _cfg.merge(DEFAULT_CONF)

    return open_logfile(_cfg.access_log)
