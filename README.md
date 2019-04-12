# EXEd

**EXEd** is an api service which provide remote execution on top of **Exector/Task Plugins**.

- Executor Plugins: plugins which implement the executor interface on top of ops tools (e.g.: ansible/salt) for remote execution.
- Task Plugins: plugins which implement the task interface on top of executor plugin for long run tasks like code release or rolling restart.

# Remote Execution

The api server listen on http request, serves remote execution request by invoke **Executor Plugin**, there are two types of remote execution

- Block/Sync via Http GET: The api server block request and invoke *executor* by itself and then respond with its result.
- NonBlock/Asnyc via Http POST: The api server send request to celery broker, and respond with a *jid* (job id) without block, the result of execution can be queried at `Job API`.

Which means, you need make sure both api server and celery worker can access *executor* context, for *ansible* executor implementation, these are playbooks and inventory.

## API & Celery Worker CLI

| Flags        | Component     | Description              | Default          |
| :----------: | :-----------: | :----------------------: | :--------------: |
| -h/--help    | API Server    | show help and exit       | -                |
| -v/--version | API Server    | show version and exit    | -                |
| -c/--conf    | API Server    | full path to exed.conf   | ${cwd}/exed.conf |
| -d/--daemon  | API Server    | run api server as daemon | run frontground  |
| --exe-conf   | Celery Worker | celery worker start args | -                |

## API & Celery Worker Configurations

| Options     | Section | Description                     | Default                             |
| :---------: | :-----: | :-----------------------------: | :---------------------------------: |
| listen_addr | api     | api listen address              | 127.0.0.1                           |
| listen_port | api     | api listen port                 | 16808                               |
| pid_file    | api     | api server pidfile              | - (no pidfile)                      |
| executor    | runner  | executor plugin name            | ansible                             |
| concurrency | runner  | executor concurrency            | ${nproc}                            |
| modules     | runner  | executor/task plugin directory  | ${cwd}/modules                      |
| redis_url   | runner  | redis connection info           | redis://127.0.0.1:6379              |
| broker_url  | runner  | broker connection info (celery) | amqp://guest:guest@localhost:5672// |
| log_level   | log     | log level of exe server         | debug                               |
| error_log   | log     | error log path                  | - (stdout)                          |
| access_log  | log     | access log path                 | - (stdout)                          |

- options under `log` section doesn't affect celery worker.
- `concurrency` only affect the executor tools (when use ansible, same as the `--forks` options).

## Executor Plugins Configuration
| Options   | Section | Description                  | Default   |
| :-------: | :-----: | :--------------------------: | :-------: |
| workdir   | ansible | ansible work dir             | ${cwd}    |
| playbooks | ansible | ansible playbooks dir        | playbooks |

- when use ansible executor plugin, there should be an **init pb** named `_deploy.yml`.
- the **init pb** should accept two vars: `_targets` and `_role`, for example:

  ```
  ## Deploy Playbook for zerops exed ##

  ## with_items not support for multiple roles ##
  ---
  - name: "deploy {{ _role }} on remote host(s)."
    hosts: "{{ _targets }}"
    roles:
      - "{{ _role }}"
    vars_files:
      - vars/common.yml
      - vars/others.yml
  ```

