# (c) 2016, Hao Feng <whisperaven@gmail.com>

from abc import ABC, abstractmethod

from .consts import EXECUTOR_UNSET


class ExecutorPrototype(ABC):
    """ Abstract base class for ``Executor`` implementations. """

    __EXECUTOR_NAME__ = EXECUTOR_UNSET

    def __init__(self, hosts, timeout, concurrency):
        """ Initialize ``Executor`` instance. """
        self._slot = None
        self._hosts = hosts if isinstance(hosts, (tuple, list)) else [hosts]
        self._timeout = timeout
        self._concurrency = concurrency

    @classmethod
    def name(cls):
        """ Name of this ``Executor`` implementations. """
        return cls.__EXECUTOR_NAME__

    @property
    def hosts(self):
        """ Host to manipulation of this ``Executor`` instance. """
        return self._hosts

    def set_hosts(self, hosts):
        """ Temporary change host(s) of this ``Executor`` instance. """
        if self._slot == None:
            self._slot = self._hosts
        self._hosts = hosts if isinstance(hosts, (tuple, list)) else [hosts]

    def reset_hosts(self):
        """ Reset host(s) of this ``Executor`` instance before change. """
        if self._slot != None:
            self._hosts = self._slot
            self._slot = None

    @abstractmethod
    def extract_return_error(self, return_context):
        """ Extra error context from return context. """
        raise NotImplementedError

    @abstractmethod
    def target(self, pattern):
        """ Match target by given pattern. """
        raise NotImplementedError

    @abstractmethod
    def execute(self, module, check_mode=False, **module_args):
        """ Invoke executor module with given args on remote host(s). """
        raise NotImplementedError

    @abstractmethod
    def raw_execute(self, cmd):
        """ Invoke executor command module on remote host(s). """
        raise NotImplementedError

    @abstractmethod
    def ping(self):
        """ Ping remote host(s) via executor. """
        raise NotImplementedError

    @abstractmethod
    def facter(self):
        """ Gather information of remote host(s). """
        raise NotImplementedError

    @abstractmethod
    def service(self, name, start=True, restart=False, graceful=True):
        """ Manipulate service on remote host(s). """
        raise NotImplementedError

    @abstractmethod
    def deploy(self, component, extra_vars=None, partial=None):
        """ Deploy service/role/app (the component) on remote host(s). """
        raise NotImplementedError
