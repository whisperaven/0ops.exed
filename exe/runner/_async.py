# (c) 2016, Hao Feng <whisperaven@gmail.com>

import os
import sys

from celery import Celery

from .utils import celery_worker_arguments, CeleryWorkerInit


## Initialize Celery App ##
AsyncRunner = Celery(__name__)
AsyncRunner.user_options['worker'].add(celery_worker_arguments)
AsyncRunner.steps['worker'].add(CeleryWorkerInit)
