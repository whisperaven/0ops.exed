# (c) 2016, Hao Feng <whisperaven@gmail.com>

from urllib.parse import unquote

import cherrypy

from .utils import *
from .consts import *
from .handler import EndpointHandler

from exe.runner import ExecuteRunner


@cherrypy.expose
class ExecuteHandler(EndpointHandler):
    """ Endpoint Handler: ``/execute``. """

    __RUNNER__ = ExecuteRunner

    @cherrypy.tools.json_out()
    def GET(self, **params):
        """ Execute command on remote host. """
        target = parse_params_target(params)
        cmd = params.pop('cmd', "")
        if not cmd or not isinstance(cmd, str):
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_BAD_SERVPARAMS)
        cmd = unquote(cmd)

        result = self.handle(target, cmd)
        if not result:
            raise cherrypy.HTTPError(status.NOT_FOUND, ERR_NO_MATCH)
        else:
            return api_response(status.OK, result)

    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    def POST(self, **params):
        """ Execute command on remote host(s). """
        targets = cherrypy.request.json.pop('targets', [])
        if not targets or not isinstance(targets, list):
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_NO_TARGET)

        cmd = cherrypy.request.json.pop('cmd', "")
        if not cmd or not isinstance(cmd, str):
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_BAD_ROLE)

        jid = self.handle(targets, cmd, run_async=True)
        return api_response(status.CREATED, dict(jid=jid))
