# -*- coding: utf-8 -*-

import os
import sys
import os.path
import logging
import multiprocessing

from ansible.playbook.play import Play
from ansible.inventory import Inventory
from ansible.vars import VariableManager
from ansible.parsing.dataloader import DataLoader
from ansible.plugins.callback import CallbackBase
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.parsing.splitter import parse_kv
from ansible.errors import AnsibleError

from .consts import *
from .prototype import ExecutorPrototype

from exe.utils.err import excinst
from exe.utils.path import make_abs_path
from exe.exc import ExecutorPrepareError, ExecutorDeployError, ExecutorNoMatchError

LOG = logging.getLogger(__name__)


## ansible options ##
class AnsibleOpts(object):
    """ Ansible options helper. """
    
    def __init__(self, **kargs):
        for opt, val in kargs.items():
            setattr(self, opt, val)

    def __setattr__(self, attr, val):
        object.__setattr__(self, attr, val)

    def __getattr__(self, attr):
        return None


## ansible reaper ##
class AnsibleReaper(CallbackBase):
    """ Ansible reaper for result collect, act as Ansible Callback. """

    REAPER_DONE = -1

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stdout'
    CALLBACK_NAME = 'exe_executor'

    def __init__(self, hosts):
        self._task_ctx = None
        self._item_ctx = None
        # ansible doesn't have callback to tell us
        #   there is no host matched, so we do that 
        #   check by ourself by using this list.
        self._hosts = hosts
        # ansible run jobs by `fork()` workers,
        #   shm will make those control vars synced.
        self._reaper_queue = multiprocessing.Queue()
        self._playbook_mode = multiprocessing.Value('I', 0)

    def _set_playbook_mode(self):
        self._playbook_mode.value = 1

    def _set_task_ctx(self, task):
        self._task_ctx = task if self._playbook_mode.value else None

    def _set_item_ctx(self, item=None):
        self._item_ctx = item

    def _runner_return(self, result, ignore_errors=False):
        host = result._host.get_name()

        if result.is_skipped():
            _status = EXE_SKIPED
        elif result.is_unreachable():
            _status = EXE_UNREACHABLE
        elif result.is_failed():
            _status = EXE_FAILED if not ignore_errors else EXE_SKIPED
        elif result.is_changed():
            _status = EXE_CHANGED
        else:
            _status = EXE_OK

        if self._task_ctx != None:
            _name = self._task_ctx.get_name()
        else:
            _name = None

        if self._item_ctx != None:
            _name += " -> {0}".format(self._item_ctx)

        self._reaper_queue.put({
            host: {
                EXE_NAME_ATTR: _name,
                EXE_STATUS_ATTR: _status,
                EXE_RETURN_ATTR: result._result
                }})

    def reaper_exception(self, exc):
        self._reaper_queue.put(exc)

    def reaper(self):
        while True:
            result = self._reaper_queue.get()
            # riase the internal exception which wrapped
            #   by the `try/except` block inside both
            #   `self._run_pbs` and `self._run_tasks`.
            if isinstance(result, Exception):
                raise result
            if result == self.REAPER_DONE:
                self._reaper_queue.close()
                if len(self._hosts) != 0:
                    raise ExecutorNoMatchError("no host match <{0}>".format(", ".join(self._hosts)))
                break
            else:
                # check for no host match
                host = result.keys()[0]
                if host in self._hosts:
                    self._hosts.remove(host)
                yield result

    def done(self):
        self._reaper_queue.put(self.REAPER_DONE)

    def v2_playbook_on_start(self, playbook):
        self._set_playbook_mode()

    def v2_playbook_on_task_start(self, task, is_conditional):
        self._set_task_ctx(task)

    def v2_playbook_on_handler_task_start(self, task):
        self._set_task_ctx(task)

    def v2_runner_on_ok(self, result):
        self._set_item_ctx() # clean the item ctx
        self._runner_return(result)

    def v2_runner_on_skipped(self, result):
        self._runner_return(result)

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self._runner_return(result, ignore_errors)

    def v2_runner_on_unreachable(self, result):
        self._runner_return(result)

    def v2_runner_item_on_ok(self, result):
        self._set_item_ctx(result._result.get('item', None))
        self._runner_return(result)

    def v2_runner_item_on_skipped(self, result):
        self._set_item_ctx(result._result.get('item', None))
        self._runner_return(result)

    def v2_runner_item_on_failed(self, result):
        self._set_item_ctx(result._result.get('item', None))
        self._runner_return(result)

