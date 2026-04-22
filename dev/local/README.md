# Local Development

Run a localhost SiteRM development stack from the repository root:

```bash
make local-up
```

`make local-up` creates `dev/local/venv` with Python 3.12 and installs the SiteRM Python requirements there before launching services. If an existing local venv uses a different Python version, it is recreated. To use a specific Python 3.12 binary:

```bash
make PYTHON_BOOTSTRAP=/path/to/python3.12 local-up
```

Local development skips `easysnmp` by default because it is only needed for the SNMP monitoring worker and often requires native Net-SNMP libraries. To include it:

```bash
make LOCAL_WITH_SNMP=true local-up
```

`LOCAL_WITH_SNMP=true` requires Homebrew `net-snmp` to be installed and linked.

The Makefile starts a MariaDB container on `127.0.0.1:13306`, initializes the SiteRM tables, generates local JWT and X.509 material, and launches:

- Frontend: `http://127.0.0.1:8080`
- Agent: localhost manual config
- Debugger: localhost manual config

Useful targets:

```bash
make local-status
make logs
make local-stop
make local-db-down
```

Create a local Frontend user after the database is up:

```bash
make local-user-create LOCAL_USERNAME=admin LOCAL_USER_PERMISSION=admin
```

This uses `siterm-usertool` and prompts for the password interactively. The generic wrapper is also available for list, disable, enable, delete, and password reset operations:

```bash
make local-usertool LOCAL_USERTOOL_ARGS="list"
make local-usertool LOCAL_USERTOOL_ARGS="set-password admin"
```

Runtime files are generated under `dev/local/{certs,jwt,logs,run,state}`. The tracked configuration lives under `dev/local/conf`.
