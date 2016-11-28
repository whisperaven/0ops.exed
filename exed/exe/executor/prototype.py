# -*- coding: utf-8 -*-

EXECUTOR_UNSET = None

class ExecutorPrototype(object):

    __EXECUTOR_NAME__ = EXECUTOR_UNSET

    def __init__(self, hosts, timeout):
        self._hosts = hosts
        self._timeout = timeout
