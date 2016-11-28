# -*- coding: utf-8 -*-

import cherrypy

from exe.runner import FacterRunner
from .handler import CommonHandler


@cherrypy.expose
class FacterHandler(CommonHandler):
    """ Endpoint Handler: `/facter`. """

    __RUNNER__ = FacterRunner
