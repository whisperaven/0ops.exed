# -*- coding: utf-8 -*-

import sys
import logging

from celery import bootsteps

from exe.cfg import cfgread
from exe.exc import ConfigError
from exe.utils.err import excinst 

from .context import Context

LOG = logging.getLogger(__name__)


## Celery Worker Helpers ##
def celery_init(c):
    """ Init/config celery instance using runner config. """

    ctx = Context()
    runner_cfg = ctx.cfg

    c.conf.update(
        worker_concurrency=ctx.concurrency,
        broker_url=runner_cfg.broker_url,
        result_backend=runner_cfg.redis_url
    )


def celery_worker_arguments(parser):
    parser.add_argument('--exe-conf', action="store", required=True, default="",
        help="path to config file of exed service, "
            "we need parse it before start celery worker.")


class CeleryWorkerInit(bootsteps.Step):
    """ Celery will init Runners before execute this one. """

    def __init__(self, worker, exe_conf="", **options):
        try:
            if not exe_conf:
                raise ConfigError("no config file given, "
                    "need parse exe conf before start celery worker.")
            cfgread(exe_conf)
            celery_init(worker.app)
        except ConfigError:
            LOG.error("error while try to parse config file, {0}".format(excinst()))
            sys.exit(1)

