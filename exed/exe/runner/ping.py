# -*- coding: utf-8 -*-

from .jobs import Job
from .async import AsyncRunner
from .context import Context


class PingRunner(Context):
    """ Ping remote host(s) via Executor. """

    __RUNNER_NAME__ = "ping"
    __RUNNER_MUTEX_REQUIRED__ = False

    def handle(ctx, targets, async=False):

        if not async:
            return ctx.executor(targets).ping()
        
        job = Job(targets, ctx.runner_name, ctx.runner_mutex)
        job.create(ctx.redis)
        
        return job.associate_task(
            _async_ping.delay(job.dict_ctx, targets), ctx.redis)


@AsyncRunner.task(bind=True, ignore_result=True, base=Context, serializer='json')
def _async_ping(ctx, job_ctx, targets):

    job = Job.load(job_ctx)
    job.bind_task(ctx.request.id)

    redis = _async_ping.redis
    executor = _async_ping.executor(targets)

    for return_data in executor.ping():
        target, retval = return_data.popitem()

        job.task_update(target, retval, redis)
        job.task_done(target, redis)

    job.done(redis)
