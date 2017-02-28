# -*- coding: utf-8 -*-

import cherrypy

from .utils import *
from .consts import *
from .handler import EndpointHandler

from exe.runner import ServiceRunner


def _state_parse(state):
    restart = False
    if state == STATE_STARTED:
        start = True
    elif state == STATE_STOPED:
        start = False
    elif state == STATE_RESTARTED:
        start = True
        restart = True
    else:
        raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_BAD_SERVPARAMS)
    return start, restart

@cherrypy.expose
class ServiceHandler(EndpointHandler):
    """ Endpoint Handler: `/service`. """

    __RUNNER__ = ServiceRunner

    @cherrypy.tools.json_out()
    def GET(self, **params):
        """ Manipulate service on remote host. """
        name = params.pop('name', None)
        state = parse_params_int(params, 'state')
        target = parse_params_target(params)

        if name == None or state == None:
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_BAD_SERVPARAMS)

        name = name.lower()
        start, restart = _state_parse(state)
        graceful = parse_params_bool(params, 'graceful')

        result = self.handle(target, name, start, restart, graceful)
        if not result:
            raise cherrypy.HTTPError(status.NOT_FOUND, ERR_NO_MATCH)
        else:
            return response(status.OK, result)

    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    def POST(self):
        """ Manipulate service on remote host(s). """
        targets = cherrypy.request.json.pop('targets', None)
        if not targets or not isinstance(targets, list):
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_NO_TARGET)

        name = cherrypy.request.json.pop('name', None)
        state = cherrypy.request.json.pop('state', None)
        if name == None or state == None:
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_BAD_SERVPARAMS)

        name = name.lower()
        start, restart = _state_parse(state)
        graceful = cherrypy.request.json.pop('graceful', False)

        jid = self.handle(target, name, start, restart, graceful, async=True)
        return response(status.CREATE, dict(jid=jid))
