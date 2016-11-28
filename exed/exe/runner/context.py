# -*- coding: utf-8 -*-

import redis
import celery

from exe.cfg import CONF
from exe.cfg import ModuleOpts
from exe.exc import ConfigError
from exe.executor import AnsibleExecutor as Executor


## Consts ##
DEFAULT_CONF = {
    'redis_url'     : "redis://localhost",
    'broker_url'    : "'amqp://guest:guest@localhost:5672//",
    'executor'      : "ansible",
    'concurrency'   : 0
}


class Context(celery.Task):

    __RUNNER_NAME__ = None
    __RUNNER_MUTEX_REQUIRED__ = False

    def __init__(self):

        try:
            self._cfg = CONF.runner
        except ConfigError:
            self._cfg = ModuleOpts("", DEFAULT_CONF)
        self._cfg.merge(DEFAULT_CONF)

        self._rpool = None
        self._executor_opts = CONF.module(self._cfg.executor)

    @property
    def cfg(self):
        return self._cfg

    @property
    def runner_name(self):
        return self.__RUNNER_NAME__

    @property
    def runner_mutex(self):
        return self.__RUNNER_MUTEX_REQUIRED__

    @property
    def redis(self):
        if not self._rpool:
            self._rpool = redis.ConnectionPool.from_url(url=self._cfg.redis_url)
        return redis.Redis(connection_pool=self._rpool)

    def executor(self, targets=[]):
        return Executor(targets, **self._executor_opts.dict_opts)

