# (c) 2016, Hao Feng <whisperaven@gmail.com>

from sys import exc_info


__all__ = ["excinst"]


def excinst():
    """ Exception instance inside try/except block. """
    return exc_info()[1]
