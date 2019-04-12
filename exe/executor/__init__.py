# (c) 2016, Hao Feng <whisperaven@gmail.com>

from .prototype import ExecutorPrototype
from ._ansible import AnsibleExecutor


EXECUTORS = [AnsibleExecutor]


__all__ = ['ExecutorPrototype', 'AnsibleExecutor', 'EXECUTORS']
