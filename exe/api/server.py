# (c) 2016, Hao Feng <whisperaven@gmail.com>

import logging

import cherrypy

from .job import JobQueryHandler
from .target import TargetHandler
from .ping import PingHandler
from .facter import FacterHandler
from .deploy import DeployHandler
from .service import ServiceHandler
from .execute import ExecuteHandler
from .task import TaskHandler
from .utils import error_response
from .consts import *

from exe.exc import ConfigError
from exe.utils.cfg import CONF, ModuleOpts


LOG = logging.getLogger(__name__)


class APIServer(object):
    """ Root application and api server instance. """

    _SERVER_TOKEN = API_SERVER_TOKEN
    _ENDPOINT_MAP = {
        '/jobs'    : JobQueryHandler,
        '/target'  : TargetHandler,
        '/ping'    : PingHandler,
        '/facter'  : FacterHandler,
        '/deploy'  : DeployHandler,
        '/service' : ServiceHandler,
        '/execute' : ExecuteHandler,
        '/task'    : TaskHandler,
    }

    def __init__(self):
        """ Initialize APIServer instance. """
        try:
            self._cfg = CONF.api_server
            self._cfg.merge(API_SERVER_DEFAULT_CONF)
        except ConfigError:
            self._cfg = ModuleOpts("", API_SERVER_DEFAULT_CONF)

        self._mount_endpoints()
        self._update_config()

    def _make_dispatch_conf(self):
        """ Set request dispatcher to ``MethodDispatcher``.

        Search ``request.dispatch`` using path inside ``Application`` object
        ``_cptree.Appliction.find_config(path, 'request.dispatch', ...).``
        """
        return {'/': {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}}

    def _mount_endpoints(self):
        """ Mount handlers to endpoints.

        Right after mount, we should also set the right request dispatcher
        for each request, we can't do this in ``_update_config()`` just
        because cherrypy will search this configuration using ``path_info``
        before any configuration got loaded.
        """
        for uri, handler in APIServer._ENDPOINT_MAP.items():
            cherrypy.tree.mount(handler(), uri, self._make_dispatch_conf())

    def _update_config(self):
        """ Update CherryPy configurations. """
        _cp_config = {
            # Server Opts #
            'server.socket_host': self._cfg.listen_addr,
            'server.socket_port': self._cfg.listen_port,
            'server.thread_pool': 10,
            'engine.autoreload.on': False,
            # Log Opts #
            'log.screen': False,
            'log.error_file': "",
            'log.access_file': "",
            # Request Opts #
            'request.show_tracebacks': False,
            'request.show_mismatched_params': False,
            'response.headers.server': APIServer._SERVER_TOKEN,
            # Custom Tools Opts #
            'tools.delete_allow_header.on': True,
            'tools.fix_http_content_length.on': True,
            # 'tools.encode.on': True,
            # 'tools.encode.encoding': 'utf-8',
            # Error Handling Opts #
            'error_page.default': error_response,
        }
        cherrypy.config.update(_cp_config)
        cherrypy.log.error_log = LOG

    def set_access_log(self, handler):
        """ Setting CherryPy access logger. """
        cherrypy.log.access_log.addHandler(handler)

    def run(self, daemon=False):
        """ Run APIServer instance. """
        if daemon:
            daemon = cherrypy.process.plugins.Daemonizer(cherrypy.engine)
            daemon.subscribe()
        if self._cfg.pid_file:
            pid = cherrypy.process.plugins.PIDFile(cherrypy.engine, self._cfg.pid_file)
            pid.subscribe()
        cherrypy.engine.start()
        cherrypy.engine.block()
        return 0