## ansible executor ##
class AnsibleExecutor(ExecutorPrototype):
    """ Executor implemented on top of ansible. """

    __EXECUTOR_NAME__ = "ansible"

    FORK = 10
    RAW_ARG = "_RAW"
    INVENTORY = "inventory"
    PLAYBOOKS = "playbooks"

    CMD_MODULE = "shell"
    PING_MODULE = "ping"
    FACTER_MODULE = "facter"
    SERVICE_MODULE = "service"

    RAW_MODULE = ('command', 'shell', 'script', 'raw')
    INIT_PB = "_deploy.yml"
    ROLE_VAR = "_role"
    TARGET_VAR = "_targets"
    DEFAULT_PARTIAL = "all"

    def __init__(self, hosts=[], timeout=0, concurrency=0, 
            workdir=os.getcwd(), inventory=None, playbooks=None, sshkey=None):
        """ Prepare ansible context. """

        self._workdir = make_abs_path(workdir)

        inventory = inventory if inventory else self.INVENTORY
        playbooks = playbooks if playbooks else self.PLAYBOOKS

        # check inventory dir or file exists
        inventory = make_abs_path(inventory, self._workdir)
        if not os.path.exists(inventory):
            raise ExecutorPrepareError("{0}, bad inventory given".format(inventory))
        self._inventory_path = inventory

        # check playbooks dir and make sure init playbooks exists
        playbooks = make_abs_path(playbooks, self._workdir)
        if not os.path.isdir(playbooks):
            raise ExecutorPrepareError("{0}, bad playbooks directory given".format(playbooks))
        if not os.path.exists(os.path.join(playbooks, self.INIT_PB)):
            raise ExecutorPrepareError("{0} not exists, init playbooks \"{0}\" not found".format(self._INIT_PB))
        self._playbooks_path = playbooks

        # we don't need check sshkey here, assume the user have `~/.ssh` if no key given
        if sshkey != None and not os.path.isabs(sshkey):
            sshkey = make_abs_path(sshkey, self._workdir)
            if not os.path.isfile(sshkey):
                raise ExecutorPrepareError("{0}, bad sshkey file".format(sshkey))
        self._sshkey = sshkey

        LOG.info("init ansible executor with: "
                "workdir <{0}>, inventory <{1}>, playbooks <{2}>, sshkey <{3}>".format(
                    self._workdir, inventory, playbooks, self._sshkey))
        self._concurrency = concurrency if concurrency else self.FORK
        self._prepare()

        super(AnsibleExecutor, self).__init__(hosts, timeout)

    def _prepare(self):
        """ Prepare ansible internal data struts. """
        self._loader = DataLoader()
        self._varmanager = VariableManager()
        self._inventory = Inventory(loader=self._loader, variable_manager=self._varmanager, host_list=self._inventory_path)
        self._varmanager.set_inventory(self._inventory)  
        self._opts = AnsibleOpts(forks=self._concurrency, private_key_file=self._sshkey)

    def _reset_internal(self):
        """ Reset ansible internal data struts by invoke `_prepare` again. """
        self._prepare()

    def _is_raw(self, module):
        """ Ansible RAW module, see `_play_ds()` in `cli/adhoc.py` """
        return module in self.RAW_MODULE

    def _set_check_mode(self, check):
        """ Ansible check mode, see `load_options_vars()` in `utils/vars.py` . """
        self._varmanager.options_vars = dict(ansible_check_mode=check)

    def _run_tasks(self, play, reaper):
        """ Init TQM and run play. """
        tqm = TaskQueueManager(inventory=self._inventory,
            variable_manager=self._varmanager, 
            loader=self._loader,
            options=self._opts,
            passwords=None,
            stdout_callback=reaper)
        # with multiprocessing, the parent cannot handle exception riased
        #   by the child process.
        # which means, the try/except in the `runner._async_deploy` cannot
        #   known what happened here, and cause the entire celery worker
        #   process stop working without exit.
        # Solution:
        #   1, handle ansible exception here (inside executor).
        #   2, cannot raise other exception in `except` block, because of
        #       this piece of code may be run under other `fork()`.
        #   3, because of <2>, we use `reaper` to tell outside something going wrong.
        try:
            tqm.run(play)
        except AnsibleError:
            reaper.reaper_exception(ExecutorPrepareError(str(excinst())))
        finally:
            tqm.cleanup()
            reaper.done()

    def _run_pbs(self, playbooks, reaper):
        """ Init PBEX and run playbooks. """
        pbex = PlaybookExecutor(playbooks=playbooks,
            inventory=self._inventory,
            variable_manager=self._varmanager,
            loader=self._loader,
            options=self._opts,
            passwords=None)
        pbex._tqm._stdout_callback = reaper
        # Same raeson with `self._run_tasks`
        try:
            pbex.run()
        except AnsibleError:
            reaper.reaper_exception(ExecutorPrepareError(str(excinst())))
        reaper.done()

    def _execute_playbooks(self, playbooks, extra_vars=None, partial=None):
        """ Execute ansible playbooks. """
        if partial is None:
            partial = self.DEFAULT_PARTIAL
        if not isinstance(playbooks, (list, tuple)):
            playbooks = [playbooks]

        self._reset_internal()
        self._set_check_mode(False)

        self._opts.tags = partial
        self._varmanager.extra_vars = extra_vars
        collector = AnsibleReaper(self._hosts)

        LOG.info("execute playbook <{0}> with extra_vars <{1}> and partial <{2}> on <{3}>".format(
            playbooks, extra_vars, partial, self._hosts))
        worker = multiprocessing.Process(target=self._run_pbs, args=(playbooks, collector))
        worker.start()

        return collector.reaper()

    def target(self, pattern):
        """ Match target by given pattern. """
        return [ h.get_name() for h in self._inventory.get_hosts(pattern) ]

    def execute(self, module, check_mode=False, **module_args):
        """ Invoke ansible module with given args on remote host(s). """
        # Handle raw module args
        args = module_args.pop(self.RAW_ARG, None) 
        if args is None:
            args = ""
        # Handle module args
        for opt, val in module_args.items():
            args = "{0}={1} {2}".format(opt, val, args)

        self._reset_internal()
        self._set_check_mode(check_mode)

        args = parse_kv(args.strip(), self._is_raw(module))
        name = "execute {0} on {1}".format(module, self._hosts)
        collector = AnsibleReaper(self._hosts)

        play_ds = dict(name=name, hosts=self._hosts, gather_facts="no",
                tasks=[dict(name=name, action=dict(module=module, args=args))])
        play = Play.load(play_ds, variable_manager=self._varmanager, loader=self._loader)

        LOG.info("execute ansible module <{0}> with args <{1}> on <{2}>".format(module, args, self._hosts))
        worker = multiprocessing.Process(name="exec", target=self._run_tasks, args=(play, collector))
        worker.start()

        return collector.reaper()

    def raw_execute(self, cmd):
        """ Invoke ansible command module on remote host(s). """
        raw = {self.RAW_ARG: cmd}
        _handler = lambda host, result: {
            host: dict(
                status=result.get(EXE_STATUS_ATTR),
                stdout=result.get(EXE_RETURN_ATTR).pop('stdout', ""),
                stderr=result.get(EXE_RETURN_ATTR).pop('stderr', ""), 
                rtc=result.get(EXE_RETURN_ATTR).pop('rc', -1))}

        for _out in self.execute(self.CMD_MODULE, **raw):
            yield _handler(*_out.popitem())

    def ping(self):
        """ Ping remote host(s). """
        _handler = lambda host, result: {
                host: {
                    EXE_STATUS_ATTR: result.get(EXE_STATUS_ATTR)}}
        for _out in self.execute(self.PING_MODULE):
            yield _handler(*_out.popitem())

    def facter(self):
        """ Gather information of remote host(s). """
        _handler = lambda host, result: {
            host: {
                EXE_STATUS_ATTR: result.get(EXE_STATUS_ATTR), 
                'facter': dict(
                    [ (attr, val) for attr, val in result.pop(EXE_RETURN_ATTR).iteritems()
                        if attr not in (
                            '_ansible_parsed', 'changed', '_ansible_no_log', 'cmd', 
                            'failed', 'unreachable', 'rc', 'invocation', 'msg') ])}}
        for _out in self.execute(self.FACTER_MODULE):
            yield _handler(*_out.popitem())

    def service(self, name, start=True, restart=False, graceful=True):
        """ Manipulate service on remote host(s). """
        if restart:
            state = "reloaded" if graceful else "restarted"
        else:
            state = "started" if start else "stopped"

        _handler = lambda host, result: {
                host: {
                    EXE_STATUS_ATTR: result.pop(EXE_STATUS_ATTR)}}
        for _out in self.execute(self.SERVICE_MODULE, name=name, state=state):
            yield _handler(*_out.popitem())

    def deploy(self, roles, extra_vars=None, partial=None):
        """ Deploy service/role/app on remote host(s). """
        if extra_vars:
            if not isinstance(extra_vars, dict):
                raise ExecutorDeployError("Bad extra_vars for deploy")
        else:
            extra_vars = dict()

        extra_vars[self.ROLE_VAR] = roles
        extra_vars[self.TARGET_VAR] = self._hosts

        playbook = os.path.join(self._playbooks_path, self.INIT_PB)
        return self._execute_playbooks(playbook, extra_vars, partial)
