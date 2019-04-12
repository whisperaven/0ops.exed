# (c) 2016, Hao Feng <whisperaven@gmail.com>

import http.client as status

## API Error Messages ##
ERR_NO_MATCH       = "no hosts match that target"
ERR_NO_TARGET      = "no target(s) given"
ERR_NO_JID         = "no jid given"
ERR_BAD_ROLE       = "role should be string types"
ERR_BAD_PARTIAL    = "partial should be string list or omitted"
ERR_BAD_EXTRAVARS  = "extra vars should be an json object or omitted"
ERR_BAD_EXTRAOPTS  = "extra opts for task handler should be an json object"
ERR_BAD_SERVPARAMS = "bad service name or state"
ERR_BAD_TSKPARAMS  = "bad task params"
ERR_JOB_NOT_EXISTS = "job not exists"

## Remote Service State Emum ##
STATE_STARTED   = 0
STATE_STOPED    = 1
STATE_RESTARTED = 2

## API Server Default Configurations ##
API_SERVER_DEFAULT_CONF = dict(
    listen_addr = "127.0.0.1",
    listen_port = 16808,
    pid_file    = ""
)

## Server Consts ##
API_SERVER_TOKEN = "0ops Api Server"
