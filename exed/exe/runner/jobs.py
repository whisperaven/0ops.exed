# -*- coding: utf-8 -*-

import time
import uuid
import json

from redis import WatchError

from exe.exc import JobConflictError, JobNotExistsError

from .context import Context


class JobQuerier(Context):

    __RUNNER_NAME__ = "job"
    __RUNNER_MUTEX_REQUIRE__ = False

    def handle(ctx, jid=None, outputs=False, follow=False, delete=False):

        redis = ctx.redis
        if not jid:
            return [ j.split(':')[1] for j in redis.keys(Job.job_key('*')) ]

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

    STATE_DONE = 0
    STATE_RUNNING = 1
    STATE_FAILURE = 2

    DONE = "__DONE__"
    FAILURE = "__FAILURE__"

    def __init__(self, targets, operate, mutex=True, state=None, taskid=None):

        self._id = taskid
        self._op = operate
        self._targets = targets
        self._state = state
        self._rdata = {}

        if not mutex:
            self._op = self._op + ':' + self._random_tag

    @property
    def _random_tag(self):
        return uuid.uuid4().hex

    @property
    def dict_ctx(self):
        return dict(targets=self._targets, operate=self._op, mutex=True,
            state=self._state, taskid=self._id)

    @property
    def ctx(self):
        _ctx = self.dict_ctx
        _ctx.update(dict(return_data=self._rdata))
        _ctx.pop('taskid')
        _ctx.pop('mutex')
        _ctx['operate'] = _ctx['operate'].split(':')[0]
        return _ctx

    @classmethod
    def load(cls, dict_ctx):
        return cls(**dict_ctx)

    @classmethod
    def load_task(cls, taskid, redis):

        _t = redis.hgetall(cls.job_key(taskid))
        if not _t:
            return _t

        targets = json.loads(_t.pop('targets'))
        operate = _t.pop('operate')
        state = int(_t.pop('state'))

        return cls(**dict(targets=targets, operate=operate, taskid=taskid, state=state))

    @staticmethod
    def job_key(taskid):
        return "job:{0}".format(taskid)

    @property
    def meta_keys(self):
        return [ self._meta_key(_fqdn) for _fqdn in self._targets ]

    @property
    def data_keys(self):
        return [ self._data_key(_fqdn) for _fqdn in self._targets ]

    def _meta_key(self, fqdn):
        return "{0}:{1}:meta".format(fqdn, self._op)

    def _data_key(self, fqdn):
        return "{0}:{1}:data".format(fqdn, self._op)

    def load_data(self, redis):
        for key in self.data_keys:
            target = key.split(':')[0]
            rdata = redis.lrange(key, 0, -1)

            self._rdata.update({target: [ json.loads(retval) for retval in rdata ]})

    def create(self, redis):

        start = time.time()
        pipe = redis.pipeline()

        try:
            pipe.watch(self.meta_keys)
            for key in self.meta_keys:
                if pipe.exists(key):
                    raise JobConflictError("operate conflict, job already exists on some host(s)")
            pipe.multi()
            for key in self.meta_keys:
                pipe.hmset(key, dict(state=Job.STATE_RUNNING, start=start))
            pipe.execute()
        except WatchError:
            raise JobConflictError("operate conflict, try again later")
        finally:
            pipe.reset()

    def associate_task(self, task, redis):
        redis.hmset(self.job_key(task.id), dict(
            state=Job.STATE_RUNNING, targets=json.dumps(self._targets),
            operate=self._op))
        return task.id

    def bind_task(self, taskid):
        self._id = taskid

    def task_update(self, target, retval, redis):
        retval = json.dumps(retval)
        redis.publish("{0}:{1}".format(target, self._op), retval)
        redis.rpush(self._data_key(target), retval)

    def task_failure(self, target, redis):
        return redis.hset(self._meta_key(target), 'state', Job.STATE_FAILURE)

    def task_done(self, target, redis):
        return redis.hset(self._meta_key(target), 'state', Job.STATE_DONE)

    def failure(self, redis):
        redis.publish("{0}:control".format(self._op), Job.FAILURE)
        return redis.hset(self.job_key(self._id), 'state', Job.STATE_FAILURE)

    def done(self, redis):
        redis.publish("{0}:control".format(self._op), Job.DONE)
        return redis.hset(self.job_key(self._id), 'state', Job.STATE_DONE)

    def reaper(self, redis):
        pipe = redis.pipeline(False)
        pipe.delete(*self.meta_keys)
        pipe.delete(*self.data_keys)
        pipe.delete(self.job_key(self._id))
        pipe.execute()
        return ""   # Delete return 204 no content

    def follow(self, redis):

        cc = "{0}:control".format(self._op)
        rc = [ "{0}:{1}".format(target, self._op) for target in self._targets ]
        ps = redis.pubsub(ignore_subscribe_messages=True)

        ps.subscribe(cc, *rc)
        yield self.ctx
        if self.ctx['state'] != Job.STATE_RUNNING:
            return

        for msg in ps.listen():
            value = msg['data']
            source = msg['channel']

            if source == cc:
                break
            source = source.split(':')[0]   ## remove the operate 
            yield {source: json.loads(value)}

