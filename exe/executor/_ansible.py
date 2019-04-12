# (c) 2016, Hao Feng <whisperaven@gmail.com>

import os
import sys
import copy
import json
import time
import logging
import os.path
import multiprocessing

from ansible.cli import CLI
from ansible.cli.adhoc import AdHocCLI
from ansible.cli.playbook import PlaybookCLI
from ansible.playbook import Playbook
from ansible.playbook.play import Play
from ansible.playbook.task import Task
from ansible.plugins.callback import CallbackBase
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.executor.task_result import TaskResult
from ansible.executor.stats import AggregateStats
from ansible.errors import AnsibleError

from billiard import current_process as billiard_current_process

from .consts import *
from .prototype import ExecutorPrototype

from exe.utils.err import excinst
from exe.utils.path import make_abs_path
from exe.exc import ExecutorPrepareError, ExecutorDeployError, ExecutorNoMatchError


LOG = logging.getLogger(__name__)


## ansible reaper ##
class AnsibleReaper(CallbackBase):
    """ Ansible reaper for result collect, act as Ansible Callback. """

    # Ansible Callback Plugin API
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stdout'
    CALLBACK_NAME = 'exe_reaper'

    def __init__(self, hosts=None, skip_announce=True):
        self._reaper_targets = hosts
        self._reaper_announce = not skip_announce

        # initialized by first reaper event
        self._reaper_name = None
        self._reaper_hosts = None
        self._reaper_tasks_ctx = None
        self._reaper_start_timestamp = 0

        self._reaper_initialized = False

        # ansible run jobs after `fork()` workers,
        #   multiprocessing will make those control vars synced
        self._reaper_queue = multiprocessing.Queue()
        self._reaper_done_ev = multiprocessing.Event()

    # Executor Internal Reaper API #
    def reaper_await(self):
        """ Await Exit event.

        Sometime the child process may exit before ansible callback
        ``v2_playbook_on_stats`` returns, we use this method to block
        child process until the parent reaper instance reap everything.
        """
        self._reaper_done_ev.wait()

    def reaper_exception(self, exc):
        """ Reaper Exception raised by child process. """
        self._reaper_queue.put(exc)

    def reaper_returns(self, pid):
        """ Yield ansible outputs to the outside through the reaper instance. """
        LOG.debug("starting reaper for pid {0}".format(pid))

        try:
            while True:
                LOG.debug("reaper block, waiting message from "
                          "pid {0}".format(pid))
                _event = self._reaper_queue.get()

                LOG.debug("reaper got event <{0}> from "
                          "pid {1}".format(_event, pid))
                # riase the internal exception which wrapped
                #   by the `try/except` block inside both
                #   `self.execute` and `self.deploy`.
                if isinstance(_event, Exception):
                    raise _event

                # the first event after start, the ``_event`` shuld be an
                #   instance of ``ansible.playbook.Play``, after that the
                #   reaper was fully initialized
                if not self._reaper_initialized:
                    if not isinstance(_event, Play):
                        raise ExecutorPrepareError(
                            "cannot initialize ansible reaper instance "
                            "after fork()")
                    self._set_reaper_ctx(_event)

                    LOG.debug(
                        "callback method <v2_playbook_on_play_start> runs, "
                        "set reaper context with empty tasks list, "
                        "name: <{0}>, hosts: <{1}>, start: <{2}> ".format(
                            self._reaper_name, self._reaper_hosts,
                            self._reaper_start_timestamp))

                    if self._reaper_announce:
                        yield self._new_reaper_event(self._reaper_name)
                    continue

                # the task start event
                if isinstance(_event, Task):
                    self._append_reaper_task_ctx(_event)

                    LOG.debug("callback method <v2_playbook_on_task_start> or "
                        "<v2_playbook_on_handler_task_start> runs, append task"
                        " context to reaper: <{0}>".format(
                            self._reaper_tasks_ctx[-1]))
                    if self._reaper_announce:
                        yield self._new_reaper_event(
                            self._reaper_tasks_ctx[-1]['name'])
                    continue

                # the wrapped runner return event
                if isinstance(_event, tuple):
                    _type    = _event[0]
                    _payload = _event[1]

                    self._reaper_tasks_ctx[-1][_type].append(_payload)

                    LOG.debug("callback method <v2_runner_on_*> or "
                              "<v2_runner_item_on_*> runs, append task context"
                              " to reaper: <{0}>".format(
                                  self._reaper_tasks_ctx[-1]))
                    yield copy.deepcopy(_payload); continue

                # the statistics of this play run after all, after that
                #   the reaper should exit
                if isinstance(_event, AggregateStats):
                    _summary_dict = {}
                    for target in self._reaper_targets:
                        _summary_dict[target] = _event.summarize(target)

                    # operate finished, make sure everything was runned
                    #   on all remote host(s)
                    for task_context in self._reaper_tasks_ctx:
                        if len(self._reaper_targets) != len(task_context['hosts']):
                            _hosts = [ tuple(t.keys())[0]
                                for t in task_context['hosts'] ]
                            _missing = [ t for t in self._reaper_targets
                                if t not in _hosts ]

                            raise ExecutorNoMatchError(
                                "target not found: <{0}>".format(
                                    ",".join(_missing)))

                    LOG.debug("callback method <v2_playbook_on_stats> runs, "
                              "going to return from reaper, stats summary: "
                              "<{0}>".format(_summary_dict))
                    break

        finally:
            LOG.debug("reaper cleanup pid {0}".format(pid))
            self._reaper_queue.close()
            self._reaper_done_ev.set()
            os.waitpid(pid, 0)

    def _set_reaper_ctx(self, play):
        """ Handle new play start. """
        self._reaper_name  = play.get_name()            # play name
        self._reaper_hosts = play.hosts                 # play hosts
        self._reaper_start_timestamp = int(time.time()) # play start timestamp

        self._reaper_tasks_ctx = [] # play tasks
        self._reaper_initialized = True

    def _append_reaper_task_ctx(self, task):
        """ Handle new task start. """
        self._reaper_tasks_ctx.append(dict(
            name    = task.get_name(),   # task name
            path    = task.get_path(),   # task line number in playbooks
            tags    = task.tags,         # task tags
            items   = [],                # task items
            hosts   = [],                # task host states
            start   = int(time.time()))) # task start timestamp

    def _new_reaper_event(self, name, status=EXE_ANNOUNCE,
                          result=None, summary=None):
        """ Wrap the ansible result inside reaper event. """
        _host   = EXE_ANNOUNCE_ATTR
        _result = {}

        if result:
            _host   = result._host.get_name()
            _result = result._result.copy()
        elif summary:
            _host   = EXE_ANNOUNCE_SUMMARY_ATTR
            _result = summary

        return {
            _host: {
                EXE_NAME_ATTR: name,
                EXE_STATUS_ATTR: status,
                EXE_RETURN_ATTR: _result,
            }
        }

    def _update_reaper_task_state(self, status, result):
        """ Handle new task return of each host. """
        self._reaper_queue.put(
            ('hosts', self._new_reaper_event(
                result.task_name, status, result)))

    def _update_reaper_item_state(self, status, result):
        """ Handle new item return of each task of each host. """
        self._reaper_queue.put(
            ('items', self._new_reaper_event(
                result.task_name, status, result)))

    # Ansible Callback Plugin API Implementations #
    def v2_playbook_on_start(self, playbook):
        """ The very first one of all callback methods. """
        pass

    def v2_playbook_on_stats(self, stats):
        """ The last one of all callback methods, indicates everything was done. """
        self._reaper_queue.put(stats)

    def v2_playbook_on_play_start(self, play):
        """ CLI output: <PLAY [...] *************> (the first one). """
        self._reaper_queue.put(play)

    def v2_playbook_on_task_start(self, task, is_conditional):
        """ CLI output: <TASK [Gathering Facts] *************> (at each task starts). """
        self._reaper_queue.put(task)

    def v2_playbook_on_handler_task_start(self, task):
        """ CLI output: <RUNNING HANDLER [...] *************> (at each handler task starts). """
        self._reaper_queue.put(task)

    def v2_runner_on_ok(self, result):
        """ CLI output: <ok: [...]> (at each task of each host return). """
        self._update_reaper_task_state(EXE_OK, result)

    def v2_runner_on_skipped(self, result):
        """ CLI output: <skipping: [...]> (at each task of each host return). """
        self._update_reaper_task_state(EXE_SKIPED, result)

    def v2_runner_on_failed(self, result, ignore_errors=False):
        """ CLI output: <failed: [...]> (at each task of each host return). """
        self._update_reaper_task_state(EXE_FAILED, result)

    def v2_runner_on_unreachable(self, result):
        """ CLI output: <unreachable: [...]> (at each task of each host return). """
        self._update_reaper_task_state(EXE_UNREACHABLE, result)

    def v2_runner_item_on_ok(self, result):
        """ CLI output: <ok: [...] => (item=...)> (at each item of each task of each host return). """
        self._update_reaper_item_state(EXE_OK, result)

    def v2_runner_item_on_skipped(self, result):
        """ CLI output: <skipped: [...] => (item=...)> (at each item of each task of each host return). """
        self._update_reaper_item_state(EXE_SKIPED, result)

    def v2_runner_item_on_failed(self, result):
        """ CLI output: <failed: [...] => (item=...)> (at each item of each task of each host return). """
        self._update_reaper_item_state(EXE_FAILED, result)

