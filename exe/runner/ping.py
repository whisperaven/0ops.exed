# (c) 2016, Hao Feng <whisperaven@gmail.com>

import logging

from .jobs import Job
from ._async import AsyncRunner
from .context import Context

from exe.executor.utils import *
from exe.utils.err import excinst
from exe.exc import ExecutorPrepareError, ExecutorNoMatchError


LOG = logging.getLogger(__name__)


class PingRunner(Context):
    """ Ping remote host(s) via Executor. """

    __RUNNER_NAME__ = "ping"
    __RUNNER_MUTEX_REQUIRED__ = False

    def handle(ctx, targets, run_async=False):
        """ Handle remote ping request. """
        if not run_async:
            return next(ctx.executor(targets).ping(), None)
        job = Job(targets, ctx.runner_name, ctx.runner_mutex)
        job.create(ctx.redis)
        
        return job.associate_task(
            _async_ping.delay(job.dict_ctx, targets), ctx.redis)


@AsyncRunner.task(bind=True, ignore_result=True,
                  base=Context, serializer='json')
def _async_ping(ctx, job_ctx, targets):
    job = Job.load(job_ctx)
    job.bind(ctx.request.id)

    try:
        redis = _async_ping.redis

        failed_targets = []
        for yield_data in _async_ping.executor(targets).ping():
            target, context = decompose_exec_yielddata(yield_data)

            # ping returns:
            #   {$host -> {EXE_STATUS_ATTR -> $state (int)}
            # just push these context to redis
            job.push_return_data(target, context, redis)

            failed = execstate_failure(extract_return_state(context))
            if failed:
                failed_targets.append(target)

            job.target_done(target, failed, redis)

        msg = None
        if failed_targets:
            msg = "total <{0}> of <{1}> remote host(s) no response".format(
                len(failed_targets), len(targets))
        job.done(bool(failed_targets), msg, redis)

    except (ExecutorPrepareError, ExecutorNoMatchError):
        msg = "got executor error, {0}".format(excinst())
        LOG.error(msg)
        job.done(failed=True, errmsg=msg, redis=redis)
    except:
        msg = "got unexpected error, {0}".format(excinst())
        LOG.error(msg)
        job.done(failed=True, errmsg=msg, redis=redis)
