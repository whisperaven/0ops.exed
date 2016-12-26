# -*- coding: utf-8 -*-

from .prototype import ReleaseHandlerPrototype


## common release handler ##
class CommonReleaseHandler(ReleaseHandlerPrototype):
    """ Common release handler, a good example about how to write `ReleaseHandler`. """

    __RHANDLER_NAME__ = "common"
    __RHANDLER_TYPE__ = "common"
    __SUPPORTED_APP__ = ("common", "simple")

    def release(self, revision, **extra_opts):
        pass

    def rollback(self, revision, **extra_opts):
        pass

    def revision(self, **extra_opts):
        pass

