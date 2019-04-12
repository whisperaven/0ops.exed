# (c) 2016, Hao Feng <whisperaven@gmail.com>

from .consts import *


__all__ = ["exec_success", "exec_failure", "execstate_name",
           "execstate_success", "execstate_failure", "execstate_announce",
           "decompose_exec_yielddata", "decompose_exec_returncontext",
           "compose_exec_returncontext", "extract_return_state"]


def exec_success(return_context):
    """ Return ``True`` when return context with successful state. """
    return return_context.get(EXE_STATUS_ATTR) in EXE_SUCCESS_STATES


def exec_failure(return_context):
    """ Return ``True`` when return context with failed state. """
    return return_context.get(EXE_STATUS_ATTR) in EXE_FAILURE_STATES


def execstate_announce(state):
    """ Return ``True`` when state is announce state. """
    return state == EXE_ANNOUNCE


def execstate_success(state):
    """ Return ``True`` when state is successful state. """
    return state in EXE_SUCCESS_STATES


def execstate_failure(state):
    """ Return ``True`` when state is failure state. """
    return state in EXE_FAILURE_STATES


def execstate_name(state):
    """ Return string represent the name of that state. """
    try:
        return EXE_STATUS_MAP[state]
    except KeyError: # this should never happen
        return EXE_STATUS_MAP[EXE_FAILED]


def decompose_exec_yielddata(yield_data):
    """ Decompose ``Executor``s yield data, return a pair which contains
    remote host and its return context represent as ``(host, context)``. """
    return yield_data.popitem()


def decompose_exec_returncontext(return_context):
    """ Decompose ``Executor``s return data, return a tuple which contains
    remote execution state and thier operation name and context represent
    as ``(state, name, context)``. """
    return (return_context.pop(EXE_STATUS_ATTR),
            return_context.pop(EXE_NAME_ATTR, None),
            return_context.pop(EXE_RETURN_ATTR, None))


def compose_exec_returncontext(state, name, return_context):
    """ Compose an exec return data dict with given execution state and
    operation name and return context dict or something else. """
    return {EXE_STATUS_ATTR : state,
            EXE_NAME_ATTR   : name,
            EXE_RETURN_ATTR : return_context}


def extract_return_state(return_context):
    """ Extract return state from remote host's return context. """
    return return_context.pop(EXE_STATUS_ATTR)
