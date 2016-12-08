# -*- coding: utf-8 -*-

from .jobs import Job
from .async import AsyncRunner
from .context import Context

from exe.executor.consts import *

class ExecuteRunner(Context):
    """ Execute command on remote host(s). """

    __RUNNER_NAME__ = "execute"
    __RUNNER_MUTEX_REQUIRED__ = False

    def handle(ctx, targets, command, async=False):
        if not async:
            return ctx.executor(targets).raw_execute(command)

        job = Job(targets, ctx.runner_name, ctx.runner_mutex)
        job.create(ctx.redis)

        return job.associate_task(
            _async_execute.delay(job.dict_ctx, targets, command), ctx.redis)


@AsyncRunner.task(bind=True, ignore_result=True, base=Context, serializer='json')
def _async_execute(ctx, job_ctx, targets, command):

    job = Job.load(job_ctx)
    job.bind_task(ctx.request.id)

    redis = _async_execute.redis
    executor = _async_execute.executor(targets)

    failed = False
    for return_data in executor.raw_execute(command):

        target, retval = return_data.popitem()
        job.task_update(target, retval, redis)

        if int(retval.get(EXE_STATUS_ATTR)) in (EXE_FAILED, EXE_UNREACHABLE):
            job.task_failure(target, redis)
            failed = True

    if not failed:
        job.done(redis)
    else:
        job.failure(redis)
