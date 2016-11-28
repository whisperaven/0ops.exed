# -*- coding: utf-8 -*-

import logging
import logging.handlers

import cherrypy

from exe.cfg import CONF, ModuleOpts
from exe.exc import ConfigError
from exe.utils.err import errno

from .job import JobQueryHandler
from .target import TargetHandler
from .ping import PingHandler
from .facter import FacterHandler
from .deploy import DeployHandler
from .service import ServiceHandler
from .execute import ExecuteHandler
from .utils import error_response

LOG = logging.getLogger(__name__)


## Consts ##
DEFAULT_CONF = {
    'listen': "127.0.0.1",
    'listen_port': 16808,
}


## Goloal Application of cherrypy and ApiServer ##
class APIServer(object):
    """ Root Application and Api Server. """

    API_CONF = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'request.show_mismatched_params': False,
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
            'server.socket_host': self._cfg.listen,
            'server.socket_port': self._cfg.listen_port,
            'engine.autoreload.on': True,
            'log.screen': False,
            ## Custom Tools Opts ##
            'tools.delete_allow_header.on': True,
            'tools.fix_http_content_length.on': True,
            ## Error Handling Opts ##
            'error_page.default': error_response,
        }
        cherrypy.config.update(_cp_config)

    def logger_init(self, access_log_handler):
        cherrypy.log.error_log = LOG
        cherrypy.log.access_log.addHandler(access_log_handler)

    def run(self, daemon=False):
        cherrypy.engine.unsubscribe('graceful', cherrypy.log.reopen_files)
        cherrypy.engine.start()
        cherrypy.engine.block()

