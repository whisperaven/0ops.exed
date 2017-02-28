# -*- coding: utf-8 -*-

import logging

from .jobs import Job
from ._async import AsyncRunner
from .context import Context

from exe.executor.utils import *
from exe.utils.err import excinst
from exe.exc import JobNotSupportedError
from exe.exc import ExecutorPrepareError, ExecutorDeployError, ExecutorNoMatchError

LOG = logging.getLogger(__name__)


class DeployRunner(Context):
    """ Deploy on remote host(s) via Executor. """

    __RUNNER_NAME__ = "deploy"
    __RUNNER_MUTEX_REQUIRED__ = True

    def handle(ctx, targets, role, extra_vars, partial=None, async=True):
        if not async:   # This should never happen
            raise JobNotSupportedError("deploy can not run under block mode (you may hit a bug)") 
        job = Job(targets, ctx.runner_name, ctx.runner_mutex)
        job.create(ctx.redis)

        return job.associate_task(
            _async_deploy.delay(job.dict_ctx, targets, role, extra_vars, partial), ctx.redis)


@AsyncRunner.task(bind=True, ignore_result=True, base=Context, serializer='json')
def _async_deploy(ctx, job_ctx, targets, role, extra_vars, partial):
    job = Job.load(job_ctx)
    job.bind(ctx.request.id)

    failures = []
    try:
        redis = _async_deploy.redis
        for return_data in _async_deploy.executor(targets).deploy(role, extra_vars, partial):
            target, retval = parse_exe_return(return_data)

            # recreate retval for deploy endpoint
            state, name, retval = parse_exe_retval(retval)
            retval = create_exe_retval(state, name, None)

            job.update(target, retval, redis)
            if isExeFailure(retval):
                failures.append(target)

        failed = True if failures else False
        for target in targets:
            if target not in failures:
                job.update_done(target, redis)
        job.done(redis, failed)

    except (ExecutorPrepareError, ExecutorDeployError, ExecutorNoMatchError):
        msg = "got executor error, {0}".format(excinst())
        LOG.error(msg)
        job.done(redis, failed=True, error=msg)
    except:
        msg = "got unexpected error, {0}".format(excinst())
        LOG.error(msg)
        job.done(redis, failed=True, error=msg)
