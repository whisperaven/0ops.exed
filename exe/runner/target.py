# (c) 2016, Hao Feng <whisperaven@gmail.com>

from .jobs import Job
from .context import Context

from exe.exc import JobNotSupportedError


class TargetRunner(Context):
    """ Match target(s) by given pattern. """

    __RUNNER_NAME__ = "target"
    __RUNNER_MUTEX_REQUIRED__ = False

    def handle(ctx, pattern, run_async=False):
        if not run_async:
            return ctx.executor().target(pattern)
        # This should never happen
        raise JobNotSupportedError("{0} can not run under "
                                   "async mode.".format(self.runner_name))
