# -*- coding: utf-8 -*-

import sys
import logging

from exe.api import APIServer
from exe.runner import AsyncRunner, AsyncWorker
from exe.exc import ConfigError
from exe.utils.log import logger_bootstrap
from exe.utils.err import errno

from .consts import *
from .parse import exe_argparse, exe_cfgparse, exe_logprepare, exe_accesslog

LOG = logging.getLogger(__name__)


def exe_main():

    logger_bootstrap()

    args = exe_argparse()
    try:
        exe_cfgparse(args.conf)
        exe_logprepare()
        if args.run_as == API_SERVER:
            server = APIServer()
            server.logger_init(exe_accesslog())
        else:
            server = AsyncWorker(AsyncRunner)
    except ConfigError:
        LOG.error("error while try to parse config file, {0}".format(errno()))
        sys.exit(1)

    server.run(args.daemon)
