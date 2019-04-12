#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Exceptions ##
class ExeError(Exception):
    """ Base exception for all errors raised from EXE code """

    def __init__(self, message=""):
        self.message = message

    def __str__(self):
        return self.message

    def __repr__(self):
        return self.message


## Config Errors ##
class ConfigError(ExeError):
    pass


## Job Errors ##
class JobNotSupportedError(ExeError):
    pass


class JobNotExistsError(ExeError):
    pass


class JobConflictError(ExeError):
    pass


class JobDeleteError(ExeError):
    pass


## TaskRunner Errors ##
class TaskNotSupportedError(ExeError):
    pass


## Executor Errors ##
class ExecutorPrepareError(ExeError):
    pass


class ExecutorNoMatchError(ExeError):
    pass


class ExecutorDeployError(ExeError):
    pass


## Task Errors ##
class TaskPrepareError(ExeError):
    pass


class TaskError(ExeError):
    pass


class TaskAbort(ExeError):
    pass
