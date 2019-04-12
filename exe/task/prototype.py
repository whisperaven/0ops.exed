# (c) 2016, Hao Feng <whisperaven@gmail.com>

from abc import ABC, abstractmethod


TASK_RUNNER_UNSET = None


class TaskRunnerPrototype(ABC):
    """ Abstract base class for ``TaskRunner`` implementations. """

    __TASK_RUNNER_NAME__ = TASK_RUNNER_UNSET
    __TASK_RUNNER_TYPE__ = TASK_RUNNER_UNSET

    def __init__(self, hosts, executor):
        """ Initialize ``TaskRunner`` instance. """
        self._hosts = hosts
        self._executor = executor

    @classmethod
    def runner_name(cls):
        """ Name of this ``TaskRunner`` implementations. """
        return cls.__TASK_RUNNER_NAME__

    @classmethod
    def runner_type(cls):
        """ Type of this ``TaskRunner`` implementations. """
        return cls.__TASK_RUNNER_TYPE__

    @property
    def executor(self):
        """ Executor of this ``TaskRunner`` implementations. """
        return self._executor

    @property
    def hosts(self):
        """ Host to manipulation of this ``TaskRunner`` instance. """
        return self._hosts

    @abstractmethod
    def run_task(self, **taskopts):
        """ Execute user defined task on remote host(s). """
        raise NotImplementedError
