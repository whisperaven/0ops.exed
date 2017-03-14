# -*- coding: utf-8 -*-

import json

import cherrypy

from .utils import *
from .consts import *
from .handler import EndpointHandler

from exe.runner import JobQuerier


@cherrypy.expose
class JobQueryHandler(EndpointHandler):
    """ Endpoint Handler: `/job`. """

    __RUNNER__ = JobQuerier

    def GET(self, jid=None, **params):
        """ List or gather job info. """
        detail = parse_params_bool(params, 'detail')
        follow = parse_params_bool(params, 'follow')
        outputs = parse_params_bool(params, 'outputs')
        return response(status.OK, self.handle(jid, outputs, follow, detail))
    GET._cp_config = {'tools.json_stream_output.on': True, 'response.stream': True}

    @cherrypy.tools.json_out()
    def DELETE(self, jid=None):
        """ Delete (reaper) a job. """
        if not jid:
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_NO_JID)
        return response(status.NO_CONTENT, self.handle(jid, delete=True))
