# (c) 2016, Hao Feng <whisperaven@gmail.com>

from configparser import ConfigParser
from copy import deepcopy

from exe.exc import ConfigError
from .err import excinst


__all__ = ["CONF", "ModuleOpts", "cfgread"]


class _ConfigOpts(object):
    """ Configuration modules constructor. """

    def __init__(self):
        """ Initialize ConfigOpts instance. """
        self._ctx = {}

    @property
    def modules(self):
        """ Configuration modules access. """
        return [ ModuleOpts(m, self._ctx[m]) for m in self._ctx ]

    def module(self, module_name):
        """ Configuration module access. """
        return getattr(self, module_name)

    def __iter__(self):
        return modules()

    def __getattr__(self, attr):
        try:
            return ModuleOpts(attr, self._ctx[attr])
        except KeyError:
            raise ConfigError("\"{0}\", no such configuration section".format(attr))

    def regisiter_opts(self, cfg_name, cfg_dict):
        """ Configuration module register. """
        if cfg_name in self._ctx:
            raise ConfigError("duplicated configuration section \"{0}\"".format(cfg_name))
        self._ctx[cfg_name] = cfg_dict
CONF = _ConfigOpts()


class ModuleOpts(object):
    """ Configuration module content access """

    def __init__(self, name, opts):
        """ Initialize ModuleOpts instance. """
        self._name = name
        self._opts = opts

    @property
    def name(self):
        """ Configuration module name. """
        return self._name

    @property
    def dict_opts(self):
        """ Configuration module content (dict-like content). """
        return self._opts

    def merge(self, default_cfg_dict):
        """ Merge module content with ``default_cfg_dict``. """
        _cfg = deepcopy(default_cfg_dict)
        for opt, val in _cfg.items():
            try:
                self._opts[opt] = type(val)(self._opts[opt])
            except KeyError:
                pass
            except ValueError:
                raise ConfigError("bad value type of configuration option \"{0}\"".format(opt))
        _cfg.update(self._opts)
        self._opts = _cfg

    def __getattr__(self, attr):
        try:
            return self._opts[attr]
        except KeyError:
            raise ConfigError("\"{0}\" no such configuration option".format(attr))


def cfgread(config_file):
    """ Configuration file reader, register modules to global ``CONF`` instance. """
    try:
        cfp = open(config_file)
        cfg = ConfigParser()
        cfg.read_file(cfp)
        cfp.close()
    except:
        raise ConfigError("cannot open & read configuration file, {0}".format(excinst()))

    for _cs in cfg.sections():
        CONF.regisiter_opts(_cs, dict(zip(
            [ c[0] for c in cfg.items(_cs) ],
            [ c[1].strip('\'').strip('"') for c in cfg.items(_cs) ])))

    return CONF
