# -*- coding: utf-8 -*-

from .jobs import Job
from .async import AsyncRunner
from .context import Context


class FacterRunner(Context):
    """ Gather information of remote host. """

    __RUNNER_NAME__ = "facter"
    __RUNNER_MUTEX_REQUIRED__ = False

    def handle(ctx, targets, async=False):
        if not async:
            return ctx.executor(targets).facter()

        job = Job(targets, ctx.runner_name, ctx.runner_mutex)
        job.create(ctx.redis)

        return job.associate_task(
            _async_facter.delay(job.dict_ctx, targets), ctx.redis)


@AsyncRunner.task(bind=True, ignore_result=True, base=Context, serializer='json')
def _async_facter(ctx, job_ctx, targets):

    job = Job.load(job_ctx)
    job.bind_task(ctx.request.id)

    redis = _async_facter.redis
    executor = _async_facter.executor(targets)

    for return_data in executor.facter():
        target, retval = return_data.popitem()
        job.task_update(target, retval, redis)
        job.task_done(target, redis)

    job.done(redis)
