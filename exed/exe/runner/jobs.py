# -*- coding: utf-8 -*-

import time
import uuid
import json
import copy
import logging

from redis import WatchError

from .context import Context

from exe.exc import JobConflictError, JobNotExistsError
from exe.executor.utils import *
from exe.executor.consts import *

LOG = logging.getLogger(__name__)


class JobQuerier(Context):
    """ Query information about Job(s) from redis. """

    __RUNNER_NAME__ = "job"
    __RUNNER_MUTEX_REQUIRE__ = False

    def handle(ctx, jid=None, outputs=False, follow=False, delete=False):
        redis = ctx.redis
        if not jid:
            return [ j.split(':')[1] for j in redis.keys(Job._key('*')) ]

        job = Job.load_task(jid, redis)
        if not job:
            raise JobNotExistsError("no such jid {0}".format(jid))
        if delete:
            return job.reaper(redis)
        if outputs:
            job.load_data(redis)

        if not follow:
            return job.ctx
        else:
            return job.follow(redis)


class Job(object):
    """ Manipulate job/task and update their context in redis. """

    STATE_DONE = 0
    STATE_RUNNING = 1
    STATE_FAILURE = 2

    DONE = "__DONE__"
    FAILURE = "__FAILURE__"

    def __init__(self, targets, operate, mutex=True, state=None, taskid=None, error=""):
        """ Create job context instance. """
        self._id = taskid
        self._op = operate
        self._state = state
        self._targets = targets

        self._rdata = {}     # for store return data of job
        self._error = error  # for store error message of job

        if not mutex:
            self._op = self._op + ':' + self._random_tag

    @property
    def _random_tag(self):
        return uuid.uuid4().hex

    @classmethod
    def load(cls, dict_ctx):
        """ Create job context instance with dumped job context. """
        return cls(**dict_ctx)

    @classmethod
    def load_task(cls, taskid, redis):
        """ Create job context instance by load from redis. """
        t = redis.hgetall(cls._key(taskid))
        if not t:
            return t
        return cls(**dict(taskid = taskid,
            targets = json.loads(t.pop('targets')),
            operate = t.pop('operate'),
            state = int(t.pop('state')),
            error = t.pop('error')))

    @property
    def dict_ctx(self):
        """ Dump job context to dict object for later recreate. """
        return dict(mutex=True,
                state=self._state,
                taskid=self._id,
                targets=self._targets,
                operate=self._op,
                error=self._error)

    @property
    def ctx(self):
        """ Dump job context for query request. """
        ctx = copy.deepcopy(self.dict_ctx)
        ctx.pop('taskid', None)
        ctx.pop('mutex', None)
        ctx['operate'] = ctx['operate'].split(':')[0]
        ctx.update({EXE_RETURN_ATTR: self._rdata})
        return ctx

    @staticmethod
    def _key(taskid):
        """ Format redis key with given taskid. """
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
        """ Format redis key for meta data. """
        return "{0}:{1}:meta".format(fqdn, self._op)

    def _data_key(self, fqdn):
        """ Format redis key for return data. """
        return "{0}:{1}:data".format(fqdn, self._op)

    def load_data(self, redis):
        """ Load all return data of job from redis . """
        for key in self.data_keys:
            target = key.split(':')[0]
            rdata = redis.lrange(key, 0, -1)

            self._rdata.update({target: [ json.loads(retval) for retval in rdata ]})

    def create(self, redis):
        """ 
        Create job by create job context in redis, each job will create len(hosts) meta keys, 
            conflict dectection is done by redis key exists check of job meta keys. 

        If no conflict, job context (the `meta_keys`) will created with redis pipeline 
            to avoid operate confilct.
        """
        pipeline = redis.pipeline()
        try:
            pipeline.watch(self.meta_keys)
            for key in self.meta_keys:
                if pipeline.exists(key):
                    raise JobConflictError("operate conflict, job already exists on some host(s)")

            LOG.debug("going to create job meta data <{0}>".format(';'.join(self.meta_keys)))
            start = time.time()
            pipeline.multi()
            for key in self.meta_keys:
                pipeline.hmset(key, dict(state=Job.STATE_RUNNING, start=start))
            pipeline.execute()
            LOG.debug("job meta data create finished, <{0}>".format(';'.join(self.meta_keys)))

        except WatchError:
            LOG.debug("conflict detected on job meta data create <{0}>".format(';'.join(self.meta_keys)))
            raise JobConflictError("operate conflict, try again later")
        finally:
            pipeline.reset()

    def associate_task(self, task, redis):
        """ 
        Associate job context with celery AsyncResult (which returned by task.delay() 
            of celcey) object by create job key with targets and operate in redis. 

        When job was queried, this key will return, and using the targets/operate, we can
            find all job context by find their meta/data keys.
        """
        redis.hmset(self._key(task.id), dict(
            state=Job.STATE_RUNNING, targets=json.dumps(self._targets),
            operate=self._op, error=""))
        return task.id

    def bind(self, taskid):
        """ Bind job context with celery task by taskid. """
        self._id = taskid

    def update(self, target, retval, redis):
        """ Update job context with target and retval. """
        content = json.dumps(retval)
        redis.publish("{0}:{1}".format(target, self._op), content)
        redis.rpush(self._data_key(target), content)

        if not isExeSuccess(retval):
            redis.hset(self._meta_key(target), 'state', Job.STATE_FAILURE)

    def update_done(self, target, redis):
        """ Update job context mark operate on target was done. """
        redis.hset(self._meta_key(target), 'state', Job.STATE_DONE)

    def done(self, redis, failed=False, error=""):
        """ Mark job as done or failed if failure is `True`. """
        if failed:
            redis.publish("{0}:control".format(self._op), Job.FAILURE)
            state = Job.STATE_FAILURE
        else:
            redis.publish("{0}:control".format(self._op), Job.DONE)
            state = Job.STATE_DONE
        pipeline = redis.pipeline(False)
        if error:
            pipeline.hset(self._key(self._id), 'error', error)
        pipeline.hset(self._key(self._id), 'state', state)
        pipeline.execute()

    def reaper(self, redis):
        """ Reaper job and corresponding context (meta/data keys). """
        pipeline = redis.pipeline(False)
        pipeline.delete(*self.meta_keys)
        pipeline.delete(*self.data_keys)
        pipeline.delete(self._key(self._id))
        pipeline.execute()
        return ""   # Delete API return 204 no content

    def follow(self, redis):
        """ Return job context in follow mode. """
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
