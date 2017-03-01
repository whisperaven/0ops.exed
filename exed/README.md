# EXEd

**EXEd** is an api service which provide remote execute (including code release) on top of **exector plugins (e.g.: ansible/salt plugin)**

# Consts/Enum
Usage | Type | Value
---|---|---
Job State Done | int | 0
Job State Running | int | 1
Job State Failure | int | 2
Operate State OK | int | 0
Operate State Skiped | int | 1
Operate State Failed | int | 2
Operate State Unreachable | int | 3
Operate State Changed | int | 4
Service State Started | int | 0
Service State Stoped | int | 1
Service State Restarted | int | 2

- Job State for async job.
- Operate State for executor task.
- Service State for service api endpoint.

# CLI/Flags
Flags | Usage | Default
---|---|---
-h/--help | show usage | -
-v/--version | show version | -
-c/--conf | path to config file | ${cwd}/exe.conf
-d/--daemon | run as daemon | run frontground 
--exe-conf | celery worker ext args | -

# Config
Opts | Section | Usage | Default
---|---|---|---
listen | api | api listen address | 127.0.0.1
listen_port | api | api listen port | 16808
pid_file | api | api server pidfile | - (no pidfile)
executor | runner | executor plugin | ansible
concurrency | runner | celery concurrency | ${nproc}
redis_url | runner | redis connection info | redis://127.0.0.1:6379
broker_url | runner | rmq connection info | amqp://guest:guest@localhost:5672//
log_level | log | log level of exe server | debug
error_log | log | error log path | - (stdout)
access_log | log | access log path | - (stdout)

- these options under log section doesn't affect celery worker

# Executor Plugins Config
Opts | Section | Usage | Default
---|---|---|---
workdir | ansible | ansible work dir | ${cwd}
inventory | ansible | ansible inventory file/dir | inventory
playbooks | ansible | ansible playbooks dir | playbooks
sshkey | ansible | path to ssh private key file | -

# Run it:
```shell
$ bin/exed -c etc/exe.conf -d                                   # start the api server
$ celery worker -A exe.runner -l info --exe-conf etc/exe.conf   # start the celery worker
```

- Before you do that, you should have rabbitmq/redis server deployed.
- Make sure both api/worker can access rabbitmq and redis server.
- Make sure your ansible (including playbooks and inventory) was on the same machine with both api/worker.

# EXEd Remote API

## Target/Hosts Endpoint Summary
Endpoint | Usage | Supported method
--- | --- | ---
/target${query_params} | Match and list remote hosts with given pattern | GET

## Jobs Endpoint Summary
Endpoint | Usage | Supported method
--- | --- | ---
/targets${query_params} | Match and list remote hosts with given pattern | GET
/jobs/(jid)${query_params} | List all jobs or query specific job | GET
/jobs/(jid) | Delete specific job | DELETE

## Operate Endpoint Summary
Endpoint | Usage | Supported method
--- | --- | ---
/ping${query_params} | Ping remote host (block/sync mode) | GET
/ping | Ping remote host(s) (non-block/async mode) | POST
/facter${query_params} | Gather facter info of remote host (block/sync mode) | GET
/facter | Gather facter info of remote host(s) (non-block/async mode) | POST
/service${query_params} | Manipulate service on remote host (block/sync mode) | GET
/service | Manipulate service on remote host(s) (non-block/async mode) | POST
/execute${query_params} | Execute raw command on remote host (block/sync mode) | GET
/execute | Execute raw command on remote host(s) (non-block/async mode) | POST
/deploy | Deploy service/role/app on remote host(s) (non-block/async mode) |POST

## Release Endpoint Summary
Endpoint | Usage | Supported method
--- | --- | ---
/release | Gather release plugins info | GET
/release | Gather released revision or release new revision on remote host(s) | POST

## Errors

- The Remote API uses standard HTTP status codes to indicate the success of failure of the API call. 
- The body of the response will be JSON in the following format:

    ```
    {
        "message": "operate conflict"
    }
    ```

## Target/Hosts Endpoints
### Host Match/List
``` GET /target ```

Match and list remote hosts with given pattern, return json string array contain all matched hosts.

##### Example request:
```
GET /target?pattern=karazhan.* HTTP/1.1
```

##### Example response:
```
HTTP/1.1 200 OK
Content-Type: application/json

["karazhan.0ops.io", "karazhan...", ...]
```

##### Query parameters:
- **pattern**: str, pattern use to match remote host fqdn. Default using '\*' for match all hosts.

##### Status codes:
- **200** - no error
- **400** - bad request/parameter
- **500** - server error

## Jobs Endpoints
### Job List
``` GET /jobs ```

List current jobs, return json string array contain all jobs.

##### Example request:
```
GET /jobs HTTP/1.1
```

