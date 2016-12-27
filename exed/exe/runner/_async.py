# -*- coding: utf-8 -*-

import os
import sys

from celery import Celery
from celery.signals import worker_process_init
from multiprocessing import current_process

from .utils import celery_worker_arguments, CeleryWorkerInit


## Celery App ##
AsyncRunner = Celery(__name__)
AsyncRunner.user_options['worker'].add(celery_worker_arguments)
AsyncRunner.steps['worker'].add(CeleryWorkerInit)


## Fix Celery Multiprocessing/Billiard Issues ##
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
