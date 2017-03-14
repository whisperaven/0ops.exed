# -*- coding: utf-8 -*-

from .consts import *


def isExeSuccess(retval):
    """ Return `True` when retval with successful state. """
    return retval.get(EXE_STATUS_ATTR) in EXE_SUCCESS_STATES


def isExeFailure(retval):
    """ Return `True` when retval with failed state. """
    return retval.get(EXE_STATUS_ATTR) in EXE_FAILURE_STATES


def isExeSuccessState(state):
    """ Return `True` when state is successful state. """
    return state in EXE_SUCCESS_STATES


def isExeFailureState(state):
    """ Return `True` when state is failure state. """
    return state in EXE_FAILURE_STATES


def parse_exe_return(return_data):
    """ Parse and return `target, retval` of `Executor`s yield data. """
    return return_data.popitem()


def parse_exe_retval(retval):
    """ Parse and return `state, name, retval` of `Executor`s yield data. """
    return retval.pop(EXE_STATUS_ATTR), retval.pop(EXE_NAME_ATTR, None), retval.pop(EXE_RETURN_ATTR, None)


def create_exe_retval(state, name, retval):
    """ Create an exe retval dict with given `state, name, retval` data. """
    return {EXE_STATUS_ATTR: state, EXE_NAME_ATTR: name, EXE_RETURN_ATTR: retval}


def exe_retval_state(retval):
    """ Parse and return `state` of `Executor`s yield data. """
    return retval.pop(EXE_STATUS_ATTR)
