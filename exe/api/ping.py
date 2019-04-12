# (c) 2016, Hao Feng <whisperaven@gmail.com>

import cherrypy

from .handler import CommonHandler

from exe.runner import PingRunner


@cherrypy.expose
class PingHandler(CommonHandler):
    """ Endpoint Handler: ``/ping``. """

    __RUNNER__ = PingRunner
