# (c) 2016, Hao Feng <whisperaven@gmail.com>

import inspect
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
from exe.exc import TaskNotSupportedError, TaskPrepareError
from exe.exc import TaskError, TaskAbort

LOG = logging.getLogger(__name__)


class TaskRunner(Context):
    """ Task execution on remote host. """

    __RUNNER_NAME__ = "task"
    __RUNNER_MUTEX_REQUIRED__ = True

    def query(ctx):
        return [ dict(name=tr.runner_name, type=tr.runner_type())
            for tr in ctx.task_plugins ]

    def handle(ctx, targets, taskname, tasktype, taskopts, run_async=False):
        if not run_async:   # This should never happen
            raise JobNotSupportedError(
                "tasks can not run under block mode (you may hit a bug)")
        if not ctx.task_plugin(tasktype):
            raise TaskNotSupportedError(
                "non supported task type {0}".format(tasktype))

        job = Job(targets, ctx.runner_name, ctx.runner_mutex,
            dict(taskname=taskname, tasktype=tasktype, taskopts=taskopts))
        job.create(ctx.redis)

        return job.associate_task(
            _async_task.delay(job.dict_ctx, 
                targets, taskname, tasktype, taskopts), ctx.redis)


@AsyncRunner.task(bind=True, ignore_result=True,
                  base=Context, serializer='json')
def _async_task(ctx, job_ctx, targets, taskname, tasktype, taskopts):
    job = Job.load(job_ctx)
    job.bind(ctx.request.id)

    try:
        redis = _async_task.redis
        executor = _async_task.executor(targets)

        try:
            tr = _async_task.task_plugin(tasktype)(targets, executor)
        except TypeError:
            raise TaskPrepareError(
                "<{0}>, bad task plugin implementate, {1}".format(
                    tr.runner_name, excinst()))

        try:
            LOG.info(("execute task <{0}> using <{1}> with args "
                      "<{2}> on <{3}>").format(taskname,
                                               tr.runner_name,
                                               taskopts,
                                               targets))
            returnner = tr.run_task(**taskopts)
            if not inspect.isgenerator(returnner):
                raise TaskPrepareError(("<{0}>, bad task plugin implementate, "
                                        "should return generator, "
                                        "not {1}").format(tr.runner_name,
                                                          type(returnner)))
        except TypeError:
            raise TaskPrepareError("{0} bad task plugin args".format(excinst()))

        failed_targets = []
        for yield_data in returner:
            target, context = decompose_exec_yielddata(yield_data)

            # task plugin returns:
            #   just like the deploy runner, everything yield from the
            #   returnner should wrapped via ``compose_exec_returncontext``
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

            msg = "<{0}> of <{1}> remote host(s) got task errors".format(
                len(failed_targets), len(targets))
        job.done(bool(failed_targets), msg, redis)

    except (ExecutorPrepareError, ExecutorDeployError, ExecutorNoMatchError):
        msg = "got executor error while execute task, {0}".format(excinst())
        LOG.error(msg)
        job.done(failed=True, errmsg=msg, redis=redis)
    except TaskPrepareError:
        msg = "got task plugin error while execute task, {0}".format(excinst())
        LOG.error(msg)
        job.done(failed=True, errmsg=msg, redis=redis)
    except TaskAbort:
        msg = "task aborted by plugin while execute task, {0}".format(excinst())
        LOG.warn(msg)
        job.done(failed=False, errmsg=msg, redis=redis)
    except TaskError:
        msg = ("task aborted by plugin while execute, got task error "
               "{0}".format(excinst()))
        LOG.error(msg)
        job.done(failed=True, errmsg=msg, redis=redis)
    except:
        msg = ("task aborted while execute task, "
               "got unexpected error, {0}".format(excinst()))
        LOG.error(msg)
        job.done(failed=True, errmsg=msg, redis=redis)
