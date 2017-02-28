# -*- coding: utf-8 -*-

import abc

import six


EXECUTOR_UNSET = None


@six.add_metaclass(abc.ABCMeta)
class ExecutorPrototype(object):

    __EXECUTOR_NAME__ = EXECUTOR_UNSET

    def __init__(self, hosts, timeout):
        self._slot = None
        self._hosts = hosts if isinstance(hosts, (tuple, list)) else [hosts]
        self._timeout = timeout

    @classmethod
    def name(cls):
        return cls.__EXECUTOR_NAME__

    @property
    def hosts(self):
        return self._hosts

    def set_hosts(self, hosts):
        if self._slot == None:
            self._slot = self._hosts
        self._hosts = hosts if isinstance(hosts, (tuple, list)) else [hosts]

    def reset_hosts(self):
        if self._slot != None:
            self._hosts = self._slot
            self._slot = None

    @abc.abstractmethod
    def target(self, pattern):
        """ Match target by given pattern. """
        raise NotImplementedError

    @abc.abstractmethod
    def execute(self, module, check_mode=False, **module_args):
        """ Invoke executor module with given args on remote host(s). """
        raise NotImplementedError

    @abc.abstractmethod
    def raw_execute(self, cmd):
        """ Invoke executor command module on remote host(s). """
        raise NotImplementedError

    @abc.abstractmethod
    def ping(self):
        """ Ping remote host(s). """
        raise NotImplementedError

    @abc.abstractmethod
    def facter(self):
        """ Gather information of remote host(s). """
        raise NotImplementedError

    @abc.abstractmethod
    def service(self, name, start=True, restart=False, graceful=True):
        """ Manipulate service on remote host(s). """
        raise NotImplementedError

    @abc.abstractmethod
    def deploy(self, roles, extra_vars=None, partial=None):
        """ Deploy service/role/app on remote host(s). """
        raise NotImplementedError
