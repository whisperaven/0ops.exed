# -*- coding: utf-8 -*-

import logging
import multiprocessing

import redis
import celery

from exe.cfg import CONF
from exe.cfg import ModuleOpts
from exe.exc import ConfigError, ExecutorPrepareError, ReleaseNotSupportedError
from exe.release import ReleaseHandlerPrototype, HANDLERS
from exe.executor import ExecutorPrototype, AnsibleExecutor, EXECUTORS
from exe.utils.err import excinst
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
    """ 
    Context Object which provide some runtime context for each runner, including
        ConfigurationContext, RedisAccess, CeleryAsyncContext, RunnerAccess for 
        both runner object and endpoint handler object.

    All Runner should be subclass of this class with thier own `__RUNNER_NAME__`
        and `__RUNNER_MUTEX_REQUIRED__` attribute.
    """

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
        """ Configuration context access for runner and celery. """
        if self._cfg == None:
            try:
                self._cfg = CONF.runner
                LOG.info("configuration of <runner> loaded")
            except ConfigError:
                self._cfg = ModuleOpts("", DEFAULT_CONF)
                LOG.info("no configuration found for <runner>, load default options")
            self._cfg.merge(DEFAULT_CONF)
            LOG.info("configuration of <runner> mearged")
        return self._cfg

    @property
    def concurrency(self):
        """ Concurrency setting for runner and celery. """
        if self._concurrency == None:
            _concurrency = self._cfg.concurrency
            if not _concurrency:
                _concurrency = DEFAULT_CONCURRENCY
            self._concurrency = _concurrency
            LOG.info("concurrency setting of <runner> loaded, value is {0}".format(_concurrency))
        return self._concurrency

    @property
    def runner_name(self):
        """ For runner subclass get their own name. """
        return self.__RUNNER_NAME__

    @property
    def runner_mutex(self):
        """ For runner subclass get their own mutex attr. """
        return self.__RUNNER_MUTEX_REQUIRED__

    @property
    def redis(self):
        """ For runner subclass redis access. """
        if not self._rpool:
            self._rpool = redis.ConnectionPool.from_url(url=self.cfg.redis_url)
            LOG.info("redis connection pool <{0}> created".format(self._rpool))
        return redis.Redis(connection_pool=self._rpool)

    @property
    def release_plugins(self):
        """ For runner subclass access release handler plugins. """
        if self._release_plugins == None:
            self._release_plugins = []
            plugins = PluginLoader(ReleaseHandlerPrototype, self.cfg.modules).plugins
            plugins += HANDLERS
            for RH in plugins:
                self._release_plugins.append(RH)
            LOG.info("release handler plugin loaded via PluginLoader")
        return self._release_plugins

    def release_plugin(self, apptype):
        """ For runner subclass access release handler plugin. """
        for RH in self.release_plugins:
            if RH.htype() == apptype:
                return RH
        return None

    def executor(self, targets=[]):
        """ For runner subclass access executor plugin. """
        if self._executor_plugin == None:
            plugins = PluginLoader(ExecutorPrototype, self.cfg.modules).plugins
            plugins += EXECUTORS
            for EXECUTOR in plugins:
                if EXECUTOR.name() == self.cfg.executor:
                    self._executor_plugin = EXECUTOR
                    LOG.info("using executor: <{0}>".format(EXECUTOR.name()))
                    break
            if self._executor_plugin == None:
                raise ConfigError("executor plugin <{0}> could not be loaded".format(self.cfg.executor))
        if self._executor_plugin_opts == None:
            try:
                self._executor_plugin_opts = CONF.module(self.cfg.executor)
                LOG.info("executor plugin opts of <{0}> loaded".format(self.cfg.executor))
            except ConfigError:
                self._executor_plugin_opts = {}
                LOG.warning("no executor opts configuration found for plugin <0>".format(self.cfg.executor))
        try:
            return self._executor_plugin(targets, **self._executor_plugin_opts.dict_opts)
        except TypeError:
            raise ExecutorPrepareError("{0} bad executor implementate.".format(excinst()))
