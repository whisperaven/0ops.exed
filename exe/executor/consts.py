# -*- coding: utf-8 -*-

## executor result status enum ##
EXE_OK = 0
EXE_SKIPED = 1
EXE_FAILED = 2
EXE_UNREACHABLE = 3
EXE_CHANGED = 4
EXE_NO_MATCH = -1
## executor result attr ##
EXE_NAME_ATTR = "name"
EXE_STATUS_ATTR = "status"
EXE_RETURN_ATTR = "return_data"
## executor result status set ##
EXE_SUCCESS_STATES = (EXE_OK, EXE_SKIPED, EXE_CHANGED)
EXE_FAILURE_STATES = (EXE_FAILED, EXE_UNREACHABLE, EXE_NO_MATCH)
