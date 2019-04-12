# (c) 2016, Hao Feng <whisperaven@gmail.com>

import logging

from exe.api import APIServer
from exe.runner import AsyncRunner, celery_initialize
from exe.exc import ConfigError
from exe.utils.log import bootstrap_logger
from exe.utils.err import excinst

from .consts import *
from .parse import exe_argparse, exe_cfgparse
from .parse import exe_logger_cfgparse, exe_logger_initialize


LOG = logging.getLogger(__name__)


def cli_main():
    bootstrap_logger()
    
    try:
        args = exe_argparse()

        if args.show_version:
            cli_show_version(args)
            return 0

        cf = exe_cfgparse(args.conf)
        logcf = exe_logger_cfgparse()
        access_log = exe_logger_initialize(logcf)

        celery_initialize(AsyncRunner)
        api = APIServer()
        api.set_access_log(access_log)

    except ConfigError:
        LOG.error("error while try to parse config file, {0}".format(excinst()))
        return 1

    return api.run(args.daemon)


def cli_show_version(args):
    from exe import __version__
    print("exed version: {0}".format(__version__))
    print("\tconfiguration file path: {0}".format(args.conf))
