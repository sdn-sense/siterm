SHELL := /usr/bin/env bash

ROOT := $(CURDIR)

LOCAL_DIR ?= $(ROOT)/dev/local
CONF_DIR := $(LOCAL_DIR)/conf
RUN_DIR := $(LOCAL_DIR)/run
LOG_DIR := $(LOCAL_DIR)/logs
STATE_DIR := $(LOCAL_DIR)/state
CERT_DIR := $(LOCAL_DIR)/certs
CA_DIR := $(CERT_DIR)/ca
JWT_DIR := $(LOCAL_DIR)/jwt
VENV_DIR ?= $(LOCAL_DIR)/venv
PYTHON_BOOTSTRAP ?= $(shell if command -v python3.12 >/dev/null 2>&1; then command -v python3.12; elif test -x /usr/local/opt/python@3.12/bin/python3.12; then echo /usr/local/opt/python@3.12/bin/python3.12; elif test -x /opt/homebrew/opt/python@3.12/bin/python3.12; then echo /opt/homebrew/opt/python@3.12/bin/python3.12; fi)
PYTHON_VERSION_REQUIRED ?= 3.12
PYTHON := $(VENV_DIR)/bin/python
PIP := $(PYTHON) -m pip
LOCAL_WITH_SNMP ?= false
DEPS_PROFILE := $(if $(filter true,$(LOCAL_WITH_SNMP)),snmp,no-snmp)
DEPS_STAMP := $(VENV_DIR)/.siterm-deps-$(DEPS_PROFILE)-installed
LOCAL_SITEFE_REQUIREMENTS := $(VENV_DIR)/requirements-sitefe-local.txt

SITENAME ?= T0_US_LOCALDEV
FE_HOST ?= 127.0.0.1
FE_PORT ?= 8080
FE_URL ?= http://$(FE_HOST):$(FE_PORT)

DB_CONTAINER ?= siterm-local-mariadb
DB_PORT ?= 13306
USE_DOCKER_DB ?= true
MARIA_DB_PASSWORD ?= siterm-dev
DATABASE_URL ?= mysql+pymysql://root:$(MARIA_DB_PASSWORD)@127.0.0.1:$(DB_PORT)/sitefe?charset=utf8mb4

AGENT_SLEEP ?= 30
DEBUGGER_SLEEP ?= 30
LOCAL_USERNAME ?= admin
LOCAL_USER_PERMISSION ?= admin
LOCAL_USERTOOL_ARGS ?= list

BASE_PYTHONPATH := $(ROOT)/src/python$(if $(PYTHONPATH),:$(PYTHONPATH))
SCRIPT_PATH := $(ROOT)/packaging/general:$(ROOT)/packaging/siterm-site-agent/scripts:$(ROOT)/packaging/siterm-site-fe/scripts:$(PATH)

COMMON_ENV = PYTHONPATH="$(BASE_PYTHONPATH)" PATH="$(SCRIPT_PATH)" DATABASE_URL="$(DATABASE_URL)" RSA_DIR="$(JWT_DIR)" OIDC_CA_DIR="$(CA_DIR)" OIDC_ISSUER="$(FE_URL)" OIDC_AUDIENCE="$(FE_URL)" X509_HOST_CERT="$(CERT_DIR)/localhost-dev.crt" X509_HOST_KEY="$(CERT_DIR)/localhost-dev.key" SITERM_STATIC_DIR="$(ROOT)/src/html" CONFIG_FETCHER_COUNTER="$(RUN_DIR)/config-fetcher-counter" OTEL_ENABLED=false
FE_ENV = $(COMMON_ENV) SITERM_CONFIG_FILE="$(CONF_DIR)/siterm-fe.yaml" MAIN_CONFIG_FILE="$(CONF_DIR)/fe-main.yaml" AUTH_CONFIG_FILE="$(CONF_DIR)/fe-auth.yaml" AUTH_RE_CONFIG_FILE="$(CONF_DIR)/fe-auth-re.yaml" MAPPING_TYPE=FE
AGENT_ENV = $(COMMON_ENV) SITERM_CONFIG_FILE="$(CONF_DIR)/siterm-agent.yaml" MAIN_CONFIG_FILE="$(CONF_DIR)/agent-main.yaml" MAPPING_TYPE=Agent
DEBUGGER_ENV = $(COMMON_ENV) SITERM_CONFIG_FILE="$(CONF_DIR)/siterm-debugger.yaml" MAIN_CONFIG_FILE="$(CONF_DIR)/debugger-main.yaml" MAPPING_TYPE=Agent

