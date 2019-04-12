# (c) 2016, Hao Feng <whisperaven@gmail.com>

import time
import uuid
import json
import copy
import logging

from redis import WatchError

from .context import Context

from exe.exc import JobConflictError, JobNotExistsError, JobDeleteError
from exe.executor.utils import *
from exe.executor.consts import *

LOG = logging.getLogger(__name__)


class JobQuerier(Context):
    """ Query information about Job(s) from redis. """

    __RUNNER_NAME__ = "job"
    __RUNNER_MUTEX_REQUIRE__ = False

    def handle(ctx, jid=None, outputs=False,
               follow=False, detail=False, delete=False):
        """ Handle job query request. """
        redis = ctx.redis

        # Job List
        if not jid:
            jids = [ j.split(':')[1] for j in redis.keys(Job._key('*')) ]
            if not detail:   # list for ids without details
                return jids 
            jobs = []
            for jid in jids: # list for detail of each job
                job = Job.load_task(jid, redis)
                if not job:
                    LOG.warning("bad job <{0}> in redis, "
                                "missing context".format(jid))
                    continue
                jobs.append(job.ctx)
            return jobs

        # Job Query/Delete by JID
        job = Job.load_task(jid, redis)
        if not job:
            raise JobNotExistsError("no such jid <{0}>".format(jid))

        if delete:
            if job._state == Job.STATE_RUNNING:
                raise JobDeleteError("cannot delete a running job, "
                                     "jid <{0}>".format(jid))
            job.sweep(redis)
            return ""   # Delete API return 204 no content

        if outputs:
            job.load_data(redis)

        if not follow:
            return job.ctx
        else:
            return job.follow(redis)