##### Example response:
```
HTTP/1.1 200 OK
Content-Type: application/json

["eb1f4035-d62b-497f-9e3f-543e8e6f15f3", "c4f6acd3-4dda-44d0-8f99-76b4587e55d0", ...]
```

Those are Job IDs (jid)

##### Status codes:
- **200** - no error
- **400** - bad request/parameter
- **500** - server error

### Job Query
``` GET /jobs/(jid) ```

Query job by job ID.

##### Example request:
```
GET /jobs/c4f6acd3-4dda-44d0-8f99-76b4587e55d0?outputs=1&follow=1 HTTP/1.1
```

##### Example response:
```
HTTP/1.1 200 OK
Transfer-Encoding: chunked

{
    "state": 0, 
    "error": "",
    "startat": 1488272314,
    "operate": "deploy",
    "operate_args": {
        "role": "nginx",
        "partial": null",
        "extra_vars": {}
    },
    "return_data": {},
    "targets": [
        "molten-core.0ops.io", 
        "karazhan.0ops.io",
    ]

    {"molten-core.0ops.io": {"state": 4, ...}}
    {"karazhan.0ops.io": {"state": 4, ...}}
}
```

- The content of each chunk is depend on operate type of this job.
- The server will using chunked transfer encoding when query with **follow=1**.

##### Query parameters:
- **outputs**: 1/True/true or 0/False/false, show return data of each operations. Only Job State are shown by default.
- **follow**: 1/True/true or 0/False/false, show return data of each operations using **follow** mode (http chunked).

##### Status codes:
- **200** - no error
- **400** - bad request/parameter
- **404** - no such jobs
- **500** - server error

### Job Delete
``` DELETE /jobs/(jid) ```

Delete job by job ID.

##### Example request:
```
DELETE /jobs/eb1f4035-d62b-497f-9e3f-543e8e6f15f3 HTTP/1.1
```

##### Example response:
```
HTTP/1.1 204 No Content
```

##### Status codes:
- **204** - no error
- **400** - bad request/parameter
- **404** - no such jobs
- **500** - server error

## Operate Endpoints (Block/Sync Mode)
### Ping (Block Mode)
``` GET /ping ```

Ping remote host in block mode

##### Example request:
```
GET /ping?target=molten-core.0ops.io HTTP/1.1
```

##### Example response:
```
HTTP/1.1 200 OK
Content-Type: application/json

{"molten-core.0ops.io": {"status": 0}}
```

status 0 -> ok with no changed (see ```Consts/Enum``` section for more details on operate state)

##### Query parameters:
- **target (required)**: fqdn of remote host to ping.

##### Status codes:
- **200** - no error
- **400** - bad request/parameter
- **404** - no such host
- **500** - server error

### Gather Facter Informations (Block Mode)
``` GET /facter ```

Gather facter info of remote host in block mode

##### Example request:
```
GET /facter?target=molten-core.0ops.io HTTP/1.1
```

##### Example response:
```
HTTP/1.1 200 OK
Content-Type: application/json

{
    "molten-core.0ops.io": {
        "state": 0,
        "facter": {
            (...facter json...)
        },
}
```

again, state 0 means ok with no changed (see ```Consts/Enum``` section for more details on operate state)

##### Query parameters:
- **target (required)**: fqdn of remote host to gather facter from.

##### Status codes:
- **200** - no error
- **400** - bad request/parameter
- **404** - no such host
- **500** - server error

### Manipulate service (Block Mode)
``` GET /service ```

Manipulate service on remote host in block mode

##### Example request:
```
GET /service?target=molten-core.0ops.io&state=2&name=nginx&graceful=1 HTTP/1.1
```

##### Example response:
```
HTTP/1.1 200 OK
Content-Type: application/json

{"molten-core.0ops.io": {"status": 4}}
```

state 4 means ok with something changed (see ```Consts/Enum``` section for more details on operate state)

##### Query parameters:
- **target (required)**: fqdn of remote host to gather facter from.
- **state (required)**: operate type (see ```Consts/Enum``` section for more details on service state enum)
- **name (required)**: service name.
- **graceful**: 1/True/true or 0/False/false, do graceful restart (reload) when state is restarted. Default is false.

##### Status codes:
- **200** - no error
- **400** - bad request/parameter
- **404** - no such host
- **500** - server error

### Execute RAW Command (Block Mode)
``` GET /execute ```

Execute RAW Command on remote host in block mode

##### Example request:
```
GET /execute?target=molten-core.0ops.io&cmd=ifconfig HTTP/1.1
```

##### Example response:
```
HTTP/1.1 200 OK
Content-Type: application/json

{
    "molten-core.0ops.io": {
        "status": 4,
        "rtc": 0,
        "stderr": "",
        "stdout": "(...output of ifconfig...)"
    }
}
```

state 4 means ok with something changed (see ```Consts/Enum``` section for more details on operate state)

