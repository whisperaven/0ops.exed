# (c) 2016, Hao Feng <whisperaven@gmail.com>

import logging

from .jobs import Job
from ._async import AsyncRunner
from .context import Context

from exe.executor.utils import *
from exe.utils.err import excinst
from exe.exc import JobNotSupportedError
from exe.exc import ExecutorPrepareError
from exe.exc import ExecutorDeployError
from exe.exc import ExecutorNoMatchError


LOG = logging.getLogger(__name__)


class DeployRunner(Context):
    """ Execute deploy task on remote host(s). """

    __RUNNER_NAME__ = "deploy"
    __RUNNER_MUTEX_REQUIRED__ = True

    def handle(ctx, targets, role, extra_vars, partial=None, run_async=True):
        """ Handle remote deploy request. """
        if not run_async:   # This should never happen, but let's be safe
            raise JobNotSupportedError("deploy can not run under async mode")
        job = Job(targets, ctx.runner_name, ctx.runner_mutex,
                  dict(role=role, extra_vars=extra_vars, partial=partial))
        job.create(ctx.redis)

        return job.associate_task(
            _async_deploy.delay(job.dict_ctx, targets, role,
                                extra_vars, partial), ctx.redis)


@AsyncRunner.task(bind=True, ignore_result=True,
                  base=Context, serializer='json')
def _async_deploy(ctx, job_ctx, targets, role, extra_vars, partial):
    job = Job.load(job_ctx)
    job.bind(ctx.request.id)

    try:
        redis = _async_deploy.redis
        executor = _async_deploy.executor(targets)

        failed_targets = []
        for yield_data in executor.deploy(role, extra_vars, partial):
            target, context = decompose_exec_yielddata(yield_data)

            # deploy returns:
            #   {$host -> {EXE_STATUS_ATTR -> $state (int),
            #              EXE_RETURN_ATTR -> $data (dict),
            #              EXE_NAME_ATTR   -> $name (string)}
            # when $host == EXE_ANNOUNCE_ATTR or
            #      $host == EXE_ANNOUNCE_SUMMARY_ATTR
            # means that message was an announce or summary without any
            #   operate on remote host(s), just like a print statement
            #   in your code
            #
            # and then, before push these data into redis, we compose
            #   our executor return context as follow:
            #
            #   {$host -> {EXE_STATUS_ATTR -> $state (int),
            #              EXE_RETURN_ATTR -> $description (string),
            #              EXE_NAME_ATTR   -> $name (string)}
            state, name, return_ctx = decompose_exec_returncontext(context)

            # handle announce context
            if execstate_announce(state):
                _context = compose_exec_returncontext(state, name,
                                                      execstate_name(state))
                for target in targets:
                    job.push_return_data(target, _context, redis)
                continue

            # handle success & failure context
            if execstate_failure(state):
                failed_targets.append(target)

                _context = compose_exec_returncontext(
                    state, name, executor.extract_return_error(return_ctx))
            else:
                _context = compose_exec_returncontext(state, name,
                                                      execstate_name(state))
            job.push_return_data(target, _context, redis)

        msg = None
        if failed_targets:
            for target in targets:
                failed = target in failed_targets
                job.target_done(target, failed, redis)

            msg = "<{0}> of <{1}> remote host(s) got deploy errors".format(
                len(failed_targets), len(targets))
        job.done(bool(failed_targets), msg, redis)

    except (ExecutorPrepareError, ExecutorDeployError, ExecutorNoMatchError):
        msg = ("got executor error while invoke deploy tool, "
               "{0}".format(excinst()))
        LOG.error(msg)
        job.done(failed=True, errmsg=msg, redis=redis)
    except:
        msg = ("got unexpected error while invoke deploy tool, "
               "{0}".format(excinst()))
        LOG.error(msg)
        job.done(failed=True, errmsg=msg, redis=redis)
