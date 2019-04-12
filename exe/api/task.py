# (c) 2016, Hao Feng <whisperaven@gmail.com>

import cherrypy

from .utils import *
from .consts import *
from .handler import EndpointHandler

from exe.runner import TaskRunner


@cherrypy.expose
class TaskHandler(EndpointHandler):
    """ Endpoint Handler: ``/task``. """

    __RUNNER__ = TaskRunner

    @cherrypy.tools.json_out()
    def GET(self, **params):
        """ Task handler meta data query. """
        return api_response(status.OK, self.runner.query())

    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    def POST(self):
        """ Task execution on remote host(s). """
        targets = cherrypy.request.json.pop('targets', [])
        if not targets or not isinstance(targets, list):
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_NO_TARGET)

        taskname = cherrypy.request.json.pop('taskname', "")
        tasktype = cherrypy.request.json.pop('tasktype', "")
        for val in (taskname, tasktype):
            if not val or not isinstance(val, str):
                raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_BAD_TSKPARAMS)

        taskopts = cherrypy.request.json.pop('taskopts', {})
        if not isinstance(extra_opts, dict):
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_BAD_EXTRAOPTS)

        jid = self.handle(targets, taskname, tasktype, extra_opts, run_async=True)
        return api_response(status.CREATED, dict(jid=jid))
