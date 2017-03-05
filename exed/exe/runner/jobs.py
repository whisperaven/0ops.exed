# -*- coding: utf-8 -*-

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

    def handle(ctx, jid=None, outputs=False, follow=False, detail=False, delete=False):
        redis = ctx.redis
        if not jid: # List mode
            jids = [ j.split(':')[1] for j in redis.keys(Job._key('*')) ]
            if not detail:
                return jids 
            jobs = []
            for jid in jids:
                job = Job.load_task(jid, redis)
                if not job:
                    LOG.warning("bad job <{0}> in redis, missing context".format(jid))
                    continue
                jobs.append(job.ctx)
            return jobs


        job = Job.load_task(jid, redis)
        if not job:
            raise JobNotExistsError("no such jid {0}".format(jid))
        if delete:
            if job._state == Job.STATE_RUNNING:
                raise JobDeleteError("cannot delete a running job")
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

    def __init__(self, targets, operate, mutex=True, 
            operate_args={}, startat=0, utag=None, state=None, taskid=None, error=""):
        """ Create job context instance. """
        self._id = taskid
        self._op = operate
        self._opargs = operate_args
        self._state = state
        self._targets = targets
        self._startat = startat
        self._utag = utag    # for avoid data keys conflict

        self._rdata = {}     # for store return data of job
        self._error = error  # for store error message of job

        if not mutex:
            self._op = self._op + ':' + self._random_tag
        if not self._startat:
            self._startat = int(time.time())
        if not self._utag:
            self._utag = self._random_tag

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
            utag = t.pop('utag'),
            startat = int(t.pop('startat')),
            operate_args = json.loads(t.pop('operate_args')),
            error = t.pop('error')))

    @property
    def dict_ctx(self):
        """ Dump job context to dict object for later recreate. """
        return dict(mutex=True,
                state=self._state,
                taskid=self._id,
                targets=self._targets,
                operate=self._op,
                operate_args = self._opargs,
                startat=self._startat,
                utag=self._utag,
                error=self._error)

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
        return "{0}:{1}:{2}:data".format(fqdn, self._op, self._utag)

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

        If no conflict, job context (the `meta_keys`) will created via redis pipeline 
            to avoid operate confilct.
        """
        pipeline = redis.pipeline()
        try:
            pipeline.watch(self.meta_keys)
            for key in self.meta_keys:
                if pipeline.exists(key):
                    raise JobConflictError("operate conflict, job already exists on some host(s)")

            LOG.info("going to create job meta data <{0}>".format(';'.join(self.meta_keys)))
            pipeline.multi()
            for key in self.meta_keys:
                pipeline.hmset(key, dict(startat=self._startat))
            pipeline.execute()
            LOG.info("job meta data create finished, <{0}>".format(';'.join(self.meta_keys)))

        except WatchError:
            LOG.info("conflict detected on job meta data create <{0}>".format(';'.join(self.meta_keys)))
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
        pipeline = redis.pipeline(False)
        pipeline.hmset(self._key(task.id), dict(
            state=Job.STATE_RUNNING, targets=json.dumps(self._targets),
            operate=self._op, operate_args=json.dumps(self._opargs), 
            utag=self._utag, startat=self._startat, error=""))
        for key in self.meta_keys:
            pipeline.hset(key, 'associate', task.id)
        pipeline.execute()
        return task.id

    def bind(self, taskid):
        """ Bind job context with celery task by taskid. """
        self._id = taskid

    def update(self, target, retval, redis):
        """ Update job context with target and retval. """
        content = json.dumps(retval)
        redis.publish("{0}:{1}".format(target, self._op), content)
        redis.rpush(self._data_key(target), content)

    def update_done(self, redis, target, failed=False):
        """ Logging and update Job Context when operate on target was done. """
        if failed:
            state = "failed"
            if not self._error:
                self._error = "some operations failed on {0}".format(target)
        else:
            state = "successed"
        LOG.info("{0} operation on {1} of {2} was {3}".format(self.operate, target, self._id, state))

    def done(self, redis, failed=False, error=""):
        """ Mark job as done or failed if failure is `True`. """
        if failed:
            redis.publish("{0}:control".format(self._op), Job.FAILURE)
            state = Job.STATE_FAILURE
        else:
            redis.publish("{0}:control".format(self._op), Job.DONE)
            state = Job.STATE_DONE

        if not error:
            error = self._error

        pipeline = redis.pipeline(False)
        pipeline.hset(self._key(self._id), 'error', error)
        pipeline.hset(self._key(self._id), 'state', state)
        pipeline.delete(*self.meta_keys)
        pipeline.execute()

    def reaper(self, redis):
        """ Reaper job and corresponding context (meta/data keys). """
        pipeline = redis.pipeline(False)
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
