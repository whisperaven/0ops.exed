# (c) 2016, Hao Feng <whisperaven@gmail.com>

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

    def handle(ctx, targets, command, run_async=False):
        """ Handle remote cmd execution request. """
        if not run_async:
            return next(ctx.executor(targets).raw_execute(command), None)
        job = Job(targets, ctx.runner_name, ctx.runner_mutex,
                  dict(command=command))
        job.create(ctx.redis)

        return job.associate_task(
            _async_execute.delay(job.dict_ctx, targets, command), ctx.redis)


@AsyncRunner.task(bind=True, ignore_result=True,
                  base=Context, serializer='json')
def _async_execute(ctx, job_ctx, targets, command):
    job = Job.load(job_ctx)
    job.bind(ctx.request.id)

    try:
        redis = _async_execute.redis
        executor = _async_execute.executor(targets)

        failed_targets = []
        for yield_data in executor.raw_execute(command):
            target, context = decompose_exec_yielddata(yield_data)

            # raw_execute returns:
            #   {$host -> {EXE_STATUS_ATTR -> $state (int),
            #              'stdout' -> $stdout (string),
            #              'stderr' -> $stderr (string),
            #              'rtc'    -> $ret_code (int)}
            # just push these context to redis
            job.push_return_data(target, context, redis)

            failed = execstate_failure(extract_return_state(context))
            if failed:
                failed_targets.append(target)

            job.target_done(target, failed, redis)

        msg = None
        if failed_targets:
            msg = "<{0}> of <{1}> remote host(s) got execute errors".format(
                len(failed_targets), len(targets))
        job.done(bool(failed_targets), msg, redis)

    except (ExecutorPrepareError, ExecutorNoMatchError):
        msg = ("got executor error while execute raw command, "
              " {0}").format(excinst())
        LOG.error(msg)
        job.done(failed=True, errmsg=msg, redis=redis)
    except:
        msg = ("got unexpected error while execute raw command, "
               "{0}").format(excinst())
        LOG.error(msg)
        job.done(failed=True, errmsg=msg, redis=redis)
