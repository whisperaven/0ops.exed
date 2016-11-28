# -*- coding: utf-8 -*-

import six
import cherrypy

from exe.runner import DeployRunner

from .utils import *
from .consts import *
from .handler import EndpointHandler


@cherrypy.expose
class DeployHandler(EndpointHandler):
    """ Endpoint Handler: `/deploy`. """

    __RUNNER__ = DeployRunner

    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    def POST(self):
        """ Deploy on remote host(s). """

        targets = cherrypy.request.json.pop('targets', None)
        if not targets or not isinstance(targets, list):
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_NO_TARGET)

        role = cherrypy.request.json.pop('role', None)
        if not role or not isinstance(role, six.text_type):
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_BAD_ROLE)

        extra_vars = cherrypy.request.json.pop('extra_vars', dict())
        if not isinstance(extra_vars, dict):
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_BAD_EXTRAVARS)

        jid = self.handle(targets, role, extra_vars, async=True)
        return response(status.CREATED, dict(jid=jid))
