# -*- coding: utf-8 -*-

from copy import deepcopy

from exe.exc import ConfigError


__all__ = ['CONF', 'ModuleOpts']


class _ConfigOpts(object):

    def __init__(self):
        self.ctx = {}

    @property
    def modules(self):
        return [ ModuleOpts(m, self.ctx[m]) for m in self.ctx.keys() ]

    def module(self, module_name):
        return getattr(self, module_name)

    def __iter__(self):
        return modules()

    def __getattr__(self, attr):
        try:
            return ModuleOpts(attr, self.ctx[attr])
        except KeyError:
            raise ConfigError("\"{0}\", no such config section.".format(attr))

    def regisiter_opts(self, cfg_name, cfg_dict):
        if self.ctx.has_key(cfg_name):
            raise ConfigError("duplicated config section \"{0}\".".format(cfg_name))
        self.ctx[cfg_name] = cfg_dict


class ModuleOpts(object):

    def __init__(self, name, opts):
        self._name = name
        self._opts = opts

    @property
    def name(self):
        return self._name

    @property
    def dict_opts(self):
        return self._opts

    def merge(self, default_cfg_dict):
        cfg = deepcopy(default_cfg_dict)
        for opt, val in cfg.iteritems():
            try:
                self._opts[opt] = type(val)(self._opts[opt])
            except KeyError:
                pass
            except ValueError:
                raise ConfigError("bad value type of config opt \"{0}\".".format(opt))
        cfg.update(self._opts)
        self._opts = cfg

    def __getattr__(self, attr):
        try:
            return self._opts[attr]
        except KeyError:
            raise ConfigError("\"{0}\" no such config option.".format(attr))

CONF = _ConfigOpts()
