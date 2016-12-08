# -*- coding: utf-8 -*-

from .prototype import ReleaseHandlerPrototype
from .common import CommonReleaseHandler


HANDLERS = [CommonReleaseHandler]


__all__ = ['ReleaseHandlerPrototype', 'HANDLERS', 'CommonReleaseHandler']
