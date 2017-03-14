# -*- coding: utf-8 -*-

import abc

import six


RELEASE_HANDLER_UNSET = None


@six.add_metaclass(abc.ABCMeta)
class ReleaseHandlerPrototype(object):

    __RHANDLER_NAME__ = RELEASE_HANDLER_UNSET
    __RHANDLER_TYPE__ = RELEASE_HANDLER_UNSET

    def __init__(self, hosts, appname, executor):
        self._hosts = hosts
        self._appname = appname
        self._executor = executor

    @classmethod
    def hname(cls):
        return cls.__RHANDLER_NAME__

    @classmethod
    def htype(cls):
        return cls.__RHANDLER_TYPE__

    @property
    def appname(self):
        return self._appname

    @property
    def hosts(self):
        return self._hosts

    @property
    def executor(self):
        return self._executor

    @abc.abstractmethod
    def release(self, revision, **extra_opts):
        """ Release revision on remote host(s). """
        raise NotImplementedError

    @abc.abstractmethod
    def rollback(self, revision, **extra_opts):
        """ Rollback using remote backups. """
        raise NotImplementedError

    @abc.abstractmethod
    def revision(self, **extra_opts):
        """ Gather content of revision records. """
        raise NotImplementedError