- **[Environmental configuration](http://docs.ansible.com/ansible/intro_configuration.html#environmental-configuration)** of ansible is the only way to change ansible settings.

## Run it:

``` shell
# install packages
$ pip install cherrypy ansible "celery[redis]"

# configure ansible
$ export ANSIBLE_HOST_KEY_CHECKING=False
$ export ANSIBLE_RETRY_FILES_ENABLED=False
$ export ANSIBLE_CONFIG="/opt/ansible/ansible.cfg"

# start the api server
$ bin/exed -c etc/exed.conf -d

# start the celery worker
$ celery worker --app exe.runner --loglevel info --exe-conf etc/exed.conf
```

- Before you do that, you should have broker/redis server deployed.
- Make sure both api/worker can access broker and redis server.
- Make sure your ansible (including playbooks and inventory) was on the same machine with both api/worker.

# Remote APIs

Current supported remote api endpoints

## Target/Hosts Endpoint

| Endpoint               | Description                                    | Supported method |
| :--------------------: | :--------------------------------------------: | :--------------: |
| /target${query_params} | Match and list remote hosts with given pattern | GET              |

## Jobs Endpoint

| Endpoint                   | Description                         | Supported method |
| :------------------------: | :---------------------------------: | :--------------: |
| /jobs/(jid)${query_params} | List all jobs or query specific job | GET              |
| /jobs/(jid)                | Delete specific job                 | DELETE           |

## Operate Endpoints

| Endpoint                | Description                                                      | Supported method |
| :---------------------: | :--------------------------------------------------------------: | :--------------: |
| /ping${query_params}    | Ping remote host (block/sync mode)                               | GET              |
| /ping                   | Ping remote host(s) (non-block/async mode)                       | POST             |
| /facter${query_params}  | Gather facter info of remote host (block/sync mode)              | GET              |
| /facter                 | Gather facter info of remote host(s) (non-block/async mode)      | POST             |
| /service${query_params} | Manipulate service on remote host (block/sync mode)              | GET              |
| /service                | Manipulate service on remote host(s) (non-block/async mode)      | POST             |
| /execute${query_params} | Execute raw command on remote host (block/sync mode)             | GET              |
| /execute                | Execute raw command on remote host(s) (non-block/async mode)     | POST             |
| /deploy                 | Deploy service/role/app on remote host(s) (non-block/async mode) | POST             |

## Tasks Endpoints

| Endpoint | Usage                                               | Supported method |
| -------- | --------------------------------------------------- | ---------------- |
| /tasks   | Gather task plugins info                            | GET              |
| /tasks   | Gather task state or run new task on remote host(s) | POST             |

## Errors

- The Remote API uses standard HTTP status codes to indicate the success or failure of the API call.
- The body of the response will be JSON in the following format:

    ```
    {
        "message": "operate conflict"
    }
    ```

# Remote API Enums

#### Job state enums

| State | Name    |
| :---: | :-----: |
| **0** | Done    |
| **1** | Running |
| **2** | Failure |

#### Operate state enums

| State | Name        |
| :---: | :---------: |
| **0** | ANNOUNCE    |
| **1** | OK          |
| **2** | Skiped      |
| **3** | Failed      |
| **4** | Unreachable |
| **5** | Changed     |

# Job API Reference

#### ` GET /jobs `

- List current jobs, return json string array contain all jobs.

    - Query parameters:
        - **detail**: `1/True/true` or `0/False/false`, show job detail of each jobs. Only jid(s) was returned by default.

    - Status codes:
        - **200** - no error
        - **400** - bad request/parameter
        - **500** - server error

    - Example request:
    ```
    GET /jobs HTTP/1.1
    ```

    - Example response:
    ```
    HTTP/1.1 200 OK
    Content-Type: application/json

    ["eb1f4035-d62b-497f-9e3f-543e8e6f15f3", "c4f6acd3-4dda-44d0-8f99-76b4587e55d0", ...]
    ```
    - Those items inside the return array are Job IDs (jids)

#### ` GET /jobs/(jid) `

- Query job by job ID.

    - Query parameters:
        - **outputs**: `1/True/true` or `0/False/false`, show return data of each operations. Only Job State was returned by default.
        - **follow**: `1/True/true` or `0/False/false`, show return data of each operations using *follow* mode (http chunked).

    - Status codes:
        - **200** - no error
        - **400** - bad request/parameter
        - **404** - no such jobs
        - **500** - server error

    - Example request:
    ```
    GET /jobs/c4f6acd3-4dda-44d0-8f99-76b4587e55d0?outputs=1&follow=1 HTTP/1.1
    ```

    - Example response:
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
            "karazhan.0ops.io"
        ]

        {"molten-core.0ops.io": {"state": 5, ...}}  (operation http chunk)
        {"karazhan.0ops.io": {"state": 5, ...}}     (operation http chunk)
    }
    ```

    - The server will using chunked transfer encoding when query with `follow=1`.
    - The content of each chunk is depend on operate type of that job.
    - Job state and operation state value, see `Remote API Enums` section.

#### ` DELETE /jobs/(jid) `

- Delete job by job ID.

    - Status codes:
        - **204** - no error
        - **400** - bad request/parameter
        - **404** - no such jobs
        - **500** - server error

    - Example request:
    ```
    DELETE /jobs/eb1f4035-d62b-497f-9e3f-543e8e6f15f3 HTTP/1.1
    ```

    - Example response:
    ```
    HTTP/1.1 204 No Content
    ```

# Execution API Reference

Result of all non-block/async jobs need query from the `/jobs` endpoint, each job will be marked as `Done` as soon as all remote hosts return without error, otherwise the job was marked as `Failure`.

#### ` GET /target `

- Match and list remote hosts with given pattern, return json string array contain all matched hosts.

    - Query parameters:
        - **pattern**: str, pattern use to match remote host fqdn. Default using `*` for match all hosts.

    - Status codes:
        - **200** - no error
        - **400** - bad request/parameter
        - **500** - server error

    - Example request:
    ```
    GET /target?pattern=karazhan.* HTTP/1.1
    ```

    - Example response:
    ```
    HTTP/1.1 200 OK
    Content-Type: application/json

    ["karazhan.0ops.io", "karazhan...", ...]
    ```

#### ` GET /ping `

- Ping remote host in block mode.

    - Query parameters:
        - **targets (required)**: fqdn of remote host to ping.

    - Status codes:
        - **200** - no error
        - **400** - bad request/parameter
        - **404** - no such host
        - **500** - server error

    - Example request:
    ```
    GET /ping?target=molten-core.0ops.io HTTP/1.1
    ```

    - Example response:
    ```
    HTTP/1.1 200 OK
    Content-Type: application/json

    {"molten-core.0ops.io": {"status": 1}}
    ```
    - `status` are operation state enum, see `Remote API Enums`

#### ` POST /ping `

- Ping remote host(s) in non block mode.

    - Request JSON:
        - **targets (required)**: list of fqdn of remote hosts to ping.

    - Status codes:
        - **201** - no error
        - **400** - bad request/parameter
        - **404** - no such host
        - **500** - server error

    - Example request:
    ```
    POST /ping HTTP/1.1
    Content-Type: application/json

    {
      "targets": [
        "molten-core.0ops.io",
        "karazhan.0ops.io"
      ]
    }
    ```

    - Example response:
    ```
    HTTP/1.1 201 Create
    Content-Type: application/json

    {"jid": "c4f6acd3-4dda-44d0-8f99-76b4587e55d0"}
    ```

#### ` GET /facter `

- Gather facter of remote host in block mode.

    - Query parameters:
        - **targets (required)**: fqdn of remote host to gather from.

    - Status codes:
        - **200** - no error
        - **400** - bad request/parameter
        - **404** - no such host
        - **500** - server error

    - Example request:
    ```
    GET /facter?target=molten-core.0ops.io HTTP/1.1
    ```

    - Example response:
    ```
    HTTP/1.1 200 OK
    Content-Type: application/json

    {
      "molten-core.0ops.io": {
        "status": 1,
        "facts": { ... }
      }
    }
    ```
    - `status` are operation state enum, see `Remote API Enums`

#### ` POST /facter `

- Gather facter of remote host(s) in non block mode.

    - Request JSON:
        - **targets (required)**: list of fqdn of remote hosts to gather from.

    - Status codes:
        - **201** - no error
        - **400** - bad request/parameter
        - **404** - no such host
        - **500** - server error

    - Example request:
    ```
    POST /facter HTTP/1.1
    Content-Type: application/json

    {
      "targets": [
        "molten-core.0ops.io",
        "karazhan.0ops.io"
      ]
    }
    ```

    - Example response:
    ```
    HTTP/1.1 201 Create
    Content-Type: application/json

    {"jid": "c4f6acd3-4dda-44d0-8f99-76b4587e55d0"}
    ```

#### ` GET /service `

- Manipulate service on remote host in block mode.

    - Query parameters:
        - **target (required)**: fqdn of remote host to gather facter from.
        - **state (required)**: service desired state.
        - **name (required)**: service name.
        - **graceful**: `1/True/true` or `0/False/false`, do graceful restart (reload) when state is *restarted*. Default is `false`.

    - Status codes:
        - **200** - no error
        - **400** - bad request/parameter
        - **404** - no such host
        - **500** - server error

    - Service Desired State:
        - **0** - Started
        - **1** - Stoped
        - **2** - Restarted

    - Example request:
    ```
    GET /service?target=molten-core.0ops.io&state=2&name=nginx&graceful=1 HTTP/1.1
    ```

    - Example response:
    ```
    HTTP/1.1 200 OK
    Content-Type: application/json

    {"molten-core.0ops.io": {"status": 5}}
    ```
    - `status` are operation state enum, see `Remote API Enums`

#### ` POST /service `

- Manipulate service on remote host(s) in non block mode.

    - Request JSON:
        - **target (required)**: list of fqdn of remote hosts to gather facter from.
        - **state (required)**: service desired state.
        - **name (required)**: service name.
        - **graceful**: `1/True/true` or `0/False/false`, do graceful restart (reload) when state is *restarted*. Default is `false`.

    - Status codes:
        - **201** - no error
        - **400** - bad request/parameter
        - **404** - no such host
        - **500** - server error

    - Service Desired State:
        - **0** - Started
        - **1** - Stoped
        - **2** - Restarted

    - Example request:
    ```
    POST /service HTTP/1.1
    Content-Type: application/json

    {
      "targets": [
        "molten-core.0ops.io",
        "karazhan.0ops.io"
      ],
      "name": "nginx",
      "state": 2,
      "graceful": true
    }
    ```

    - Example response:
    ```
    HTTP/1.1 201 Create
    Content-Type: application/json

    {"jid": "c4f6acd3-4dda-44d0-8f99-76b4587e55d0"}
    ```

#### ` GET /execute `

- Execute RAW Command on remote host in block mode.

    - Query parameters:
        - **target (required)**: fqdn of remote host to run the command.
        - **cmd (required)**: command to run on remote host

    - Status codes:
        - **200** - no error
        - **400** - bad request/parameter
        - **404** - no such host
        - **500** - server error

    - Example request:
    ```
    GET /execute?target=molten-core.0ops.io&cmd=ifconfig HTTP/1.1
    ```

    - Example response:
    ```
    HTTP/1.1 200 OK
    Content-Type: application/json

    {
        "molten-core.0ops.io": {
            "status": 5,
            "rtc": 0,
            "stderr": "",
            "stdout": "(...output of ifconfig...)"
        }
    }
    ```
    - `status` are operation state enum, see `Remote API Enums`

#### ` POST /execute `

- Execute RAW Command on remote host(s) in non block mode.

    - Request JSON:
        - **target (required)**: list of fqdn of remote hosts to run the command.
        - **cmd (required)**: command to run on remote host

    - Status codes:
        - **200** - no error
        - **400** - bad request/parameter
        - **404** - no such host
        - **500** - server error

    - Example request:
    ```
    POST /execute HTTP/1.1
    Content-Type: application/json

    {
      "targets": [
		"molten-core.0ops.io",
		"karazhan.0ops.io",
      ],
      "cmd": "ifconfig"
    }
    ```

    - Example response:
    ```
    HTTP/1.1 201 Create
    Content-Type: application/json

    {"jid": "c4f6acd3-4dda-44d0-8f99-76b4587e55d0"}
    ```

#### ` POST /deploy `

- Deploy service/role/app on remote host(s), only support async mode.

    - Request JSON:
        - **targets (required)** - list of fqdn of remote host(s) to deploy.
        - **role (required)** - str, the role/app to deploy on remote hosts.
        - **partial** - list of tag name, only deploy things marked by this tag.
        - **extra_vars** - objcet, vars which used by the role (e.g.: render config).

    - Status codes:
        - **201** - job created
        - **400** - bad parameter
        - **500** - server error

    - Example request:
    ```
    POST /deploy HTTP/1.1
    Content-Type: application/json

    {
      "targets": [
          "molten-core.0ops.io",
          "karazhan.0ops.io",
      ],
      "role": "nginx",
      "partial": [
        "reconfig",
      ],
      "extra_vars": {
        "upstreams": [
          "127.0.0.1:8080",
          "127.0.0.1:8081"
        ],
        "server_name": "exe.0ops.io"
      }
    }
    ```

    - Example response:
    ```
    HTTP/1.1 201 Create
    Content-Type: application/json

    {"jid": "c4f6acd3-4dda-44d0-8f99-76b4587e55d0"}
    ```
    - **EXEd** doesn't known the detail about `role/partial/extra_vars`, it just pass them to the executor plugin, for this request, with ansible plugin, means: There should be an ansible playbooks role with name `nginx`, and inside that role, there should be a tag with name `reconfig`.
