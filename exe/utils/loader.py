# -*- coding: utf-8 -*-

import os
import os.path
import sys
import logging
import importlib

from exe.utils.err import excinst

LOG = logging.getLogger(__name__)


## Consts ##
PY_EXTS = (".pyc", ".py")


class PluginLoader(object):
    """ Find and load plugins from plugin directory. """
    
    def __init__(self, plugin_pt, plugin_path):
        """ Init loader object for plugin loading. """
        self._pymodule_path = []
        self._pymodule_name = []
        self._plugin_pt = plugin_pt
        self._plugins = None

        self._find_modules(plugin_path)

    @property
    def plugins(self):
        """ Loaded plugins. """
        if self._plugins == None:
            self._plugins = self._load_plugins()
        return self._plugins

    def _load_plugins(self):
        """ Load exe plugins from imported python modules. """
        _path = sys.path
        _modules = []

        sys.path = self._pymodule_path
        for mod in self._pymodule_name:
            try:
                m = importlib.import_module(mod)
            except ImportError:
                LOG.error("bad module <{0}>, <{1}>".format(mod, excinst()))
            for attr, obj in vars(m).items():
                try:
                    if issubclass(obj, self._plugin_pt) and obj != self._plugin_pt:
                        _modules.append(obj)
                        LOG.info("module {0} loaded".format(obj))
                except TypeError:   # issubclass() arg 1 must be a class
                    continue
        sys.path = _path

        return _modules

    def _find_modules(self, module_path):
        """ Find python modules from plugin directory. """
        if os.path.isfile(module_path):
            name, ext = os.path.splitext(os.path.basename(module_path))
            if name != "__init__" \
                    and ext in PY_EXTS \
                    and '.' not in name \
                    and name not in self._pymodule_name:
                LOG.info("find module file: <{0}>".format(module_path))
                self._pymodule_path.append(os.path.dirname(module_path))
                self._pymodule_name.append(name)

        elif os.path.isdir(module_path):
            LOG.info("looking for module file in <{0}>".format(module_path))
            _files = [ f for f in os.listdir(module_path) if os.path.isfile(os.path.join(module_path, f)) ]
            for module_file in _files:
                self._find_modules(os.path.join(module_path, module_file))