##### Query parameters:
- **target (required)**: fqdn of remote host to gather facter from.
- **cmd (required)**: command to run on remote host

##### Status codes:
- **200** - no error
- **400** - bad request/parameter
- **404** - no such host
- **500** - server error

## Operate Endpoints (Non-Block/Async Modes)

### Deploy
``` POST /deploy ```

Deploy service/role/app on remote host(s), only support async mode.

##### Example request:
```
POST /deploy HTTP/1.1
Content-Type: application/json

{
	"targets": [
		"molten-core.0ops.io",
		"karazhan.0ops.io",
	],
	"role": "nginx",
	"partial": "reconfig",
	"extra_vars": {
		"upstreams": [
			"127.0.0.1:8080",
			"127.0.0.1:8081",
		],
		"server_name": "exe.0ops.io"
	}
}
```

##### Example response:
```
HTTP/1.1 201 Create
Content-Type: application/json

{"jid": "c4f6acd3-4dda-44d0-8f99-76b4587e55d0"}
```

- Job in async mode (not only deploy) only return jid without block when job was created.
- **EXEd** doesn't known the detail about role/partial/extra_vars, it just pass them to the executor plugin, for this request, with ansible plugin, which means:
  - There should be an ansible playbooks role with name **nginx**.
  - Inside that role, there should be a tag with name **reconfig**.

##### JSON parameters:
- **targets (required)** - String array, remote hosts to deploy.
- **role (required)** - String, the role/app to deploy on remote hosts.
- **partial** - String, only deploy things marked by this tag.
- **extra_vars** - Object, vars which used by the role (e.g.: render config).

##### Status codes:
- **201** - job created
- **400** - bad parameter
- **500** - server error

### Ping / Facter / Service / Execute
``` POST /ping | /facter | /service | /execute ```

Do operate in non-block/async mode.

##### Example request:
```
POST /service HTTP/1.1
Content-Type: application/json

{
	"targets": [
		"molten-core.0ops.io",
		"karazhan.0ops.io",
	],
	"name": "ntp",
	"state": 2,
	"graceful": true,
}
```

##### Example response:
```
HTTP/1.1 201 Create
Content-Type: application/json

{"jid": "eb1f4035-d62b-497f-9e3f-543e8e6f15f3"}
```

- All job in async mode only return jid without block when job was created.

##### JSON parameters:
- Those api have same parameters of their corresponding method in **block/sync mode**.
- The different here is async mode using **POST** with json data instead of **GET** with query string.

##### Status codes:
- **201** - job created
- **400** - bad request/parameter
- **500** - server error

## Release Endpoings

### Release plugins info (Block/Sync Mode)
``` GET /release ```

Gather release plugins info from server

##### Example request:
```
GET /release HTTP/1.1
```

##### Example response:
```
HTTP/1.1 200 OK
Content-Type: application/json

[
    {
        "type": "common",
        "name": "common_release"
    },
    {
        "type": "something_else",
        "name": "yet_another_release"
    }
]
```

- The server current have two release plugins loaded.

##### Status codes:
- **200** - no error
- **400** - bad request/parameter
- **500** - server error

### Release/Rollback/GatherRevision (Non-Block/Async Mode)
``` POST /release ```

Release/Rollback/GatherRevision on remote host(s).

##### Example request:
```
POST /release HTTP/1.1
Content-Type: application/json

{
	"targets": [
		"molten-core.0ops.io",
		"karazhan.0ops.io",
	],
    "appname": "zerops", 
    "apptype": "common", 
    "revision": "1cc5aae96d61fd491f6dc626a06e3d3b792182b1", 
    "rollback": false, 
    "extra_opts": {
        "giturl": "git@github.com:whisperaven/0ops.git",
        "concurrency": 1,
        "graceful_reload": false,
        (...options...)
    }
}
```

##### Example response:
```
HTTP/1.1 201 Create
Content-Type: application/json

{"jid": "c4f6acd3-4dda-44d0-8f99-76b4587e55d0"}
```

- Every Job in async mode (including ping/facter/service/etc.) only return jid without block when job was created.
- **EXEd** doesn't known the detail about release, it just pass them to the release plugin, for this request, means:
  - There should be an release plugin with **\_\_RHANDLER_TYPE\_\_ = "common"**.
  - The **release** method of that plugin will invoked: **release(revison, \*\*extra_opts)**.
  - When **rollback** is **true**, the **rollback** method of that plugin will invoked: **rollback(revision, \*\*extra_opts)**.
  - When **revision** is **?**, the **revision** method of that plugin will invoked: **revision(\*\*extra_opts)**

##### JSON parameters:
- **targets (required)** - String array, remote hosts to release.
- **appname (required)** - String, name of app to release.
- **apptype (required)** - String, type of release plugin to use.
- **revision (required)** - String, the revision to release/rollback.
- **extra_opts** - Object, extra options to the release/rollback/revision method of release plugin.

