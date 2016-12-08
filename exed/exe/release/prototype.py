# -*- coding: utf-8 -*-

RELEASE_HANDLER_UNSET = None


class ReleaseHandlerPrototype(object):

    __RHANDLER_NAME__ = RELEASE_HANDLER_UNSET
    __RHANDLER_TYPE__ = RELEASE_HANDLER_UNSET
    __SUPPORTED_APP__ = ()

    def __init__(self, hosts, appname, executor):
        self._hosts = hosts
        self._appname = appname
        self._executor = executor

    @classmethod
    def name(cls):
        return cls.__RHANDLER_NAME__

    @classmethod
    def handler_type(cls):
        return cls.__RHANDLER_TYPE__

    @classmethod
    def supported_apps(cls):
        return cls.__SUPPORTED_APP__

    @classmethod
    def support(cls, apptype):
        """ Return true if handler support the apptype. """
        return apptype in cls.__SUPPORTED_APP__

    def release(self, revision, **extra_opts):
        """ Release revision on remote host(s). """
        raise NotImplementedError

    def rollback(self, revision, **extra_opts):
        """ Rollback using remote backups. """
        raise NotImplementedError

    def revision(self, **extra_opts):
        """ Gather content of revision records. """
        raise NotImplementedError

    def rbackup(self, extra_opts):
        """ Make backup on remote host(s). """
        raise NotImplementedError
