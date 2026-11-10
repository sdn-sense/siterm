#!/usr/bin/env python3
"""
DB Backend for communication with database.
"""

import json
import os
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from SiteRMLibs.DBModels import REGISTRY, Base, KVStore, Lease, Model, ModelContent
from sqlalchemy import URL, create_engine, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

# ==========================================================
#  Utilities
# ==========================================================


def getUTCnow() -> int:
    """Get UTC time as epoch seconds."""
    return int(datetime.now(timezone.utc).timestamp())


def loadEnvFile(filepath="/etc/environment"):
    """Load environment variables from a file (best effort)."""
    if not os.path.isfile(filepath):
        return
    try:
        with open(filepath, "r", encoding="utf-8") as fd:
            for line in fd:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export ") :]
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    except Exception as ex:
        exc = traceback.format_exc()
        print(f"Failed loading env file {filepath}. Error: {ex}. Trace: {exc}")


# Characters the FE container cannot pass through intact: shell sourcing of /etc/environment,
# and the sed substitution into the double-quoted SQL literal done by mariadb_init.sh.
DB_PASSWORD_FORBIDDEN_CHARS = "\"'`\\/&$;|<>()"


def validateDBPassword(password):
    """Raise ValueError if the MariaDB password is unset, a template placeholder or has unsupported characters."""
    if not password:
        raise ValueError("MARIA_DB_PASSWORD is not set. Set it in the environment file.")
    if "".join(ch for ch in password.upper() if ch.isalpha()) == "REPLACEME":
        raise ValueError(f"MARIA_DB_PASSWORD is still the template placeholder ({password}). Set a real password in the environment file.")
    if any(ch.isspace() or not ch.isprintable() or ch in DB_PASSWORD_FORBIDDEN_CHARS for ch in password):
        raise ValueError(f"MARIA_DB_PASSWORD contains unsupported characters. Whitespace and any of {' '.join(DB_PASSWORD_FORBIDDEN_CHARS)} are not allowed.")


def buildDatabaseURL() -> str:
    """
    Build SQLAlchemy DATABASE_URL for MariaDB/MySQL.

    Priority:
      1. DATABASE_URL env var
      2. Construct from MARIA_DB_* variables
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    user = os.getenv("MARIA_DB_USER", "root")
    password = os.getenv("MARIA_DB_PASSWORD", "")
    validateDBPassword(password)
    host = os.getenv("MARIA_DB_HOST", "localhost")
    port = os.getenv("MARIA_DB_PORT", "3306")
    database = os.getenv("MARIA_DB_DATABASE", "sitefe")
    charset = os.getenv("MARIA_DB_CHARSET", "utf8mb4")

    return URL.create(
        "mysql+pymysql",
        username=user,
        password=password,
        host=host,
        port=int(port),
        database=database,
        query={"charset": charset},
    ).render_as_string(hide_password=False)


# ==========================================================
#  Database Backend
# ==========================================================
class DBBackend:
    """Database backend using SQLAlchemy ORM."""

    def __init__(self):
        loadEnvFile()

        self.database_url = buildDatabaseURL()
        self.autocommit = os.getenv("MARIA_DB_AUTOCOMMIT", "True") in ("True", "true", "1")
        self.engine = create_engine(self.database_url, pool_pre_ping=True, future=True)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)

    @contextmanager
    def session(self):
        """Provide a transactional scope around a series of operations on the database."""
        session = self.Session()
        try:
            yield session
            if self.autocommit:
                session.commit()
        except Exception:
            print(f"Full traceback: {traceback.format_exc()}")
            session.rollback()
            raise
        finally:
            session.close()

    def createdb(self):
        """Create all tables from ORM metadata."""
        Base.metadata.create_all(self.engine)

    def upgradedb(self, directory):
        """Initialize Alembic if needed, then always upgrade DB to head."""
        loadEnvFile()
        cfg = Config("/etc/alembic.ini")
        # Alembic's ConfigParser interpolates '%', which URL.create emits for special password characters.
        cfg.set_main_option("sqlalchemy.url", self.database_url.replace("%", "%%"))
        cfg.set_main_option("script_location", str(directory))

        versionsDir = os.path.join(directory, "versions")

        try:
            if not os.path.isdir(versionsDir):
                print(f"Initializing Alembic in {directory}")
                command.init(cfg, directory)
            with self.engine.connect() as conn:
                context = MigrationContext.configure(conn)
                current = context.get_current_revision()
            if current is None:
                print("Database not stamped, stamping to base")
                command.stamp(cfg, "base")
            print(f"Upgrading database (current={current}) → head")
            command.upgrade(cfg, "head")
            return current
        except Exception:
            print("Database upgrade failed")
            print(traceback.format_exc())
            raise

    def executeRaw(self, sql):
        """
        Execute raw SQL directly on the engine.
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), {})
            conn.commit()
            return result

    def cleandb(self):
        """Delete all rows from all tables."""
        with self.session() as session:
            for model in REGISTRY.values():
                session.query(model).delete()

    def cleandbtable(self, tablename):
        """Delete all rows from a specific table."""
        model = REGISTRY.get(tablename)
        if not model:
            raise ValueError(f"Unknown table: {tablename}")
        with self.session() as session:
            session.query(model).delete()


