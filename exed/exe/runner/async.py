# -*- coding: utf-8 -*-

from celery import Celery
from celery.bin import worker
from celery.signals import worker_process_init
from multiprocessing import current_process

from .context import Context


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
        self._update_config()

    def _update_config(self):
        _cfg = self._ctx.cfg
        self._celery.conf.update(
            # worker_pool="gevent",
            # worker_redirect_stdouts_level="DEBUG",
            # worker_redirect_stdouts=True,
            broker_url=_cfg.broker_url,
            result_backend=_cfg.redis_url
        )

    def run(self):
        _worker = worker.worker(app=self._celery)
        _worker.run(loglevel="INFO")
