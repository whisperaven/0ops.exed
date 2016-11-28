# -*- coding: utf-8 -*-

from .jobs import Job
from .async import AsyncRunner
from .context import Context

from exe.executor.consts import *

class ServiceRunner(Context):
    """ Manipulate service on remote host. """

    __RUNNER_NAME__ = "service"
    __RUNNER_MUTEX_REQUIRED__ = False

    def handle(ctx, targets, name, start, restart, graceful, async=False):
        if not async:
            return ctx.executor(targets).service(name, start, restart, graceful)

        job = Job(targets, ctx.runner_name, ctx.runner_mutex)
        job.create(ctx.redis)

        return job.associate_task(
            _async_deploy.delay(job.dict_ctx, targets, name, start, restart, graceful), ctx.redis)


@AsyncRunner.task(bind=True, ignore_result=True, base=Context, serializer='json')
def _async_service(ctx, job_ctx, targets, name, start, restart, graceful):

    job = Job.load(job_ctx)
    job.bind_task(ctx.request.id)

    redis = _async_deploy.redis
    executor = _async_deploy.executor(targets)

    failed = False
    for return_data in executor.service(name, start, restart, graceful):

        target, retval = return_data.popitem()
        job.task_update(target, retval, redis)

        if retval in (EXE_FAILED, EXE_UNREACHABLE):
            job.task_failure(target, redis)
            failed = True
        else:
            job.task_done(target, redis)

    if not failed:
        job.done(redis)
    else:
        job.failure(redis)
