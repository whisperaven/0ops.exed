# -*- coding: utf-8 -*-

import json
import inspect
import logging

try:
    from html import unescape
except ImportError:
    unescape = None
try:
    from html.parser import HTMLParser
except ImportError:
    from HTMLParser import HTMLParser

import six
import cherrypy
from cherrypy._cptools import HandlerWrapperTool

from .consts import *

LOG = logging.getLogger(__name__)


## Middware/CherrypyTools ##
# Not in use, because some bad uri will return 400 frist, not 404
@cherrypy.tools.register('before_handler')
def params_check_target():
    """ Check the request params contains 'target' or not. """
    if not cherrypy.request.params.has_key('target'):
        raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_NO_TARGET)


@cherrypy.tools.register('before_finalize')
def fix_http_content_length():
    """ Reverse operate done by cherrypys `_be_ie_unfriendly`. """
    response = cherrypy.serving.response
    if not inspect.isgenerator(response.body): # Dont do this in `stream` mode
        response.body = response.collapse_body().strip()
        response.headers['Content-Length'] = str(len(response.collapse_body())) 


@cherrypy.tools.register('before_finalize')
def unescape_response():
    """ Unescape the html body which escaped by `_cpcompat.escape_html()`. """
    response = cherrypy.serving.response
    if not inspect.isgenerator(response.body): # Dont do this in `stream` mode
        response.body = six.binary_type(unescape_html(response.collapse_body()))


@cherrypy.tools.register('before_finalize')
def delete_allow_header():
    """ Delete the `Allow` header which set by `MethodDispatcher`. """
    response = cherrypy.serving.response
    response.headers.pop('Allow', None)


def _json_stream_output(next_handler, *args, **kwargs):
    """ Output JSON in stream mode. """
    cherrypy.response.headers['Content-Type'] = "application/json"
    _outputs = next_handler(*args, **kwargs)
    if inspect.isgenerator(_outputs):
        def _stream_outputs():
            for _content in _outputs:
                yield json.dumps(_content)
        return _stream_outputs()
    else:
        return json.dumps(_outputs)
cherrypy.tools.json_stream_output = HandlerWrapperTool(_json_stream_output)


## Error Handling ##
def error_response(status, message, traceback, version):
    """ Global http error handler, reply with status code and message json. """
    cherrypy.response.status = status
    cherrypy.response.headers['Content-Type'] = "application/json"
    return json.dumps(dict(message=message))


# Helpers #
def unescape_html(content):
    if unescape is not None:
        return unescape(content)
    else:
        return HTMLParser().unescape(content)


def parse_params_target(params):
    """ Get the `target` from request params or raise http 400 error. """
    try:
        return params.pop('target')
    except KeyError:
        raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_NO_TARGET)


def parse_params_bool(params, p):
    """ Get and parse the `params` from request params to see if it is a true value. """
    val = params.pop(p, None)
    if not val:
        return False
    return val.lower() in ("yes", "1", "true")
    

def parse_params_int(params, p):
    """ Get and parse the `params` from request params and try to covert it to int. """
    val = params.pop(p, None)
    try:
        return int(val, 10)
    except ValueError:
        return None


def response(status, body):
    """ Set response status code and body before send them to the client,
        Note that the `json.loads()` should done by the cherrypy `json_out` tools. """
    cherrypy.response.status = status
    return body
