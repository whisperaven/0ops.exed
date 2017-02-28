# -*- coding: utf-8 -*-

import logging

from .jobs import Job
from ._async import AsyncRunner
from .context import Context

from exe.executor.utils import *
from exe.utils.err import excinst
from exe.exc import ExecutorPrepareError, ExecutorNoMatchError

LOG = logging.getLogger(__name__)


class ServiceRunner(Context):
    """ Manipulate service on remote host. """

    __RUNNER_NAME__ = "service"
    __RUNNER_MUTEX_REQUIRED__ = False

    def handle(ctx, targets, name, start, restart, graceful, async=False):
        if not async:
            return next(ctx.executor(targets).service(name, start, restart, graceful), None)
        job = Job(targets, ctx.runner_name, ctx.runner_mutex)
        job.create(ctx.redis)

        return job.associate_task(
            _async_deploy.delay(job.dict_ctx, targets, name, start, restart, graceful), ctx.redis)


@AsyncRunner.task(bind=True, ignore_result=True, base=Context, serializer='json')
def _async_service(ctx, job_ctx, targets, name, start, restart, graceful):
    job = Job.load(job_ctx)
    job.bind(ctx.request.id)

    redis = _async_deploy.redis
    executor = _async_deploy.executor(targets)

    failed = False
    try:
        for rdeturn_data in _async_service.executor(targets).service(name, start, restart, graceful):
            target, retval = parse_exe_return(return_data)

            job.update(target, retval, redis)
            if isExeSuccess(retval):
                job.update_done(target, redis)
            else:
                failed = True

        job.done(redis, failed)

    except (ExecutorPrepareError, ExecutorNoMatchError):
        msg = "got executor error, <{0}>".format(excinst())
        LOG.error(msg)
        job.done(redis, failed=True, error=msg)
    except:
        msg = "got unexpected error, <{0}>".format(excinst())
        LOG.error(msg)
        job.done(redis, failed=True, error=msg)
