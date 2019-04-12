# (c) 2016, Hao Feng <whisperaven@gmail.com>

import logging

from .jobs import Job
from ._async import AsyncRunner
from .context import Context

from exe.executor.utils import *
from exe.utils.err import excinst
from exe.exc import ExecutorPrepareError, ExecutorNoMatchError


LOG = logging.getLogger(__name__)


class FacterRunner(Context):
    """ Gather information of remote host via Executor. """

    __RUNNER_NAME__ = "facter"
    __RUNNER_MUTEX_REQUIRED__ = False

    def handle(ctx, targets, run_async=False):
        """ Handle remote facter request. """
        if not run_async:
            return next(ctx.executor(targets).facter(), None)
        job = Job(targets, ctx.runner_name, ctx.runner_mutex)
        job.create(ctx.redis)

        return job.associate_task(
            _async_facter.delay(job.dict_ctx, targets), ctx.redis)


@AsyncRunner.task(bind=True, ignore_result=True,
                  base=Context, serializer='json')
def _async_facter(ctx, job_ctx, targets):
    job = Job.load(job_ctx)
    job.bind(ctx.request.id)

    try:
        redis = _async_facter.redis

        failed_targets = []
        for yield_data in _async_facter.executor(targets).facter():
            target, context = decompose_exec_yielddata(yield_data)

            # facter returns:
            #   {$host -> {EXE_STATUS_ATTR -> $state (int),
            #              'facts'         -> $fact_data (dict)}}
            # just push these context to redis
            job.push_return_data(target, context, redis)

            failed = execstate_failure(extract_return_state(context))
            if failed:
                failed_targets.append(target)

            job.target_done(target, failed, redis)

        msg = None
        if failed_targets:
            msg = "<{0}> of <{1}> remote host(s) got facts errors".format(
                len(failed_targets), len(targets))
        job.done(bool(failed_targets), msg, redis)

    except (ExecutorPrepareError, ExecutorNoMatchError):
        msg = ("got executor error while gathering facts, "
               "{0}").format(excinst())
        LOG.error(msg)
        job.done(failed=True, errmsg=msg, redis=redis)
    except:
        msg = ("got unexpected error while gathering facts, "
               "{0}").format(excinst())
        LOG.error(msg)
        job.done(failed=True, errmsg=msg, redis=redis)
