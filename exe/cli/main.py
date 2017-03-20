# -*- coding: utf-8 -*-

import sys
import logging

from exe.api import APIServer
from exe.runner import AsyncRunner, celery_init
from exe.exc import ConfigError
from exe.utils.log import logger_bootstrap
from exe.utils.err import excinst

from .consts import *
from .parse import exe_argparse, exe_cfgparse
from .parse import exe_logger_cfgparse, exe_logger_init

LOG = logging.getLogger(__name__)


def exe_main():
    logger_bootstrap()
    
    try:
        args = exe_argparse()
        cf = exe_cfgparse(args.conf)
        logcf = exe_logger_cfgparse()
        access_log = exe_logger_init(logcf)

        celery_init(AsyncRunner)
        api = APIServer()
        api.set_access_log(access_log)

    except ConfigError:
        LOG.error("error while try to parse config file, {0}".format(excinst()))
        sys.exit(1)

    api.run(args.daemon)
