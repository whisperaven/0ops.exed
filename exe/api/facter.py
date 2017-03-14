# -*- coding: utf-8 -*-

import cherrypy

from .handler import CommonHandler

from exe.runner import FacterRunner


@cherrypy.expose
class FacterHandler(CommonHandler):
    """ Endpoint Handler: `/facter`. """

    __RUNNER__ = FacterRunner
