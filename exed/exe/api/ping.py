# -*- coding: utf-8 -*-

import cherrypy

from .handler import CommonHandler

from exe.runner import PingRunner


@cherrypy.expose
class PingHandler(CommonHandler):
    """ Endpoint Handler: `/ping`. """

    __RUNNER__ = PingRunner