## ansible executor ##
class AnsibleExecutor(ExecutorPrototype):
    """ Executor implemented on top of ansible's CLI classes.

    For module execute
        AdHocCLI
    For playbook execute
        PlaybookCLI, PlaybookExecutor
    """

    __EXECUTOR_NAME__ = "ansible"

    FORK = 10
    RAW_ARG = "_RAW"
    PLAYBOOKS = "playbooks"

    CMD_MODULE = "shell"
    PING_MODULE = "ping"
    FACTER_MODULE = "setup"
    SERVICE_MODULE = "service"

    INIT_PB = "_deploy.yml"
    ROLE_VAR = "_role"
    TARGET_VAR = "_targets"

    def __init__(self, hosts=[], timeout=0, concurrency=0,
                 workdir=os.getcwd(), playbooks=None):
        """ Initialize AnsibleExecutor instance. """
        self._workdir = make_abs_path(workdir)

        self._playbooks_path = make_abs_path(
            playbooks if playbooks else self.PLAYBOOKS, self._workdir)
        if not os.path.isdir(self._playbooks_path):
            raise ExecutorPrepareError(
                "{0}, bad playbooks directory given".format(
                    self._playbooks_path))
        if not os.path.exists(os.path.join(
            self._playbooks_path, self.INIT_PB)):
            raise ExecutorPrepareError(
                "{0} does not exists, no init playbook founded".format(
                    os.path.join(self._playbooks_path, self.INIT_PB)))

        LOG.info(
            "init ansible executor with: workdir <{0}>, "
            "playbooks path <{1}>, concurrency <{2}>".format(
                self._workdir, self._playbooks_path, concurrency))
        super(AnsibleExecutor, self).__init__(hosts, timeout, concurrency)

    def _disable_daemonic(self):
        """ Disable the ``daemonic`` flag of the current process.

        When a process exits, it attempts to terminate all of its daemonic
        child processes. And a daemonic process is not allowed to create child
        processes. more detail can be found here:

        https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Process.daemon

        The celery worker are also some kind of python daemonic process, and
        ansible use ``multiprocessing`` to create their own workers. finally,
        a celery worker (which is a deamonic process) trying to create their
        own child processes, which not allowed by the ``assert`` inside the
        ``multiprocessing.Process`` class, which means ansible can not finish
        their jobs.

        References link above, the ``deamonic`` flag value is inherited from the
        creating process. After ``os.fork()``, that flag got inherited. We
        disable it by set its value to ``False``, looks dirty, but its works.
        """
        billiard_current_process()._config['daemon'] = False

    def extract_return_error(self, return_context):
        """ Extra error context from return context. """
        if 'msg' in return_context:
            return return_context['msg']
        return ""

    def target(self, pattern):
        """ Invoke ansible to Match target inside inventory by given pattern. """
        _ansible_cli = AdHocCLI(["--list-hosts", pattern])
        _ansible_cli.parse()

        LOG.debug("simulation ansible adhoc cli with "
                  "<--list-hosts {0}>".format(pattern))
        _, inventory, _ = _ansible_cli._play_prereqs(_ansible_cli.options)

        return [ h.get_name() for h in inventory.list_hosts(pattern) ]

    def deploy(self, roles, extra_vars=None, partial=None):
        """ Invoke ansible-playbook to deploy services/roles on remote host(s). """
        _playbook = os.path.join(self._playbooks_path, self.INIT_PB)

        # Playbook CLI args
        args = ["ansible-playbook"]
        # Handle init pb
        args.append(_playbook)
        # Handle playbook tags
        if partial:
            if not isinstance(partial, (list, tuple)):
                partial = [partial]
            args.append("--tags")
            args.append(",".join(partial))
        # Handle playbook forks
        if self._concurrency:
            args.append("--forks")
            args.append(str(self._concurrency))
        # Handle playbook extra_vars
        if extra_vars:
            if not isinstance(extra_vars, dict):
                raise ExecutorDeployError("bad extra_vars for deploy")
        else:
            extra_vars = {}
        extra_vars[self.ROLE_VAR] = roles
        extra_vars[self.TARGET_VAR] = self._hosts

        args.append("--extra-vars")
        args.append(json.dumps(extra_vars))

        LOG.debug("simulation ansible playbook cli with <{0}>".format(args))

        # Prepare ansible options
        _cli = PlaybookCLI(args)
        _cli.parse()
        _cli.normalize_become_options()

        # Prepare ansible internal datastructs
        _loader, _inventory, _variable_manager = _cli._play_prereqs(_cli.options)
        _options = _cli.options

        # Run it via fork() & PlaybookExecutor, and using AnsibleReaper as callback
        reaper = AnsibleReaper(self._hosts, skip_announce=False)
        pid = os.fork()
        if pid:
            LOG.debug("ansible executor fork() for deploy, child pid is <{0}>".format(pid))
            return reaper.reaper_returns(pid)
        self._disable_daemonic()

        pbex = PlaybookExecutor(
            playbooks        = [_playbook],
            inventory        = _inventory,
            variable_manager = _variable_manager,
            loader           = _loader,
            options          = _options,
            passwords        = {'conn_pass': None, 'become_pass': None}) # TODO: support become password
        # FIXME: bad way to set callback, but we have no choices
        pbex._tqm._stdout_callback  = reaper
        pbex._tqm._callbacks_loaded = True  # don't load any callback plugins, just use reaper

        LOG.info(
            "deploy <{0}>, execute playbook <{1}> with extra_vars <{2}> "
            "and partial <{3}> on <{4}>".format(
                roles, _playbook, extra_vars, partial, self._hosts))

        try:
            pbex_result = pbex.run()
            LOG.debug("ansible PlaybookExecutor result: "
                      "<{0}>".format(pbex_result))
        except AnsibleError:
            reaper.reaper_exception(ExecutorPrepareError(str(excinst())))
        finally:
            # prevent the child process exit before the ansible
            #   callback ``v2_playbook_on_stats`` returns, which may
            #   cause the parent reaper instance hang forever
            reaper.reaper_await()

        LOG.debug("ansible executor deploy child process "
                  "(pid: <{0}>) done, exit".format(os.getpid()))
        os._exit(os.EX_OK)

    def execute(self, module, skip_announce=True, **module_args):
        """ Invoke ansible module with given args on remote host(s). """
        # AdHoc CLI args
        args = ["ansible"]
        # Handle module name
        args.append("--module-name")
        args.append(module)
        # Handle module args/raw args
        if module_args:
            _module_args = module_args.pop(self.RAW_ARG, "")
            if not _module_args:
                for opt, val in module_args.items():
                    _module_args = "{0}={1} {2}".format(opt, val, _module_args)
                args += ["--args", _module_args.strip()] if _module_args.strip() else []
            else:
                args += ["--args", _module_args.strip()]
        # Handle adHoc forks
        if self._concurrency:
            args.append("--forks")
            args.append(str(self._concurrency))

        # Host pattern
        args.append(','.join(self._hosts))

        LOG.debug("simulation ansible adhoc cli with <{0}>".format(args))

        # Prepare AnsibleReaper as callback
        reaper = AnsibleReaper(self._hosts, skip_announce)

        # Prepare ansible options, make sure never ask pass
        _cli = AdHocCLI(args, reaper)
        _cli.parse()
        _cli.options.ask_pass = False

        # Run it via fork()
        pid = os.fork()
        if pid:
            LOG.debug("ansible executor fork() for execute, "
                      "child pid is <{0}>".format(pid))
            return reaper.reaper_returns(pid)
        self._disable_daemonic()

        LOG.info("execute ansible module <{0}> with args <{1}> on "
                 "<{2}>".format(module, module_args, self._hosts))

        try:
            ad_hoc_result = _cli.run()
            LOG.debug("ansible AdHoc result: <{0}>".format(ad_hoc_result))
        except AnsibleError:
            reaper.reaper_exception(ExecutorPrepareError(str(excinst())))
        finally:
            reaper.reaper_await()

        LOG.debug("ansible executor execute child process "
                  "(pid: <{0}>) done, exit".format(os.getpid()))
        os._exit(os.EX_OK)

    def raw_execute(self, cmd):
        """ Invoke ansible command module on remote host(s). """
        _raw = { self.RAW_ARG: cmd }
        _handler = lambda host, result: {
            host: {
                EXE_STATUS_ATTR: result.get(EXE_STATUS_ATTR),
                'stdout': result.get(EXE_RETURN_ATTR).pop('stdout', ""),
                'stderr': result.get(EXE_RETURN_ATTR).pop('stderr', ""),
                'rtc'   : result.get(EXE_RETURN_ATTR).pop('rc', -1)}}

        for _out in self.execute(self.CMD_MODULE, **_raw):
            yield _handler(*_out.popitem())

    def ping(self):
        """ Invoke ansible ping module on remote host(s). """
        _handler = lambda host, result: {
            host: {
                EXE_STATUS_ATTR: result.get(EXE_STATUS_ATTR)}}

        for _out in self.execute(self.PING_MODULE):
            yield _handler(*_out.popitem())

    def facter(self):
        """ Invoke ansible facter module on remote host(s). """
        _handler = lambda host, result: {
            host: {
                EXE_STATUS_ATTR: result.get(EXE_STATUS_ATTR), 
                'facts': dict(
                    [ (attr, val)
                        for attr, val in
                            result.pop(EXE_RETURN_ATTR).pop('ansible_facts').items() ]
                )
            }
        }

        for _out in self.execute(self.FACTER_MODULE):
            yield _handler(*_out.popitem())

    def service(self, name, start=True, restart=False, graceful=True):
        """ Invoke ansible service module on remote host(s). """
        if restart:
            state = "reloaded" if graceful else "restarted"
        else:
            state = "started" if start else "stopped"
        enabled = "yes" if restart or start else "no"

        _handler = lambda host, result: {
            host: {
                EXE_STATUS_ATTR: result.pop(EXE_STATUS_ATTR)}}

        for _out in self.execute(self.SERVICE_MODULE,
                                 name=name, state=state, enabled=enabled):
            yield _handler(*_out.popitem())
