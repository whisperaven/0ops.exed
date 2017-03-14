# -*- coding: utf-8 -*-

import six
import cherrypy

from .utils import *
from .consts import *
from .handler import EndpointHandler

from exe.runner import ReleaseRunner


@cherrypy.expose
class ReleaseHandler(EndpointHandler):
    """ Endpoint Handler: `/release`. """

    __RUNNER__ = ReleaseRunner

    @cherrypy.tools.json_out()
    def GET(self, **params):
        """ Release handler meta data query. """
        return response(status.OK, self.runner.query())

    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    def POST(self):
        """ Release revision of app on remote host(s). """
        targets = cherrypy.request.json.pop('targets', None)
        if not targets or not isinstance(targets, list):
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_NO_TARGET)

        appname = cherrypy.request.json.pop('appname', None)
        apptype = cherrypy.request.json.pop('apptype', None)
        revision = cherrypy.request.json.pop('revision', None)
        for val in (appname, apptype, revision):
            if not val or not isinstance(val, six.text_type):
                raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_BAD_APPPARAMS)

        rollback = cherrypy.request.json.pop('rollback', False)
        if not isinstance(rollback, bool):
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_BAD_RELPARAMS)

        extra_opts = cherrypy.request.json.pop('extra_opts', dict())
        if not isinstance(extra_opts, dict):
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_BAD_EXTRAOPTS)

        jid = self.handle(targets, appname, apptype, revision, rollback, extra_opts, async=True)
        return response(status.CREATED, dict(jid=jid))
