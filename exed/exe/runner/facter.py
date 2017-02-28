# -*- coding: utf-8 -*-

import logging

from .jobs import Job
from ._async import AsyncRunner
from .context import Context

from exe.executor.utils import *
from exe.utils.err import excinst
from exe.exc import ExecutorPrepareError, ExecutorNoMatchError

LOG = logging.getLogger(__name__)


class FacterRunner(Context):
    """ Gather information of remote host. """

    __RUNNER_NAME__ = "facter"
    __RUNNER_MUTEX_REQUIRED__ = False

    def handle(ctx, targets, async=False):
        if not async:
            return next(ctx.executor(targets).facter(), None)
        job = Job(targets, ctx.runner_name, ctx.runner_mutex)
        job.create(ctx.redis)

        return job.associate_task(
            _async_facter.delay(job.dict_ctx, targets), ctx.redis)


@AsyncRunner.task(bind=True, ignore_result=True, base=Context, serializer='json')
def _async_facter(ctx, job_ctx, targets):
    job = Job.load(job_ctx)
    job.bind(ctx.request.id)

    failed = False
    try:
        redis = _async_facter.redis
        for return_data in _async_facter.executor(targets).facter():
            target, retval = parse_exe_return(return_data)

            job.update(target, retval, redis)
            if isExeSuccess(retval):
                job.update_done(target, redis)
            else:
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
