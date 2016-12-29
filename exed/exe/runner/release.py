# -*- coding: utf-8 -*-

import logging

from .jobs import Job
from ._async import AsyncRunner
from .context import Context

from exe.release.consts import *
from exe.executor.utils import *
from exe.utils.err import excinst
from exe.exc import JobNotSupportedError, ReleaseNotSupportedError
from exe.exc import ExecutorPrepareError, ExecutorDeployError
from exe.exc import ReleasePrepareError, ReleaseError, ReleaseAbort

LOG = logging.getLogger(__name__)


class ReleaseRunner(Context):
    """ Release revision of app on remote host. """

    __RUNNER_NAME__ = "release"
    __RUNNER_MUTEX_REQUIRED__ = True

    def query(ctx):
        query_result = []
        for RH in ctx.release_plugins:
            rh_info = dict()
            rh_info['name'] = RH.hname()
            rh_info['type'] = RH.htype()
            query_result.append(rh_info)
        return query_result

    def handle(ctx, targets, appname, apptype, revision, rollback, extra_opts, async=False):
        if not async:   # This should never happen
            raise JobNotSupportedError("release can not run under block mode (you may hit a bug)")
        if not ctx.release_plugin(apptype):
            raise ReleaseNotSupportedError("non supported release type {0}".format(apptype))
        job = Job(targets, ctx.runner_name, ctx.runner_mutex)
        job.create(ctx.redis)

        return job.associate_task(
            _async_release.delay(job.dict_ctx, 
                targets, appname, apptype, revision, rollback, extra_opts), ctx.redis)


@AsyncRunner.task(bind=True, ignore_result=True, base=Context, serializer='json')
def _async_release(ctx, job_ctx, targets, appname, apptype, revision, rollback, extra_opts):

    job = Job.load(job_ctx)
    job.bind(ctx.request.id)

    failures = []
    try:
        redis = _async_release.redis
        executor = _async_release.executor(targets)

        try:
            rh = _async_release.release_plugin(apptype)(targets, appname, executor)
        except TypeError:
            raise ReleasePrepareError("{0} bad release plugin implementate".format(excinst()))

        returner = None
        try:
            if rollback:
                LOG.debug("rollback to <{0}> using <{1}> with args <{2}> on <{3}>".format(
                    revision, rh.hname(), extra_opts, rh.hosts))
                returner = rh.rollback(revision, **extra_opts)
            else:
                if revision == REVISION_QUERY:
                    LOG.debug("query revision using <{0}> with args <{1}> on <{2}>".format(
                        rh.hname(), extra_opts, rh.hosts))
                    returner = rh.revision(**extra_opts)
                else:
                    LOG.debug("release rev <{0}> using <{1}> with args <{2}> on <{3}>".format(
                        revision, rh.hname(), extra_opts, rh.hosts))
                    returner = rh.release(revision, **extra_opts)
        except TypeError:
            raise ReleasePrepareError("{0} bad release plugin args".format(excinst()))

        for return_data in returner:
            target, retval = parse_exe_return(return_data)

            job.update(target, retval, redis)
            if isExeFailure(retval):
                failures.append(target)

        failed = True if failures else False
        for target in targets:
            if target not in failures:
                job.update_done(target, redis)
        job.done(redis, failed)

    except (ExecutorPrepareError, ExecutorDeployError):
        msg = "got executor error, <{0}>".format(excinst())
        LOG.error(msg)
        job.done(redis, failed=True, error=msg)
    except ReleasePrepareError:
        msg = "got release plugin error, <0>".format(excinst())
        LOG.error(msg)
        job.done(redis, failed=True, error=msg)
    except ReleaseAbort:
        msg = "release aborted by plugin, <{0}>".format(excinst())
        LOG.error(msg)
        job.done(redis, failed=True, error=msg)
    except ReleaseError:
        msg = "release aborted by plugin, got error <{0}>".format(excinst())
        LOG.error(msg)
        job.done(redis, failed=True, error=msg)
    except:
        msg = "release aborted, got unexpected error, <{0}>".format(excinst())
        LOG.error(msg)
        job.done(redis, failed=True, error=msg)
