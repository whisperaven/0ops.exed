# -*- coding: utf-8 -*-

import logging
import multiprocessing

import redis
import celery

from exe.cfg import CONF
from exe.cfg import ModuleOpts
from exe.exc import ConfigError, ReleaseNotSupportedError
from exe.release import ReleaseHandlerPrototype, HANDLERS
from exe.executor import ExecutorPrototype, AnsibleExecutor, EXECUTORS
from exe.utils.loader import PluginLoader

LOG = logging.getLogger(__name__)


## Consts ##
DEFAULT_CONCURRENCY = multiprocessing.cpu_count()
DEFAULT_CONF = {
    'redis_url'     : "redis://localhost",
    'broker_url'    : "amqp://guest:guest@localhost:5672//",
    'executor'      : "ansible",    # default executor
    'concurrency'   : DEFAULT_CONCURRENCY,
    'modules'       : ""
}


class Context(celery.Task):

    __RUNNER_NAME__ = None
    __RUNNER_MUTEX_REQUIRED__ = False

    def __init__(self):
        """ 
        Init Context for each Runner, which provide some context data
                like config infomations or plugins.
        
        When celery worker starts,
            The `Context` will be created by celery worker initialize the
            runner instances before execute `CeleryWorkerInit`, which means
            the `cfgread` has not run and `CONF` struct will be empty here.

        So that, everything here is Lazy evaluation.
        """
        self._cfg = None
        self._rpool = None
        self._concurrency = None
        self._executor = None
        self._executor_opts = None
        self._release_handlers = None

    @property
    def cfg(self):
        if self._cfg == None:
            try:
                self._cfg = CONF.runner
            except ConfigError:
                self._cfg = ModuleOpts("", DEFAULT_CONF)
            self._cfg.merge(DEFAULT_CONF)
        return self._cfg

    @property
    def concurrency(self):
        if self._concurrency == None:
            _concurrency = self._cfg.concurrency
            if not _concurrency:
                _concurrency = DEFAULT_CONCURRENCY
            self._concurrency = _concurrency
        return self._concurrency

    @property
    def runner_name(self):
        return self.__RUNNER_NAME__

    @property
    def runner_mutex(self):
        return self.__RUNNER_MUTEX_REQUIRED__

    @property
    def redis(self):
        if not self._rpool:
            self._rpool = redis.ConnectionPool.from_url(url=self.cfg.redis_url)
        return redis.Redis(connection_pool=self._rpool)

    @property
    def release_handlers(self):
        if self._release_handlers == None:
            self._release_handlers = []
            for RH in PluginLoader(ReleaseHandlerPrototype, self.cfg.modules).modules:
                self._release_handlers.append(RH)
            for RH in HANDLERS:
                self._release_handlers.append(RH)
        return self._release_handlers

    def executor(self, targets=[]):
        if self._executor == None:
            _executors = PluginLoader(ExecutorPrototype, self.cfg.modules).modules
            _executors += EXECUTORS
            for EXECUTOR in _executors:
                if EXECUTOR.name() == self.cfg.executor:
                    self._executor = EXECUTOR
                    LOG.info("using executor: <{0}>".format(EXECUTOR.name()))
                    break
            if self._executor == None:
                raise ConfigError("executor <{0}> could not be loaded".format(self.cfg.executor))
        if not self._executor_opts:
            self._executor_opts = CONF.module(self.cfg.executor)
        return self._executor(targets, **self._executor_opts.dict_opts)

    def release_handler(self, apptype):
        for RH in HANDLERS:
            if RH.htype() == apptype:
                return RH
        return None
