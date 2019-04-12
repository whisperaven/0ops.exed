# (c) 2016, Hao Feng <whisperaven@gmail.com>

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

    def handle(ctx, targets, name, start, restart, graceful, run_async=False):
        """ Handle remote service maintain request. """
        if not run_async:
            return next(
                ctx.executor(targets).service(name, start, restart, graceful),
                None)
        job = Job(targets, ctx.runner_name, ctx.runner_mutex, 
                  dict(name=name, start=start,
                       restart=restart, graceful=graceful))
        job.create(ctx.redis)

        return job.associate_task(
            _async_service.delay(job.dict_ctx, targets,
                                 name, start, restart, graceful), ctx.redis)


@AsyncRunner.task(bind=True, ignore_result=True,
                  base=Context, serializer='json')
def _async_service(ctx, job_ctx, targets, name, start, restart, graceful):
    job = Job.load(job_ctx)
    job.bind(ctx.request.id)

    try:
        redis = _async_service.redis
        executor = _async_service.executor(targets)

        failed_targets = []
        for yield_data in executor.service(name, start, restart, graceful):
            target, context = decompose_exec_yielddata(yield_data)

            # service returns:
            #   {$host -> {EXE_STATUS_ATTR -> $state (int)}
            # just push these context to redis
            job.push_return_data(target, context, redis)

            failed = execstate_failure(extract_return_state(context))
            if failed:
                failed_targets.append(target)

            job.target_done(target, failed, redis)

        msg = None
        if failed_targets:
            msg = "<{0}> of <{1}> remote host(s) got service errors".format(
                len(failed_targets), len(targets))
        job.done(bool(failed_targets), msg, redis)

    except (ExecutorPrepareError, ExecutorNoMatchError):
        msg = ("got executor error while invoke service tool, "
               "{0}").format(excinst())
        LOG.error(msg)
        job.done(failed=True, errmsg=msg, redis=redis)
    except:
        msg = ("got unexpected error while invoke service tool, "
               "{0}").format(excinst())
        LOG.error(msg)
        job.done(failed=True, errmsg=msg, redis=redis)
