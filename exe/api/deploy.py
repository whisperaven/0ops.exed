# (c) 2016, Hao Feng <whisperaven@gmail.com>

import cherrypy

from .utils import *
from .consts import *
from .handler import EndpointHandler

from exe.runner import DeployRunner


@cherrypy.expose
class DeployHandler(EndpointHandler):
    """ Endpoint Handler: `/deploy` """

    __RUNNER__ = DeployRunner

    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    def POST(self):
        """ Deploy on remote host(s) """
        targets = cherrypy.request.json.pop('targets', [])
        if not targets or not isinstance(targets, list):
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_NO_TARGET)

        role = cherrypy.request.json.pop('role', "")
        if not role or not isinstance(role, str):
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_BAD_ROLE)

        extra_vars = cherrypy.request.json.pop('extra_vars', {})
        if not isinstance(extra_vars, dict):
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_BAD_EXTRAVARS)

        partial = cherrypy.request.json.pop('partial', None)
        if partial is not None:
            if not partial or not isinstance(partial, list):
                raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_BAD_PARTIAL)

        jid = self.handle(targets, role, extra_vars, partial, run_async=True)
        return api_response(status.CREATED, dict(jid=jid))
