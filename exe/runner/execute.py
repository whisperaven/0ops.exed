# -*- coding: utf-8 -*-

import logging

from .jobs import Job
from ._async import AsyncRunner
from .context import Context

from exe.executor.utils import *
from exe.utils.err import excinst
from exe.exc import ExecutorPrepareError, ExecutorNoMatchError

LOG = logging.getLogger(__name__)


class ExecuteRunner(Context):
    """ Execute command on remote host(s). """

    __RUNNER_NAME__ = "execute"
    __RUNNER_MUTEX_REQUIRED__ = False

    def handle(ctx, targets, command, async=False):
        if not async:
            return next(ctx.executor(targets).raw_execute(command), None)
        job = Job(targets, ctx.runner_name, ctx.runner_mutex, dict(command=command))
        job.create(ctx.redis)

        return job.associate_task(
            _async_execute.delay(job.dict_ctx, targets, command), ctx.redis)


@AsyncRunner.task(bind=True, ignore_result=True, base=Context, serializer='json')
def _async_execute(ctx, job_ctx, targets, command):
    job = Job.load(job_ctx)
    job.bind(ctx.request.id)

    failed = False
    try:
        redis = _async_execute.redis
        for return_data in _async_execute.executor(targets).raw_execute(command):
            target, retval = parse_exe_return(return_data)

            job.update(target, retval, redis)
            job.update_done(redis, target, isExeFailure(retval))

            if isExeFailure(retval):
                failed = True

        job.done(redis, failed)

    except (ExecutorPrepareError, ExecutorNoMatchError):
        msg = "got executor error, {0}".format(excinst())
        LOG.error(msg)
        job.done(redis, failed=True, error=msg)
    except:
        msg = "got unexpected error, {0}".format(excinst())
        LOG.error(msg)
        job.done(redis, failed=True, error=msg)
