# -*- coding: utf-8 -*-

import cherrypy

from exe.runner import PingRunner
from .handler import CommonHandler


@cherrypy.expose
class PingHandler(CommonHandler):
    """ Endpoint Handler: `/ping`. """

    __RUNNER__ = PingRunner
