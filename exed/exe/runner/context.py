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
        self._cfg = None            # runner config
        self._rpool = None          # redis connection pool
        self._concurrency = None    # concurrency opts
        self._release_plugins = None
        self._executor_plugin = None
        self._executor_plugin_opts = None

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
    def release_plugins(self):
        if self._release_plugins == None:
            self._release_plugins = []
            for RH in PluginLoader(ReleaseHandlerPrototype, self.cfg.modules).modules + HANDLERS:
                self._release_plugins.append(RH)
        return self._release_plugins

    def executor(self, targets=[]):
        if self._executor_plugin == None:
            _executor_plugins = PluginLoader(ExecutorPrototype, self.cfg.modules).modules + EXECUTORS
            for EXECUTOR in _executor_plugins:
                if EXECUTOR.name() == self.cfg.executor:
                    self._executor_plugin = EXECUTOR
                    LOG.info("using executor: <{0}>".format(EXECUTOR.name()))
                    break
            if self._executor_plugin == None:
                raise ConfigError("executor plugin <{0}> could not be loaded".format(self.cfg.executor))
        if self._executor_plugin_opts == None:
            try:
                self._executor_plugin_opts = CONF.module(self.cfg.executor)
            except ConfigError:
                self._executor_plugin_opts = {}
                LOG.warning("no executor opts config found, {0}".format(errno()))
        return self._executor_plugin(targets, **self._executor_plugin_opts.dict_opts)

    def release_plugin(self, apptype):
        for RH in self.release_plugins:
            if RH.htype() == apptype:
                return RH
        return None
