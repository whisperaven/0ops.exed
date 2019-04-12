# (c) 2016, Hao Feng <whisperaven@gmail.com>

import sys
import logging

from celery import bootsteps

from exe.exc import ConfigError
from exe.utils.cfg import cfgread
from exe.utils.err import excinst 

from .context import Context

LOG = logging.getLogger(__name__)


## Celery Worker Helpers ##
def celery_initialize(c):
    """ Initialize and configure celery instance using runner's configuration. """
    cfg = Context().cfg

    c.conf.update(
        broker_url=cfg.broker_url,
        result_backend=cfg.redis_url
    )


def celery_worker_arguments(parser):
    """ Handle exe arguments when celery worker start. """
    parser.add_argument('--exe-conf',
                        action="store",
                        required=True,
                        default="",
                        help="path to config file of exed service, " +
                             "we need parse it before start celery worker")


class CeleryWorkerInit(bootsteps.Step):
    """ Hook for parse exe configration file before celery worker start.

    Note that: Celery will init `Runners` before invoke this one.
    """

    def __init__(self, worker, exe_conf="", **options):
        try:
            if not exe_conf:
                raise ConfigError(
                    "no config file given, need parse exe "
                    "conf before start celery worker")
            cfgread(exe_conf)
            celery_initialize(worker.app)
        except ConfigError:
            LOG.error(
                "can not initialize celery instance, got error while "
                "try to parse config file, {0}".format(excinst()))
            sys.exit(1)
