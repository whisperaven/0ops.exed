# -*- coding: utf-8 -*-

try:
    import httplib as status
except ImportError:
    import http.client as status


## API Error Messages ##
ERR_NO_MATCH = "no hosts match that target"
ERR_NO_TARGET = "no target(s) given"
ERR_NO_JID = "no jid given"
ERR_BAD_ROLE = "role should be string types"
ERR_BAD_PARTIAL = "partial should be string types and cannot be empty"
ERR_BAD_EXTRAVARS = "extra vars should be an json object"
ERR_BAD_EXTRAOPTS = "extra opts for release handler should be an json object"
ERR_BAD_SERVPARAMS = "bad service name or state"
ERR_BAD_APPPARAMS = "bad app info params"
ERR_BAD_RELPARAMS = "bad release params"
ERR_JOB_NOT_EXISTS = "job not exists"

## Service State Emum ##
STATE_STARTED = 0
STATE_STOPED = 1
STATE_RESTARTED = 2