.PHONY: help local-up local-stop local-status local-venv local-install-deps local-check-deps local-prepare local-certs local-db-up local-db-wait local-db-init local-db-down local-config-ready local-user-create local-usertool local-start-fe local-start-agent local-start-debugger frontend agent debugger logs clean-local

help:
	@echo "SiteRM local development targets"
	@echo "  make local-up                 Prepare and start local DB, frontend, agent, debugger"
	@echo "  make local-stop               Stop local frontend, agent, debugger"
	@echo "  make local-db-down            Stop and remove the local MariaDB container"
	@echo "  make local-install-deps       Create venv and install Python requirements"
	@echo "  make local-check-deps         Check required Python modules for local launch"
	@echo "  make local-user-create        Create a local SiteFE user with siterm-usertool"
	@echo "  make local-usertool           Run siterm-usertool with LOCAL_USERTOOL_ARGS"
	@echo "  make local-status             Show local process status"
	@echo "  make logs                     Tail local logs"
	@echo "  make frontend|agent|debugger  Start one service"
	@echo ""
	@echo "Venv: $(VENV_DIR)"
	@echo "Overrides: PYTHON_BOOTSTRAP=$(PYTHON_BOOTSTRAP), VENV_DIR=$(VENV_DIR), FE_PORT=$(FE_PORT), DB_PORT=$(DB_PORT), USE_DOCKER_DB=$(USE_DOCKER_DB), LOCAL_WITH_SNMP=$(LOCAL_WITH_SNMP)"
	@echo "If FE_PORT changes, update webdomain in dev/local/conf/*-main.yaml as well."

local-up: local-check-deps local-prepare local-certs local-db-up local-db-wait local-db-init local-config-ready local-start-fe local-start-agent local-start-debugger
	@echo "Local SiteRM development stack is starting on $(FE_URL)"
	@echo "Logs are in $(LOG_DIR)"

$(PYTHON):
	@$(MAKE) local-venv

