# (c) 2016, Hao Feng <whisperaven@gmail.com>

import json
import logging

from html import unescape

import cherrypy
from cherrypy.lib import is_closable_iterator
from cherrypy._cptools import HandlerWrapperTool

from .consts import *

LOG = logging.getLogger(__name__)


## Middware/CherrypyTools ##
# Not in use, because some bad uri will return 400 frist, not 404
@cherrypy.tools.register('before_handler')
def params_check_target():
    """ Check the request params contains 'target' or not. """
    if 'target' not in cherrypy.request.params:
        raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_NO_TARGET)


# Not in use, because cherrypy does not do this in current version
@cherrypy.tools.register('before_finalize')
def unescape_response():
    """ Unescape the html body which escaped by ``_cpcompat.escape_html()``. """
    response = cherrypy.serving.response
    if not is_closable_iterator(response.body): # Dont do this for stream
        response.body = bytes(unescape_html(response.collapse_body()))


@cherrypy.tools.register('before_finalize')
def fix_http_content_length():
    """ Reverse operate done by cherrypy ``_be_ie_unfriendly``. """
    response = cherrypy.serving.response
    if not is_closable_iterator(response.body): # Dont do this for stream
        response.body = response.collapse_body().strip()
        response.headers['Content-Length'] = str(len(response.collapse_body()))


@cherrypy.tools.register('before_finalize')
def delete_allow_header():
    """ Delete the ``Allow`` header which set by ``MethodDispatcher``. """
    cherrypy.serving.response.headers.pop('Allow', None)


def _json_stream_output(next_handler, *args, **kwargs):
    """ Output JSON in stream mode. """
    outputs = next_handler(*args, **kwargs)
    response = cherrypy.serving.response

    response.headers['Content-Type'] = "application/json"

    if is_closable_iterator(outputs): # Do this only for stream
        response.stream = True
        def _stream_outputs():
            for _content in outputs:
                yield json.dumps(_content).encode('utf-8')
        return _stream_outputs()
    else:
        return json.dumps(outputs).encode('utf-8')
cherrypy.tools.json_stream_output = HandlerWrapperTool(_json_stream_output)


## Error Handling ##
def error_response(status, message, traceback, version):
    """ Global http error handler, reply with status code and message json. """
    cherrypy.response.status = status
    cherrypy.response.headers['Content-Type'] = "application/json"
    return json.dumps(dict(message=message))


# Helpers #
def unescape_html(content):
    return unescape(content)


def parse_params_target(params):
    """ Get the ``target`` from request params or raise http 400 error. """
    try:
        targets = params.pop('target')
        if not isinstance(target, list):
            raise KeyError
        return targets
    except KeyError:
        raise cherrypy.HTTPError(status.BAD_REQUEST, ERR_NO_TARGET)


def parse_params_bool(params, p):
    """ Get and parse a boolean value from request params. """
    val = params.pop(p, None)
    if not val:
        return False
    return val.lower() in ("yes", "1", "true")
    

def parse_params_int(params, p):
    """ Get and parse an int value from request params. """
    val = params.pop(p, None)
    try:
        return int(val, 10)
    except ValueError:
        return None


def api_response(status, body):
    """ Set response status code and body before send them to the client.

    Note that we should't invoke ``json.loads()`` because all json things
    should handled by ``cherrypy.tools.json_out`` tools. """
    cherrypy.serving.response.status = status
    return body
