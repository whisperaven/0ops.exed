# -*- coding: utf-8 -*-

from sys import exc_info


def errno():
    return exc_info()[1]
