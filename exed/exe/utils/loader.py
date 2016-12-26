# -*- coding: utf-8 -*-

import os
import os.path
import sys
import logging
import importlib

LOG = logging.getLogger(__name__)

## Consts ##
PY_EXTS = (".pyc", ".py")


class PluginLoader(object):
    
    def __init__(self, module_pt, module_path, modules=[]):

        self._module_path = []
        self._module_name = []
        self._module_pt = module_pt
        self._modules = None

        self._find_modules(module_path)

    @property
    def modules(self):
        if self._modules == None:
            self._modules = self._load_modules()
        return self._modules

    def _load_modules(self):

        _path = sys.path
        _modules = []

        sys.path = self._module_path
        for mod in self._module_name:
            m = importlib.import_module(mod)
            for attr, obj in vars(m).items():
                try:
                    if issubclass(obj, self._module_pt) and obj != self._module_pt:
                        _modules.append(obj)
                        LOG.info("module {0} loaded".format(obj))
                except TypeError:   # issubclass() arg 1 must be a class
                    continue
        sys.path = _path

        return _modules

    def _find_modules(self, module_path):

        if os.path.isfile(module_path):
            name, ext = os.path.splitext(os.path.basename(module_path))
            if name != "__init__" and '.' not in name and ext in PY_EXTS:
                self._module_path.append(os.path.dirname(module_path))
                if name not in self._module_name:
                    self._module_name.append(name)
                    LOG.debug("find module file: <{0}>".format(module_path))

        elif os.path.isdir(module_path):
            LOG.debug("looking for module file in <{0}>".format(module_path))
            _files = [ f for f in os.listdir(module_path) if os.path.isfile(os.path.join(module_path, f)) ]
            for module_file in _files:
                self._find_modules(os.path.join(module_path, module_file))

