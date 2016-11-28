#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import os.path


def make_abs_path(path, parent=None):
    """ Auto complate path by add prefix `parent` if `path` is not abs-path. """
    if not os.path.isabs(path):
        if not parent:
            parent = os.getcwd()
        return os.path.join(parent, path)
    return path

