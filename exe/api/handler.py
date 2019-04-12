# (c) 2016, Hao Feng <whisperaven@gmail.com>

import cherrypy

from .utils import *
from .consts import *

from exe.exc import ExecutorNoMatchError
from exe.exc import JobConflictError
from exe.exc import JobNotExistsError
from exe.exc import JobNotSupportedError
from exe.exc import JobDeleteError
from exe.utils.err import excinst


class EndpointHandler(object):
    """ Base class for all api endpoint handlers. """

    __RUNNER__ = None

    def __init__(self):
        """ Associate runner instance to this endpoint handler. """
        if self.__RUNNER__ != None:
            self._runner = self.__RUNNER__()

    @property
    def runner(self):
        """ Runner instance access. """
        return self._runner

    def handle(self, *args, **kwargs):
        """ Handle api request by invoke ``runner.handle()``.

        All exception raised by runner will be catched here, and convert them
        into cherrypy `HTTPError()` with corresponding status code and message.
        """
        try:
            return self._runner.handle(*args, **kwargs)
        except JobDeleteError:
            raise cherrypy.HTTPError(status.BAD_REQUEST, excinst().message)
        except JobConflictError:
            raise cherrypy.HTTPError(status.CONFLICT, excinst().message)
        except JobNotSupportedError:
            raise cherrypy.HTTPError(status.INTERNAL_SERVER_ERROR,
                                     excinst().message)
        except (JobNotExistsError, ExecutorNoMatchError):
            raise cherrypy.HTTPError(status.NOT_FOUND, excinst().message)
        except:
            cherrypy.log("error response 500", traceback=True)
            raise cherrypy.HTTPError(status.INTERNAL_SERVER_ERROR)


class CommonHandler(EndpointHandler):
    """ Common endpoint handler for very simple operate. """

    @cherrypy.tools.json_out()
    def GET(self, **params):
        """ Work on remote host (block mode). """
        target = parse_params_target(params)
        result = self.handle(target)
        if not result:
            raise cherrypy.HTTPError(status.NOT_FOUND, ERR_NO_MATCH)
        else:
            return api_response(status.OK, result)

    @cherrypy.tools.json_in(force=False)
    @cherrypy.tools.json_out()
    def POST(self):
        """ Work on remote host(s) (non-block mode). """
        targets = cherrypy.request.json.pop('targets', [])
        if not targets or not isinstance(targets, list):
            raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_NO_TARGET)
        jid = self.handle(targets, run_async=True)
        return api_response(status.CREATED, dict(jid = jid))
