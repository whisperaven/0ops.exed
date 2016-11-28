# -*- coding: utf-8 -*-

from .jobs import Job
from .async import AsyncRunner
from .context import Context

from exe.exc import JobNotSupportedError
from exe.executor.consts import *


class DeployRunner(Context):
    """ Deploy on remote host(s) via Executor. """

    __RUNNER_NAME__ = "deploy"
    __RUNNER_MUTEX_REQUIRED__ = True

    def handle(ctx, targets, role, extra_vars, async=True):

        if not async:   # This should never happen
            raise JobNotSupportedError("deploy can not run under block mode")

        job = Job(targets, ctx.runner_name, ctx.runner_mutex)
        job.create(ctx.redis)

        return job.associate_task(
            _async_deploy.delay(job.dict_ctx, targets, role, extra_vars), ctx.redis)


@AsyncRunner.task(bind=True, ignore_result=True, base=Context, serializer='json')
def _async_deploy(ctx, job_ctx, targets, role, extra_vars):
    
    job = Job.load(job_ctx)
    job.bind_task(ctx.request.id)

    redis = _async_deploy.redis
    executor = _async_deploy.executor(targets)

    failure = []
    for return_data in executor.deploy(role, extra_vars):
        
        target, retval = return_data.popitem()
        retval.pop(EXE_RETURN_ATTR)

        job.task_update(target, retval, redis)

        if int(retval.get(EXE_STATUS_ATTR)) in (EXE_FAILED, EXE_UNREACHABLE):
            job.task_failure(target, redis)
            failure.append(target)

    for target in targets:
        if target not in failure:
            job.task_done(target, redis)

    if not failure:
        job.done(redis)
    else:
        job.failure(redis)
