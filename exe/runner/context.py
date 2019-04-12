# (c) 2016, Hao Feng <whisperaven@gmail.com>

import os
import os.path
import logging
import multiprocessing

import redis
import celery

from exe.exc import ConfigError, ExecutorPrepareError, TaskNotSupportedError
from exe.task import TaskRunnerPrototype, TASKRUNNERS
from exe.executor import ExecutorPrototype, EXECUTORS
from exe.utils.err import excinst
from exe.utils.cfg import CONF, ModuleOpts
from exe.utils.loader import PluginLoader


LOG = logging.getLogger(__name__)


## Consts ##
RUNNER_DEFAULT_CONF = {
    'redis_url'    : "redis://localhost",
    'broker_url'   : "amqp://guest:guest@localhost:5672//",
    'executor'     : "ansible",
    'modules'      : os.path.join(os.getcwd(), "modules"),
    'concurrency'  : multiprocessing.cpu_count(),
    'timeout'      : 0  # TODO: executor timeout
}


class Context(celery.Task):
    """ Context object that provide some runtime context for each runner.

    These context including Configuration, RedisAccess, and CeleryApp
    for both runner and endpoint handler object.

    All Runner classes should be a subclass of this class with thier
    own ``__RUNNER_NAME__`` and ``__RUNNER_MUTEX_REQUIRED__`` attribute.
    """

    __RUNNER_NAME__ = None
    __RUNNER_MUTEX_REQUIRED__ = False

    def __init__(self):
        """ Initialize Context for each Runner, which provide some context data
        like config infomations or plugins.
        
        When celery worker starts, the ``Context`` object will be created
        by celery worker, and initialize the runner instances before invoke
        ``__init__`` of ``CeleryWorkerInit``.

        Which means the ``cfgread`` has not yet invoked and ``CONF`` struct
        will be empty here.

        That why nothing initialized here until they got accessed.
        """
        self._cfg          = None   # runner config
        self._rpool        = None   # redis connection pool
        self._timeout      = None   # executor timeout opts
        self._concurrency  = None   # executor concurrency opts

        self._task_plugins         = None
        self._executor_plugin      = None
        self._executor_plugin_opts = None

    @property
    def cfg(self):
        """ Configuration context access for runner and celery. """
        if self._cfg == None:
            try:
                self._cfg = CONF.runner
                self._cfg.merge(RUNNER_DEFAULT_CONF)
                LOG.info("configuration of <runner> loaded & merged")
            except ConfigError:
                self._cfg = ModuleOpts("", RUNNER_DEFAULT_CONF)
                LOG.info("no configuration found for <runner>, "
                         "load default options")
        return self._cfg

    @property
    def concurrency(self):
        """ Concurrency setting for executor of runner. """
        if self._concurrency == None:
            self._concurrency = self._cfg.concurrency
            LOG.info("executor concurrency setting of <runner> loaded, "
                     "value is <{0}>".format(self._concurrency))
        return self._concurrency

    @property
    def timeout(self):
        """ Timeout setting for exector of runner. """
        if self._timeout == None:
            self._timeout = self._cfg.timeout
            LOG.info("executor timeout setting of <runner> loaded, "
                     "value is {0}".format(self._timeout))
        return self._timeout

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
            # https://github.com/andymccurdy/redis-py/issues/463#issuecomment-41229918
            self._rpool = redis.ConnectionPool.from_url(
                url=self.cfg.redis_url, decode_responses=True)
            LOG.info("redis connection pool <{0}> created".format(self._rpool))
        return redis.Redis(connection_pool=self._rpool)

    @property
    def task_plugins(self):
        """ For runner subclass access task runner plugin(s). """
        if self._task_plugins == None:
            self._task_plugins = []
            plugins = PluginLoader(
                TaskRunnerPrototype, self.cfg.modules).plugins
            plugins += TASKRUNNERS
            for tp in plugins:
                self._task_plugins.append(tp)
            LOG.info("total <{0}> task runner plugins loaded via "
                     "PluginLoader".format(len(plugins)))
        return self._task_plugins

    def task_plugin(self, tasktype):
        """ For runner subclass access task runner plugin. """
        for tp in self.task_plugins:
            if tp.runner_type() == tasktype:
                return tp
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
                raise ConfigError("executor plugin <{0}> could not "
                                  "be loaded".format(self.cfg.executor))

        if self._executor_plugin_opts == None:
            try:
                self._executor_plugin_opts = CONF.module(self.cfg.executor)
                LOG.info("executor plugin opts of <{0}> loaded, "
                         "content was <{1}>".format(self.cfg.executor,
                             self._executor_plugin_opts.dict_opts))
            except ConfigError:
                self._executor_plugin_opts = {}
                LOG.warning("no executor opts configuration founded for "
                            "plugin <0>".format(self.cfg.executor))
        try:
            return self._executor_plugin(
                targets, timeout=self.timeout, concurrency=self.concurrency,
                **self._executor_plugin_opts.dict_opts)
        except TypeError:
            raise ExecutorPrepareError("{0} bad executor"
                                       " implementate".format(excinst()))
