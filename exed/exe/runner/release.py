# -*- coding: utf-8 -*-

from .jobs import Job
from .async import AsyncRunner
from .context import Context

from exe.exc import JobNotSupportedError
from exe.exc import ReleaseNotSupportedError
from exe.release.consts import *


class ReleaseRunner(Context):
    """ Release revision of app on remote host. """

    __RUNNER_NAME__ = "release"
    __RUNNER_MUTEX_REQUIRED__ = True

    def query(ctx):
        query_result = []
        for RH in ctx.release_handlers:
            rh_info = dict()
            rh_info['name'] = RH.hname()
            rh_info['type'] = RH.htype()
            query_result.append(rh_info)
        return query_result

    def handle(ctx, targets, appname, apptype, revision, nobackup, rollback, extra_opts, async=False):

        if not async:   # This should never happen
            raise JobNotSupportedError("release can not run under block mode (you may hit a bug)")
        if not ctx.release_handler(apptype):
            raise ReleaseNotSupportedError("non supported release app {0}".format(apptype))

        job = Job(targets, ctx.runner_name, ctx.runner_mutex)
        job.create(ctx.redis)

        return job.associate_task(
            _async_release.delay(job.dict_ctx, 
                targets, appname, apptype, revision, nobackup, rollback, extra_opts), ctx.redis)


@AsyncRunner.task(bind=True, ignore_result=True, base=Context, serializer='json')
def _async_release(ctx, job_ctx, targets, appname, apptype, revision, nobackup, rollback, extra_opts):

    job = Job.load(job_ctx)
    job.bind_task(ctx.request.id)

    redis = _async_release.redis
    executor = _async_release.executor(targets)
    rh = _async_release.release_handler(apptype)(targets, appname, executor)

    returner = None
    if rollback:
        returner = rh.rollback(revision, **extra_opts)
    else:
        if not nobackup:
            for return_data in rh.rbackup(**extra_opts):
                target, retval = return_data.popitem()
                job.task_update(target, retval, redis)
                if int(retval.get(REL_STATUS_ATTR)) == REL_FAILED:
                    job.task_failure(target, redis)
        returner = rh.release(revision, **extra_opts)

    if returner:
        for return_data in returner:
            target, retval = return_data.popitem()
            job.task_update(target, retval, redis)
            if int(retval.get(REL_STATUS_ATTR)) == REL_FAILED:
                job.task_failure(target, redis)
        job.done(redis)