class dbinterface:
    """Database interface used by applications."""

    def __init__(self, serviceName="", config="", sitename=""):
        self.serviceName = serviceName
        self.config = config
        self.sitename = sitename
        self.db = DBBackend()

    def createdb(self):
        """Create all tables in the database."""
        self.db.createdb()

    def upgradedb(self, directory):
        """Upgrade the database schema to the latest Alembic revision."""
        self.db.upgradedb(directory)

    def isDBReady(self) -> bool:
        """Check if the database is ready to accept connections."""
        try:
            with self.db.session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def executeRaw(self, sql):
        """Execute raw SQL directly on the engine."""
        return self.db.executeRaw(sql)

    @staticmethod
    def _filter(query, model, search):
        """Apply search filters ([col, val] or [col, op, val]; op may be 'in'/'notin' with a list) to a query."""
        for item in search or []:
            if len(item) == 2:
                query = query.filter(getattr(model, item[0]) == item[1])
            elif len(item) == 3 and str(item[1]).lower() == "in":
                query = query.filter(getattr(model, item[0]).in_(item[2]))
            elif len(item) == 3 and str(item[1]).lower() == "notin":
                query = query.filter(getattr(model, item[0]).not_in(item[2]))
            elif len(item) == 3:
                query = query.filter(getattr(model, item[0]).op(item[1])(item[2]))
        return query

    @staticmethod
    def _model(calltype):
        """Return the ORM model for a table name."""
        model = REGISTRY.get(calltype)
        if not model:
            raise ValueError(f"Unknown table: {calltype}")
        return model

    def get(self, calltype, limit=None, search=None, orderby=None, mapping=True, offset=None, columns=None):
        """Retrieve rows from a specific table; columns limits the loaded columns (skips large ones)."""
        model = self._model(calltype)

        with self.db.session() as session:
            if columns:
                q = self._filter(session.query(*[getattr(model, col) for col in columns]), model, search)
            else:
                q = self._filter(session.query(model), model, search)

            if orderby:
                col, direction = orderby
                q = q.order_by(getattr(model, col).desc() if direction.lower() == "desc" else getattr(model, col).asc())

            if limit:
                q = q.limit(limit)

            if offset:
                q = q.offset(offset)

            rows = q.all()

            if not mapping:
                return rows

            if columns:
                return [dict(zip(columns, row)) for row in rows]
            return [{c.name: getattr(row, c.name) for c in row.__table__.columns} for row in rows]

    def count(self, calltype, search=None):
        """Count rows in a specific table matching search filters."""
        model = REGISTRY.get(calltype)
        if not model:
            raise ValueError(f"Unknown table: {calltype}")

        with self.db.session() as session:
            return self._filter(session.query(model), model, search).count()

    def insert(self, calltype, values):
        """Insert rows into a specific table."""
        model = REGISTRY.get(calltype)
        if not model:
            raise ValueError(f"Unknown table: {calltype}")

        allowed = set(model.__table__.columns.keys())

        last_id = None
        with self.db.session() as session:
            for val in values:
                excluded = {k: v for k, v in val.items() if k not in allowed}
                clean_val = {k: v for k, v in val.items() if k in allowed}

                if excluded:
                    print(f"[DB INSERT WARNING] Table '{calltype}' ignored fields: {list(excluded.keys())}")

                obj = model(**clean_val)
                session.add(obj)
                session.flush()
                last_id = getattr(obj, "id", None)

        return "OK", "", last_id

    def update(self, calltype, values):
        """Update rows in a specific table."""
        model = REGISTRY.get(calltype)
        if not model:
            raise ValueError(f"Unknown table: {calltype}")

        allowed = set(model.__table__.columns.keys())

        with self.db.session() as session:
            for val in values:
                obj = None

                # Prefer id (fast PK lookup), fallback to uid
                if val.get("id") is not None:
                    obj = session.get(model, val.get("id"))
                elif "uid" in val and hasattr(model, "uid"):
                    obj = session.query(model).filter_by(uid=val.get("uid")).first()

                if not obj:
                    print(f"[DB UPDATE WARNING] No row found for update in '{calltype}': {val}")
                    raise ValueError(f"No row found for update in '{calltype}': {val} with id or uid")

                excluded = {k: v for k, v in val.items() if k not in allowed}
                clean_val = {k: v for k, v in val.items() if k in allowed}

                if excluded:
                    print(f"[DB UPDATE WARNING] Table '{calltype}' ignored fields: {list(excluded.keys())}")

                for key, value in clean_val.items():
                    if value is not None:
                        setattr(obj, key, value)

        return "OK", "", ""

    def delete(self, calltype, values):
        """Delete rows from a specific table."""
        model = REGISTRY.get(calltype)
        if not model:
            raise ValueError(f"Unknown table: {calltype}")

        allowed = set(model.__table__.columns.keys())

        with self.db.session() as session:
            q = session.query(model)
            for col, val in values:
                if col not in allowed:
                    print(f"[DB DELETE WARNING] Ignored invalid column '{col}' for table '{calltype}'")
                    continue
                q = q.filter(getattr(model, col) == val)
            q.delete(synchronize_session=False)

        return "OK", "", ""

    def delete_comp(self, calltype, column, op, value):
        """Delete rows with a comparison filter."""
        model = REGISTRY.get(calltype)
        if not model:
            raise ValueError(f"Unknown table: {calltype}")

        allowed = set(model.__table__.columns.keys())

        if column not in allowed:
            raise ValueError(f"Invalid column '{column}' for table '{calltype}'")

        column_attr = getattr(model, column)

        with self.db.session() as session:
            q = session.query(model)

            if op == "<":
                q = q.filter(column_attr < value)
            elif op == ">":
                q = q.filter(column_attr > value)
            elif op == "<=":
                q = q.filter(column_attr <= value)
            elif op == ">=":
                q = q.filter(column_attr >= value)
            elif op == "!=":
                q = q.filter(column_attr != value)
            elif op == "==":
                q = q.filter(column_attr == value)
            else:
                raise ValueError(f"Unsupported operator {op}")

            deleted = q.delete(synchronize_session=False)

        return deleted

    def _clean(self, _calltype, _values):
        """Clean the entire database."""
        self.db.cleandb()

    def _cleantable(self, calltype, _values):
        """Clean a specific table in the database."""
        self.db.cleandbtable(calltype)

    @staticmethod
    def get_timestamp_column(dbtable):
        """Get the name of the timestamp column for a given table."""
        model = REGISTRY.get(dbtable)
        if not model:
            return None

        columns = model.__table__.columns.keys()

        if "updatedate" in columns:
            return "updatedate"
        if "insertdate" in columns:
            return "insertdate"
        return None

    # ==========================================================
    #  Shared state helpers (kvstore, leases, model content)
    # ==========================================================

    def updatewhere(self, calltype, values, search):
        """Update columns on all rows matching search; return the number of rows changed."""
        model = self._model(calltype)
        allowed = set(model.__table__.columns.keys())
        clean = {k: v for k, v in values.items() if k in allowed}
        with self.db.session() as session:
            return self._filter(session.query(model), model, search).update(clean, synchronize_session=False)

    def deletesearch(self, calltype, search):
        """Delete all rows matching search filters; return the number of rows deleted."""
        model = self._model(calltype)
        if not search:
            raise ValueError("deletesearch requires at least one filter")
        with self.db.session() as session:
            return self._filter(session.query(model), model, search).delete(synchronize_session=False)

    def kvset(self, namespace, name, value):
        """Insert or replace a JSON-encoded kvstore value."""
        encoded = json.dumps(value)
        for _ in range(3):
            now = getUTCnow()
            try:
                with self.db.session() as session:
                    row = session.query(KVStore).filter_by(namespace=namespace, name=name).first()
                    if row:
                        row.value = encoded
                        row.updatedate = now
                    else:
                        session.add(KVStore(namespace=namespace, name=name, value=encoded, insertdate=now, updatedate=now))
                return
            except IntegrityError:
                # Another writer inserted the same key first; retry as an update.
                continue
        raise RuntimeError(f"Unable to store kvstore entry {namespace}/{name}")

    def kvadd(self, namespace, name, value):
        """Insert a JSON-encoded kvstore value only if the key does not exist yet; return True if inserted."""
        now = getUTCnow()
        # Own session: session() prints the traceback, with the statement parameters (the value, e.g. a key), on errors.
        session = self.db.Session()
        try:
            session.add(KVStore(namespace=namespace, name=name, value=json.dumps(value), insertdate=now, updatedate=now))
            session.commit()
            return True
        except IntegrityError:
            session.rollback()
            return False
        finally:
            session.close()

    def kvgetrow(self, namespace, name):
        """Return the kvstore row (value decoded) or None."""
        rows = self.get("kvstore", search=[["namespace", namespace], ["name", name]], limit=1)
        if not rows:
            return None
        row = rows[0]
        row["value"] = json.loads(row["value"]) if row["value"] else None
        return row

    def kvget(self, namespace, name, default=None):
        """Return the decoded kvstore value or default."""
        row = self.kvgetrow(namespace, name)
        return default if row is None else row["value"]

    def kvlist(self, namespace):
        """Return {name: row} for all entries of a namespace (values decoded)."""
        out = {}
        for row in self.get("kvstore", search=[["namespace", namespace]]):
            row["value"] = json.loads(row["value"]) if row["value"] else None
            out[row["name"]] = row
        return out

    def kvdelete(self, namespace, name):
        """Delete one kvstore entry; return True if it existed."""
        return bool(self.deletesearch("kvstore", [["namespace", namespace], ["name", name]]))

    def leaseacquire(self, name, holder, ttl):
        """Take, or renew, a lease; return True if holder owns it afterwards."""
        now = getUTCnow()
        with self.db.session() as session:
            renewed = (
                session.query(Lease)
                .filter(Lease.name == name, or_(Lease.holder == holder, Lease.expires_at < now))
                .update({"holder": holder, "expires_at": now + ttl, "updatedate": now}, synchronize_session=False)
            )
            if renewed:
                return True
            if session.query(Lease.id).filter(Lease.name == name).first():
                return False
        try:
            with self.db.session() as session:
                session.add(Lease(name=name, holder=holder, expires_at=now + ttl, updatedate=now))
            return True
        except IntegrityError:
            return False

    def leaserelease(self, name, holder):
        """Release a lease if holder owns it."""
        return bool(self.deletesearch("leases", [["name", name], ["holder", holder]]))

    def leaselive(self, prefix):
        """Return unexpired leases whose name starts with prefix."""
        return self.get("leases", search=[["name", "LIKE", f"{prefix}%"], ["expires_at", ">=", getUTCnow()]], orderby=["name", "asc"])

    def modelcontentput(self, uid, fmt, content):
        """Store compressed model content once per (uid, fmt)."""
        with self.db.session() as session:
            if session.query(ModelContent.id).filter_by(uid=uid, fmt=fmt).first():
                return False
        try:
            with self.db.session() as session:
                session.add(ModelContent(uid=uid, fmt=fmt, content=content, insertdate=getUTCnow()))
            return True
        except IntegrityError:
            return False

    def modelcontentget(self, uid, fmt):
        """Return compressed model content bytes or None."""
        rows = self.get("modelcontent", search=[["uid", uid], ["fmt", fmt]], limit=1, columns=["content"])
        return rows[0]["content"] if rows else None

    def modeltrim(self, keepseconds, maxcount):
        """Delete models older than keepseconds or beyond maxcount; the latest model is always kept."""
        deleted = 0
        with self.db.session() as session:
            latest = session.query(Model.id).order_by(Model.insertdate.desc(), Model.id.desc()).first()
            if not latest:
                return 0
            deleted += session.query(Model).filter(Model.insertdate < getUTCnow() - keepseconds, Model.id != latest[0]).delete(synchronize_session=False)
            extra = [row[0] for row in session.query(Model.id).order_by(Model.insertdate.desc(), Model.id.desc()).offset(maxcount).all()]
            extra = [mid for mid in extra if mid != latest[0]]
            if extra:
                deleted += session.query(Model).filter(Model.id.in_(extra)).delete(synchronize_session=False)
        return deleted

    def modelcontentcleanup(self):
        """Delete model content no models row refers to."""
        with self.db.session() as session:
            return session.query(ModelContent).filter(ModelContent.uid.not_in(select(Model.contentid))).delete(synchronize_session=False)

    def optimizetables(self, tables):
        """Rebuild tables to return space freed by deletes (MariaDB only)."""
        if self.db.engine.dialect.name not in ("mysql", "mariadb"):
            return []
        done = []
        for table in tables:
            self._model(table)
            self.executeRaw(f"OPTIMIZE TABLE `{table}`")
            done.append(table)
        return done
