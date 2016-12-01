# -*- coding: utf-8 -*-

import os
import sys

from celery import Celery
from celery.bin import worker
from celery.signals import worker_process_init
from celery.bin.celeryd_detach import detach
from multiprocessing import current_process

from exe.cfg import CONF

from .context import Context
from .context import DEFAULT_CONCURRENCY


## Celery App ##
AsyncRunner = Celery()


## Fix Celery Issues ##
@worker_process_init.connect
def fix_multiprocessing(**kwargs):
    ## Fix `AttributeError: 'Process' object has no attribute '_authkey'`
    try:
        current_process()._authkey
    except AttributeError:
        current_process()._authkey = current_process()._config['authkey']
    ## Fix `AttributeError: 'Process' object has no attribute '_daemonic'`
    ## Also: `https://github.com/celery/celery/issues/1709`
    try:
        current_process()._daemonic
    except AttributeError:
        # current_process()._daemonic = current_process()._config.get('daemon', False)
        current_process()._daemonic = False
    ## Fix `AttributeError: 'Process' object has no attribute '_tempdir'`
    try:
        current_process()._tempdir
    except AttributeError:
        current_process()._tempdir = None


## Celery Worker ##
class AsyncWorker(object):

    def __init__(self, celery_app):
        self._ctx = Context()
        self._celery = celery_app
        self._pid_file = None
        self._update_config()

    def _update_config(self):

        _cfg = self._ctx.cfg
        _concurrency = _cfg.concurrency
        if not _concurrency:
            _concurrency = DEFAULT_CONCURRENCY

        self._celery.conf.update(
            worker_concurrency=_concurrency,
            broker_url=_cfg.broker_url,
            result_backend=_cfg.redis_url
        )

        if _cfg.pid_file:
            self._pid_file = _cfg.pid_file

        _log_cfg = self._ctx._log_cfg
        if _log_cfg.worker_log:
            self._celery.conf.update(
                worker_redirect_stdouts=True,
            )
        else:
            _log_cfg.worker_log = os.devnull

    def run(self, daemon=False):
        _log_cfg = self._ctx._log_cfg
        _worker = worker.worker(app=self._celery)
        _worker.run(loglevel=_log_cfg.log_level, logfile=_log_cfg.worker_log, pidfile=self._pid_file)
