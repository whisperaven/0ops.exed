# -*- coding: utf-8 -*-

import cherrypy

try:
    from urllib.parse import unquote
except ImportError:
    from urllib import unquote

from exe.runner import TargetRunner

from .utils import *
from .consts import *
from .handler import EndpointHandler


@cherrypy.expose
class TargetHandler(EndpointHandler):
    """ Endpoint Handler: `/target`. """

    __RUNNER__ = TargetRunner

    @cherrypy.tools.json_out()
    def GET(self, **params):
        """ Match target(s) by given pattern. """

        pattern = params.pop('pattern', None)
        if pattern == None:
            pattern = '*'
        pattern = unquote(pattern)

        return self.handle(pattern)
        