local-venv:
	@mkdir -p "$(LOCAL_DIR)"
	@if [ -z "$(PYTHON_BOOTSTRAP)" ]; then \
	  echo "Python $(PYTHON_VERSION_REQUIRED) is required for the local SiteRM venv."; \
	  echo "Install python@3.12 or set PYTHON_BOOTSTRAP=/path/to/python3.12."; \
	  exit 1; \
	fi
	@bootstrap_version=$$($(PYTHON_BOOTSTRAP) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"); \
	if [ "$$bootstrap_version" != "$(PYTHON_VERSION_REQUIRED)" ]; then \
	  echo "Python $(PYTHON_VERSION_REQUIRED) is required, but PYTHON_BOOTSTRAP=$(PYTHON_BOOTSTRAP) is $$bootstrap_version."; \
	  exit 1; \
	fi
	@if [ -x "$(PYTHON)" ]; then \
	  venv_version=$$($(PYTHON) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"); \
	  if [ "$$venv_version" != "$(PYTHON_VERSION_REQUIRED)" ]; then \
	    echo "Recreating $(VENV_DIR): found Python $$venv_version, need $(PYTHON_VERSION_REQUIRED)."; \
	    rm -rf "$(VENV_DIR)"; \
	  fi; \
	fi
	@if [ ! -x "$(PYTHON)" ]; then \
	  $(PYTHON_BOOTSTRAP) -m venv "$(VENV_DIR)"; \
	  $(PIP) install --upgrade pip setuptools wheel; \
	  echo "Created local Python $(PYTHON_VERSION_REQUIRED) venv at $(VENV_DIR)"; \
	fi

$(DEPS_STAMP): requirements-sitefe.txt requirements-agent.txt | local-venv
	@if [ "$(LOCAL_WITH_SNMP)" = "true" ]; then \
	  snmp_prefix=$$(brew --prefix net-snmp 2>/dev/null || true); \
	  if [ -z "$$snmp_prefix" ] || [ ! -d "$$snmp_prefix" ]; then \
	    echo "LOCAL_WITH_SNMP=true requires Homebrew net-snmp native libraries."; \
	    echo "Run: brew install net-snmp"; \
	    exit 1; \
	  fi; \
	  $(PIP) install -r requirements-sitefe.txt -r requirements-agent.txt; \
	else \
	  awk 'tolower($$1) != "easysnmp" { print }' requirements-sitefe.txt >"$(LOCAL_SITEFE_REQUIREMENTS)"; \
	  echo "Skipping easysnmp for local development. Use LOCAL_WITH_SNMP=true to install it."; \
	  $(PIP) install -r "$(LOCAL_SITEFE_REQUIREMENTS)" -r requirements-agent.txt; \
	fi
	@touch "$(DEPS_STAMP)"

local-install-deps: $(DEPS_STAMP)

local-check-deps: local-install-deps
	@$(PYTHON) -c "import pymysql, sqlalchemy, uvicorn, fastapi, yaml" >/dev/null 2>&1 || { \
	  echo "Missing Python dependencies for local SiteRM launch."; \
	  echo "Run: make local-install-deps"; \
	  echo "This target always uses the local venv at $(VENV_DIR)."; \
	  exit 1; \
	}

local-prepare:
	@mkdir -p "$(RUN_DIR)" "$(LOG_DIR)/sitefe" "$(LOG_DIR)/agent" "$(LOG_DIR)/debugger" "$(LOG_DIR)/config-fetcher" "$(STATE_DIR)/fe" "$(STATE_DIR)/agent" "$(STATE_DIR)/debugger" "$(CERT_DIR)" "$(CA_DIR)" "$(JWT_DIR)"

local-certs: local-prepare
	@if [ ! -f "$(JWT_DIR)/private_key.pem" ]; then \
	  openssl genrsa -out "$(JWT_DIR)/private_key.pem" 2048 >/dev/null 2>&1; \
	  openssl rsa -in "$(JWT_DIR)/private_key.pem" -pubout -out "$(JWT_DIR)/public_key.pem" >/dev/null 2>&1; \
	  echo "Generated JWT keys in $(JWT_DIR)"; \
	fi
	@if [ ! -f "$(CERT_DIR)/localhost-dev.crt" ]; then \
	  openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -subj "/CN=localhost-dev" -keyout "$(CERT_DIR)/localhost-dev.key" -out "$(CERT_DIR)/localhost-dev.crt" >/dev/null 2>&1; \
	  cp "$(CERT_DIR)/localhost-dev.crt" "$(CA_DIR)/localhost-dev.pem"; \
	  echo "Generated local X.509 certificate in $(CERT_DIR)"; \
	fi

local-db-up:
	@if [ "$(USE_DOCKER_DB)" != "true" ]; then \
	  echo "Skipping Docker DB startup; using DATABASE_URL=$(DATABASE_URL)"; \
	  exit 0; \
	fi
	@if ! command -v docker >/dev/null 2>&1; then \
	  echo "docker is required for local-db-up. Override DATABASE_URL if you want to use an existing database."; \
	  exit 1; \
	fi
	@if docker ps -a --format '{{.Names}}' | grep -qx "$(DB_CONTAINER)"; then \
	  docker start "$(DB_CONTAINER)" >/dev/null; \
	else \
	  docker run -d --name "$(DB_CONTAINER)" -e MARIADB_ROOT_PASSWORD="$(MARIA_DB_PASSWORD)" -e MARIADB_DATABASE=sitefe -p 127.0.0.1:$(DB_PORT):3306 mariadb:10.11 >/dev/null; \
	fi
	@echo "MariaDB is available at 127.0.0.1:$(DB_PORT)"

local-db-wait:
	@echo "Waiting for database at $(DATABASE_URL)"
	@last_error=""; \
	for attempt in $$(seq 1 60); do \
	  if out=$$($(COMMON_ENV) $(PYTHON) -c "from SiteRMLibs.DBBackend import dbinterface; raise SystemExit(0 if dbinterface().isDBReady() else 1)" 2>&1); then \
	    echo "Database is ready"; \
	    exit 0; \
	  fi; \
	  last_error="$$out"; \
	  if [ "$$attempt" = "1" ] || [ "$$((attempt % 10))" = "0" ]; then \
	    echo "Still waiting for database... attempt $$attempt/60"; \
	  fi; \
	  sleep 2; \
	done; \
	echo "Timed out waiting for database."; \
	if [ -n "$$last_error" ]; then \
	  echo "Last readiness error:"; \
	  echo "$$last_error"; \
	fi; \
	exit 1

local-db-init:
	@$(COMMON_ENV) $(PYTHON) -c "from SiteRMLibs.DBBackend import dbinterface; dbinterface().createdb(); print('Database tables are ready')"

local-user-create: local-check-deps local-db-up local-db-wait local-db-init
	@echo "Creating local SiteFE user '$(LOCAL_USERNAME)' with permission '$(LOCAL_USER_PERMISSION)'"
	@echo "The password prompt is handled by siterm-usertool."
	@$(FE_ENV) $(PYTHON) packaging/siterm-site-fe/scripts/siterm-usertool create "$(LOCAL_USERNAME)" --permission "$(LOCAL_USER_PERMISSION)"

local-usertool: local-check-deps local-db-up local-db-wait local-db-init
	@$(FE_ENV) $(PYTHON) packaging/siterm-site-fe/scripts/siterm-usertool $(LOCAL_USERTOOL_ARGS)

local-db-down:
	@if [ "$(USE_DOCKER_DB)" != "true" ]; then \
	  echo "Skipping Docker DB removal because USE_DOCKER_DB=$(USE_DOCKER_DB)"; \
	  exit 0; \
	fi
	@if command -v docker >/dev/null 2>&1 && docker ps -a --format '{{.Names}}' | grep -qx "$(DB_CONTAINER)"; then \
	  docker rm -f "$(DB_CONTAINER)" >/dev/null; \
	  echo "Removed $(DB_CONTAINER)"; \
	fi

local-config-ready: local-prepare local-certs
	@rm -f "$${TMPDIR:-/tmp}/config-fetcher-ready"
	@$(FE_ENV) $(PYTHON) packaging/general/Config-Fetcher --action start --logtostdout --bypassstartcheck --onetimerun >"$(LOG_DIR)/config-fetcher/config-fetcher.log" 2>&1 || { \
	  echo "Config-Fetcher failed. Last log lines:"; \
	  tail -n 80 "$(LOG_DIR)/config-fetcher/config-fetcher.log"; \
	  exit 1; \
	}
	@echo "Config readiness marker created"

local-start-fe: local-prepare local-certs
	@if [ -f "$(RUN_DIR)/frontend.pid" ] && kill -0 $$(cat "$(RUN_DIR)/frontend.pid") 2>/dev/null; then \
	  echo "Frontend already running with PID $$(cat "$(RUN_DIR)/frontend.pid")"; \
	else \
	  nohup env $(FE_ENV) $(PYTHON) -m uvicorn sitefe:app --app-dir "$(ROOT)/packaging/siterm-site-fe" --host "$(FE_HOST)" --port "$(FE_PORT)" >"$(LOG_DIR)/sitefe/frontend.log" 2>&1 & echo $$! >"$(RUN_DIR)/frontend.pid"; \
	  sleep 1; \
	  if ! kill -0 $$(cat "$(RUN_DIR)/frontend.pid") 2>/dev/null; then \
	    echo "Frontend failed to stay running. Last log lines:"; \
	    tail -n 80 "$(LOG_DIR)/sitefe/frontend.log"; \
	    exit 1; \
	  fi; \
	  echo "Started frontend on $(FE_URL) with PID $$(cat "$(RUN_DIR)/frontend.pid")"; \
	fi

local-start-agent: local-prepare local-certs
	@if [ -f "$(RUN_DIR)/agent.pid" ] && kill -0 $$(cat "$(RUN_DIR)/agent.pid") 2>/dev/null; then \
	  echo "Agent already running with PID $$(cat "$(RUN_DIR)/agent.pid")"; \
	else \
	  nohup env $(AGENT_ENV) $(PYTHON) packaging/siterm-site-agent/scripts/sitermagent-update --action start --logtostdout --bypassstartcheck --noreporting --sleeptimeok "$(AGENT_SLEEP)" >"$(LOG_DIR)/agent/agent.log" 2>&1 & echo $$! >"$(RUN_DIR)/agent.pid"; \
	  sleep 1; \
	  if ! kill -0 $$(cat "$(RUN_DIR)/agent.pid") 2>/dev/null; then \
	    echo "Agent failed to stay running. Last log lines:"; \
	    tail -n 80 "$(LOG_DIR)/agent/agent.log"; \
	    exit 1; \
	  fi; \
	  echo "Started agent with PID $$(cat "$(RUN_DIR)/agent.pid")"; \
	fi

local-start-debugger: local-prepare local-certs
	@if [ -f "$(RUN_DIR)/debugger.pid" ] && kill -0 $$(cat "$(RUN_DIR)/debugger.pid") 2>/dev/null; then \
	  echo "Debugger already running with PID $$(cat "$(RUN_DIR)/debugger.pid")"; \
	else \
	  nohup env $(DEBUGGER_ENV) $(PYTHON) packaging/general/siterm-debugger --action start --logtostdout --bypassstartcheck --noreporting --sleeptimeok "$(DEBUGGER_SLEEP)" >"$(LOG_DIR)/debugger/debugger.log" 2>&1 & echo $$! >"$(RUN_DIR)/debugger.pid"; \
	  sleep 1; \
	  if ! kill -0 $$(cat "$(RUN_DIR)/debugger.pid") 2>/dev/null; then \
	    echo "Debugger failed to stay running. Last log lines:"; \
	    tail -n 80 "$(LOG_DIR)/debugger/debugger.log"; \
	    exit 1; \
	  fi; \
	  echo "Started debugger with PID $$(cat "$(RUN_DIR)/debugger.pid")"; \
	fi

frontend: local-install-deps local-config-ready local-start-fe
agent: local-install-deps local-config-ready local-start-agent
debugger: local-install-deps local-config-ready local-start-debugger

local-stop:
	@for service in frontend agent debugger; do \
	  pidfile="$(RUN_DIR)/$$service.pid"; \
	  if [ -f "$$pidfile" ]; then \
	    pid=$$(cat "$$pidfile"); \
	    if kill -0 "$$pid" 2>/dev/null; then \
	      kill "$$pid"; \
	      echo "Stopped $$service PID $$pid"; \
	    fi; \
	    rm -f "$$pidfile"; \
	  fi; \
	done

local-status:
	@for service in frontend agent debugger; do \
	  pidfile="$(RUN_DIR)/$$service.pid"; \
	  if [ -f "$$pidfile" ] && kill -0 $$(cat "$$pidfile") 2>/dev/null; then \
	    echo "$$service: running with PID $$(cat "$$pidfile")"; \
	  else \
	    echo "$$service: stopped"; \
	  fi; \
	done

logs:
	@tail -n 80 -f "$(LOG_DIR)"/sitefe/frontend.log "$(LOG_DIR)"/agent/agent.log "$(LOG_DIR)"/debugger/debugger.log

clean-local: local-stop
	@rm -rf "$(RUN_DIR)" "$(LOG_DIR)" "$(STATE_DIR)" "$(CERT_DIR)" "$(JWT_DIR)" "$(VENV_DIR)"
	@rm -f "$${TMPDIR:-/tmp}/config-fetcher-ready" "$${TMPDIR:-/tmp}"/end-site-rm-*.pid
	@echo "Removed local runtime files"
