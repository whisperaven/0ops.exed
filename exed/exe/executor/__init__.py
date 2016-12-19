# -*- coding: utf-8 -*-

from .prototype import ExecutorPrototype
from ._ansible import AnsibleExecutor


EXECUTORS = []
CORE_EXECUTORS = [AnsibleExecutor]


__all__ = ['ExecutorPrototype', 'AnsibleExecutor', 
        'CORE_EXECUTORS', 'EXECUTORS']
