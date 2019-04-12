# (c) 2016, Hao Feng <whisperaven@gmail.com>

## Executor Result Status Enum ##
EXE_ANNOUNCE    = 0
EXE_OK          = 1
EXE_SKIPED      = 2
EXE_FAILED      = 3
EXE_UNREACHABLE = 4
EXE_CHANGED     = 5
EXE_NO_MATCH    = -1

## Executor Result Status Name ##
EXE_STATUS_MAP = {
    EXE_ANNOUNCE    : "ANNOUNCE",
    EXE_OK          : "OK",
    EXE_SKIPED      : "SKIPED",
    EXE_FAILED      : "FAILED",
    EXE_UNREACHABLE : "UNREACHABLE",
    EXE_CHANGED     : "CHANGED",
    EXE_NO_MATCH    : "NO MATCH",
}

## Executor Result Attr ##
EXE_NAME_ATTR = "name"
EXE_STATUS_ATTR = "status"
EXE_RETURN_ATTR = "return_data"
EXE_ANNOUNCE_ATTR = "__ANNOUNCE__"
EXE_ANNOUNCE_SUMMARY_ATTR = "__ANNOUNCE_SUMMARY__"

## Executor Result Status Set ##
EXE_SUCCESS_STATES = (EXE_OK, EXE_SKIPED, EXE_CHANGED, EXE_ANNOUNCE)
EXE_FAILURE_STATES = (EXE_FAILED, EXE_UNREACHABLE, EXE_NO_MATCH)

## Executor Consts ##
EXECUTOR_UNSET = None