class Job(object):
    """ Manipulate job/task and update their context in redis.

    These context contains,

        1. target
            the remote host(s)
        2. operate
            the operation name, which should be the runner's name
        3. mutex
            the mutex attr of this job which should be the runner's mutex attr
        4. operate_args
            the args of this job's operation, particular for deploy jobs
        5. startat
            the timestamp that this job created
        6. utag
            an random uuid of this job
        7. state
            current state of this job
        8. taskid
            the celery task id of this job
        9. error
            error message of this job

    For more detail about their represents in redis, see doc of ``Job.create``.
    """

    STATE_DONE = 0
    STATE_RUNNING = 1
    STATE_FAILURE = 2

    DONE    = "__DONE__"
    FAILURE = "__FAILURE__"

    def __init__(self, targets, operate, mutex=True, 
            operate_args={}, startat=0, utag=None,
            state=None, taskid=None, error=""):
        """ Initialize Job instance. """
        self._id = taskid

        self._op      = operate
        self._opargs  = operate_args
        self._state   = state
        self._targets = targets
        self._startat = startat

        self._utag  = utag   # for avoid data keys conflict
        self._rdata = {}     # for store return data of job
        self._error = error  # for store error message of job

        if not mutex:
            self._op = ':'.join([self._op, self._random_tag])
        if not self._startat:
            self._startat = int(time.time())
        if not self._utag:
            self._utag = self._random_tag

    @property
    def _random_tag(self):
        """ Generate an UUID for this job. """
        return uuid.uuid4().hex

    @classmethod
    def load(cls, dict_ctx):
        """ Create job context instance with dumped job context. """
        return cls(**dict_ctx)

    @classmethod
    def load_task(cls, taskid, redis):
        """ Create job context instance by load job context from redis. """
        t = redis.hgetall(cls._key(taskid))
        if not t:
            return t

        return cls(**dict(targets      = json.loads(t.pop('targets')),
                          operate      = t.pop('operate'),
                          operate_args = json.loads(t.pop('operate_args')),
                          startat      = int(t.pop('startat')),
                          utag         = t.pop('utag'),
                          state        = int(t.pop('state')),
                          taskid       = taskid,
                          error        = t.pop('error')))

    @property
    def dict_ctx(self):
        """ Dump job context to dict object for later recreate. """
        return dict(targets      = self._targets,
                    operate      = self._op,
                    mutex        = True,
                    operate_args = self._opargs,
                    startat      = self._startat,
                    utag         = self._utag,
                    state        = self._state,
                    taskid       = self._id,
                    error        = self._error)

    @property
    def ctx(self):
        """ Dump job context for query request. """
        ctx = copy.deepcopy(self.dict_ctx)
        ctx.pop('mutex', None)
        ctx.pop('utag', None)
        ctx['operate'] = self.operate
        ctx.update({EXE_RETURN_ATTR: self._rdata})
        return ctx

    @property
    def operate(self):
        """ Parse/Format the operation name `self._op` of this job. """
        return self._op.split(':')[0]

    @staticmethod
    def _key(taskid):
        """ Format redis key with given taskid.

        Full key name example:
            job:$taskid (taskid is an uuid represents a celery task id)
        """
        return "job:{0}".format(taskid)

    @property
    def meta_keys(self):
        """ Format redis keys for all meta data. """
        return [ self._meta_key(_fqdn) for _fqdn in self._targets ]

    @property
    def data_keys(self):
        """ Format redis keys for all return data. """
        return [ self._data_key(_fqdn) for _fqdn in self._targets ]

    def _meta_key(self, fqdn):
        """ Format redis key for single meta data.

        Full key name examples (normal operation):
            molten-core.vm.0ops.io:ping:$uuid:meta
            molten-core.vm.0ops.io:service:$uuid:meta

        Full key name examples (mutex operation):
            karazhan.vm.0ops.io:deploy:meta
        """
        return "{0}:{1}:meta".format(fqdn, self._op)

    def _data_key(self, fqdn):
        """ Format redis key for single return data.

        Full key name examples (normal operation):
            molten-core.vm.0ops.io:ping:$uuid:data
            molten-core.vm.0ops.io:service:$uuid:data

        Full key name examples (mutex operation):
            karazhan.vm.0ops.io:deploy:data
        """
        return "{0}:{1}:{2}:data".format(fqdn, self._op, self._utag)

    def load_data(self, redis):
        """ Load all return data from redis. """
        for key in self.data_keys:
            target = key.split(':')[0]
            rdata  = redis.lrange(key, 0, -1)

            self._rdata.update(
                {target: [ json.loads(retval) for retval in rdata ]})

    def create(self, redis):
        """ Create job by create job context in redis.

        Each job will create at least ``len(hosts)`` meta keys, job conflict
        dectect is done by redis key exists check of all job meta keys.

        If no conflict, job context (the ``meta_keys``) will created via redis
        pipeline to avoid operate confilct with others.

        At this point, each of these meta keys value will be a redis hash:
            $fqdn:$op:meta -> { 'startat': self._startat } (mutex job)
            $fqdn:$op:$uuid:meta -> { 'startat': self._startat }

        Note that, no data keys was created, they will be create automatically
        via ``rpush()`` method inside ``Job.update`` when there is new runner
        data returns.

        After at last once update, each of these data keys value will be
        a redis list:
            $fqdn:$op:data -> [$return_data, $return_data, ...] (mutex job)
            $fqdn:$op:$uuid:data -> [$return_data, $return_data, ...]
        """
        pipeline = redis.pipeline()
        try:
            pipeline.watch(self.meta_keys)
            for key in self.meta_keys:
                if pipeline.exists(key):
                    raise JobConflictError("operate conflict, job already "
                                           "running on some host(s)")

            LOG.debug("going to create job meta data "
                      "keys <{0}>".format(';'.join(self.meta_keys)))

            pipeline.multi()
            for key in self.meta_keys:
                pipeline.hmset(key, dict(startat=self._startat))
            pipeline.execute()

            LOG.info("job meta data create finished, "
                     "keys <{0}>".format(';'.join(self.meta_keys)))

        except WatchError:
            LOG.info("conflict detected on job meta data "
                     "creation <{0}>".format(';'.join(self.meta_keys)))
            raise JobConflictError("operate conflict, try again later")
        finally:
            pipeline.reset()

    def associate_task(self, task, redis):
        """ Associate job context with celery AsyncResult.

        These AsyncResult (which returned by ``task.delay()`` of celcey)
        object, and create the job key with ``targets`` and ``operate``
        in redis.

        When job was queried, this job key will return, and using the
        targets/operate inside that key, we can always find all job context
        by finding their meta/data keys.

        At this point, each of these task key value is a redis hash:
            job:$taskid -> {
                state   -> Job.STATE_RUNNING (int: 1)
                targets -> json.dumps(["host-1", "host-2", ...])
                operate -> $op:$uuid
                operate_args -> json.dumps({ ..extra args.. })
                utag    -> $uuid
                startat -> $timestamp
                error   -> "" (empty string)
            }

        And update each of meta keys from:
            $fqdn:$op:meta -> { 'startat': self._startat } (mutex job)
            $fqdn:$op:$uuid:meta -> { 'startat': self._startat }

        to:
            $fqdn:$op:meta -> { (mutex job)
                'startat'   -> self._startat
                'associate' -> $taskid
            }
            $fqdn:$op:$uuid:meta -> {
                'startat': self._startat
                'associate' -> $taskid
            }
        """
        pipeline = redis.pipeline(False)
        pipeline.hmset(
            self._key(task.id),
            dict(
                state        = Job.STATE_RUNNING,
                targets      = json.dumps(self._targets),
                operate      = self._op,
                operate_args = json.dumps(self._opargs),
                utag         = self._utag,
                startat      = self._startat,
                error        = ""))

        for key in self.meta_keys:
            pipeline.hset(key, 'associate', task.id)
        pipeline.execute()

        return task.id

    def bind(self, taskid):
        """ Bind job context with celery task by taskid. """
        self._id = taskid

    def push_return_data(self, target, data, redis):
        """ Push return data into job data key with target and retval.

        Each of these data key will be create right after the first
        ``redis.rpush()`` call inside this method.

        This method also publish these data into a redis pubsub system
        for support job query in follow mode.
        """
        content = json.dumps(data)
        redis.publish("{0}:{1}".format(target, self._op), content)
        redis.rpush(self._data_key(target), content)

    def target_done(self, target, failed, redis):
        """ Logging and update Job Context when operate on target was done. """
        if failed:
            state = "failed"
            if not self._error:
                self._error = "some operations failed on {0}".format(target)
        else:
            state = "successed"
        LOG.info("{0} operation on {1} of {2} was "
                 "{3}".format(self.operate, target, self._id, state))

    def done(self, failed, errmsg, redis):
        """ Mark job as done or failed. """
        if failed:
            redis.publish("{0}:control".format(self._op), Job.FAILURE)
            state = Job.STATE_FAILURE
        else:
            redis.publish("{0}:control".format(self._op), Job.DONE)
            state = Job.STATE_DONE

        if not errmsg:
            errmsg = self._error

        pipeline = redis.pipeline(False)
        pipeline.hset(self._key(self._id), 'error', errmsg)
        pipeline.hset(self._key(self._id), 'state', state)
        pipeline.delete(*self.meta_keys)
        pipeline.execute()

    def sweep(self, redis):
        """ Delete job and corresponding context (meta/data keys) from redis. """
        pipeline = redis.pipeline(False)
        pipeline.delete(*self.data_keys)
        pipeline.delete(self._key(self._id))
        pipeline.execute()

    def follow(self, redis):
        """ Yield job context for follow mode. """
        cc = "{0}:control".format(self._op)
        rc = [ "{0}:{1}".format(target, self._op) for target in self._targets ]
        ps = redis.pubsub(ignore_subscribe_messages=True)

        ps.subscribe(cc, *rc)
        yield self.ctx
        if self.ctx['state'] != Job.STATE_RUNNING:
            return

        for msg in ps.listen():
            data = msg['data']
            source = msg['channel']

            if source == cc:
                break
            source = source.split(':')[0]   ## remove the operate 
            yield {source: json.loads(data)}
