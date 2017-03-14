# -*- coding: utf-8 -*-

import logging
import logging.handlers

import cherrypy

from .job import JobQueryHandler
from .target import TargetHandler
from .ping import PingHandler
from .facter import FacterHandler
from .deploy import DeployHandler
from .service import ServiceHandler
from .execute import ExecuteHandler
from .release import ReleaseHandler
from .utils import error_response

from exe.cfg import CONF, ModuleOpts
from exe.exc import ConfigError
from exe.utils.log import open_logfile

LOG = logging.getLogger(__name__)


## Consts ##
DEFAULT_CONF = {
    'listen': "127.0.0.1",
    'listen_port': 16808,
    'pid_file': "",
}


## Goloal Application of cherrypy and ApiServer ##
class APIServer(object):
    """ Root Application and Api Server. """

    API_CONF = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
        }
    }

    SERVER_TOKEN = "0ops Api Server"
    ENDPOINT_MAP = {
        '/jobs': JobQueryHandler,
        '/target': TargetHandler,
        '/ping': PingHandler,
        '/facter': FacterHandler,
        '/deploy': DeployHandler,
        '/service': ServiceHandler,
        '/execute': ExecuteHandler,
        '/release': ReleaseHandler,
    }

    def __init__(self):
        try:
            self._cfg = CONF.api
        except ConfigError:
            self._cfg = ModuleOpts("", DEFAULT_CONF)
        self._cfg.merge(DEFAULT_CONF)

        self._update_config()
        self._mount_endpoints()

    def _mount_endpoints(self):
        for uri, handler in APIServer.ENDPOINT_MAP.items():
            cherrypy.tree.mount(handler(), uri, APIServer.API_CONF)

    def _update_config(self):
        _cp_config = {
            ## Server Opts ##
            'log.screen': False,
            'log.error_file': "",
            'log.access_file': "",
            'server.socket_host': self._cfg.listen,
            'server.socket_port': self._cfg.listen_port,
            'server.thread_pool': 10,
            'engine.autoreload.on': False,
            'request.show_tracebacks': False,
            'request.show_mismatched_params': False,
            'response.headers.server': APIServer.SERVER_TOKEN,
            ## Custom Tools Opts ##
            'tools.delete_allow_header.on': True,
            'tools.fix_http_content_length.on': True,
            'tools.unescape_response.on': True,
            ## Error Handling Opts ##
            'error_page.default': error_response,
        }
        cherrypy.config.update(_cp_config)
        cherrypy.log.error_log = LOG

    def set_access_log(self, handler):
        cherrypy.log.access_log.addHandler(handler)

    def run(self, daemon=False):
        if daemon:
            daemon = cherrypy.process.plugins.Daemonizer(cherrypy.engine)
            daemon.subscribe()
        if self._cfg.pid_file:
            pid = cherrypy.process.plugins.PIDFile(cherrypy.engine, self._cfg.pid_file)
            pid.subscribe()
        cherrypy.engine.start()
        cherrypy.engine.block()
