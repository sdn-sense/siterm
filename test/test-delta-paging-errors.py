# pylint: disable=line-too-long
"""Unit tests for delta/model list pagination and delta error persistence.

Self-contained: uses an in-memory SQLite database, no SiteFE instance required.

Run:
    source dev-env.sh
    cd test
    python3 -m unittest test-delta-paging-errors
"""

import asyncio
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi import HTTPException
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.ext.compiler import compiles


@compiles(LONGTEXT, "sqlite")
def _longtextSqlite(_type, _compiler, **_kw):
    """Render MySQL LONGTEXT as TEXT on SQLite."""
    return "TEXT"


os.environ["DATABASE_URL"] = "sqlite://"

# pylint: disable=wrong-import-position
from SiteFE.PolicyService.stateMachine import StateMachine
from SiteRMLibs.DBBackend import dbinterface
from SiteRMLibs.DBModels import REGISTRY, Base

# SiteFE.REST.Delta/Model read the startup config and SiteFE.REST.dependencies loads Git config, auth keys and DB at import; stub those.
with tempfile.NamedTemporaryFile("w", suffix=".yaml") as _conf:
    _conf.write("SITENAME: T0_TEST\n")
    _conf.flush()
    with (
        mock.patch.dict(os.environ, {"SITERM_CONFIG_FILE": _conf.name}),
        mock.patch("SiteRMLibs.GitConfig.getGitConfig", return_value={}),
        mock.patch("SiteRMLibs.MainUtilities.getDBConnObj"),
        mock.patch("SiteFE.PolicyService.stateMachine.StateMachine"),
        mock.patch("SiteRMLibs.Auth.AuthHandler"),
    ):
        from SiteFE.REST import Delta, Model  # pylint: disable=ungrouped-imports

SITENAME = "T0_TEST"
ERROR = {"errType": "<class 'SiteRMLibs.CustomExceptions.OverlapException'>", "errNo": "-9", "errMsg": "VLAN 1433 already in use"}


def _delta(uid, insertdate, **kwargs):
    """Build a deltas table row."""
    row = {"uid": uid, "insertdate": insertdate, "updatedate": insertdate, "state": "activated", "deltat": "submission", "content": "{}", "modelid": "m1", "modadd": "added", "error": ""}
    row.update(kwargs)
    return row


class DBTestCase(unittest.TestCase):
    """Fresh in-memory database per test."""

    def setUp(self):
        self.dbI = dbinterface()
        Base.metadata.create_all(self.dbI.db.engine, tables=[REGISTRY[name].__table__ for name in ("deltas", "states", "models")])


class DBInterfacePagingTest(DBTestCase):
    """dbinterface.get offset and dbinterface.count."""

    def setUp(self):
        super().setUp()
        self.dbI.insert("deltas", [_delta(f"d{i}", 1000 + i) for i in range(1, 6)])

    def test_offset_pages(self):
        """Limit/offset walk through rows without overlap."""
        pages = [[row["uid"] for row in self.dbI.get("deltas", limit=2, offset=offset, orderby=["id", "DESC"])] for offset in (0, 2, 4)]
        self.assertEqual(pages, [["d5", "d4"], ["d3", "d2"], ["d1"]])

    def test_count(self):
        """count honours search filters and ignores limit."""
        self.assertEqual(self.dbI.count("deltas"), 5)
        self.assertEqual(self.dbI.count("deltas", search=[["updatedate", ">", 1003]]), 2)
        self.assertEqual(self.dbI.count("deltas", search=[["uid", "d2"]]), 1)


class GetDeltasEndpointTest(DBTestCase):
    """GET /api/{sitename}/deltas pagination."""

    def setUp(self):
        super().setUp()
        self.dbI.insert("deltas", [_delta(f"d{i}", 1000) for i in range(1, 6)])
        self.deps = {"dbI": self.dbI, "config": {"MAIN": {SITENAME: {}}}}

    def _call(self, **kwargs):
        """Call getDeltas and return (status, body, headers)."""
        request = SimpleNamespace(headers={"accept": "application/json"}, base_url="http://fe/")
        params = {"summary": True, "limit": 2, "offset": 0, "deps": self.deps, "_forbid": None}
        params.update(kwargs)
        resp = asyncio.run(Delta.getDeltas(request, sitename=SITENAME, **params))
        return resp.status_code, json.loads(resp.body), resp.headers

    def test_pages_and_total(self):
        """Pages are stable when insertdates tie and X-Total-Count reports all deltas."""
        seen = []
        for offset in (0, 2, 4):
            code, body, headers = self._call(offset=offset)
            self.assertEqual(code, 200)
            self.assertEqual(headers["x-total-count"], "5")
            seen.extend(item["id"] for item in body)
        self.assertEqual(seen, ["d5", "d4", "d3", "d2", "d1"])

    def test_offset_past_end(self):
        """Offset beyond the last delta returns 404 like an empty system."""
        with self.assertRaises(HTTPException) as ctx:
            self._call(offset=10)
        self.assertEqual(ctx.exception.status_code, 404)


class GetModelsEndpointTest(DBTestCase):
    """GET /api/{sitename}/models pagination."""

    def setUp(self):
        super().setUp()
        self.dbI.insert("models", [{"uid": f"m{i}", "insertdate": 1000, "fileloc": f"/tmp/m{i}"} for i in range(1, 6)])
        self.deps = {"dbI": self.dbI, "config": {"MAIN": {SITENAME: {}}}}

    def _call(self, **kwargs):
        """Call getModelInfo and return (status, body, headers)."""
        request = SimpleNamespace(headers={"accept": "application/json"}, base_url="http://fe/")
        params = {"current": False, "summary": True, "encode": True, "limit": 2, "offset": 0, "rdfformat": "turtle", "deps": self.deps, "_forbid": None}
        params.update(kwargs)
        resp = asyncio.run(Model.getModelInfo(request, sitename=SITENAME, **params))
        return resp.status_code, json.loads(resp.body), resp.headers

    def test_pages_and_total(self):
        """Pages are stable when insertdates tie and X-Total-Count reports all models."""
        seen = []
        for offset in (0, 2, 4):
            code, body, headers = self._call(offset=offset)
            self.assertEqual(code, 200)
            self.assertEqual(headers["x-total-count"], "5")
            seen.extend(item["id"] for item in body)
        self.assertEqual(seen, ["m5", "m4", "m3", "m2", "m1"])

    def test_offset_past_end(self):
        """Offset beyond the last model returns 404 like an empty system."""
        with self.assertRaises(HTTPException) as ctx:
            self._call(offset=10)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_current_ignores_offset(self):
        """current=True still returns only the latest model, without X-Total-Count."""
        code, body, headers = self._call(current=True, offset=4)
        self.assertEqual(code, 200)
        self.assertEqual(len(body), 1)
        self.assertNotIn("x-total-count", headers)


class DeltaErrorPersistenceTest(DBTestCase):
    """Failure reasons are stored as JSON in deltas.error."""

    def setUp(self):
        super().setUp()
        self.sm = StateMachine.__new__(StateMachine)
        self.sm.logger = mock.Mock()

    def _row(self, uid):
        """Return the deltas row for uid."""
        return self.dbI.get("deltas", search=[["uid", uid]])[0]

    def test_activation_failure_saves_error(self):
        """modadd=failed with errmsg stores the error and survives the move to failed state."""
        self.dbI.insert("deltas", [_delta("d1", 1000, state="activating", modadd="add")])
        self.sm.modelstatechanger(self.dbI, "failed", errmsg=ERROR, **self._row("d1"))
        self.sm.activating(self.dbI)
        row = self._row("d1")
        self.assertEqual(row["state"], "failed")
        self.assertEqual(json.loads(row["error"]), ERROR)

    def test_modelstatechanger_without_error_keeps_error(self):
        """Plain model state changes do not overwrite a stored error."""
        self.dbI.insert("deltas", [_delta("d1", 1000, error=json.dumps(ERROR))])
        self.sm.modelstatechanger(self.dbI, "remove", **self._row("d1"))
        row = self._row("d1")
        self.assertEqual(row["modadd"], "remove")
        self.assertEqual(json.loads(row["error"]), ERROR)

    def test_submission_failure_saves_json_error(self):
        """Submission failures store the error as JSON."""
        delta = {"ID": "d1", "insertdate": 1000, "updatedate": 1000, "Type": "submission", "content": {}, "modelId": "m1", "modadd": "idle", "State": "failed", "Error": ERROR}
        self.sm.failed(self.dbI, delta)
        row = self._row("d1")
        self.assertEqual(row["state"], "failed")
        self.assertEqual(json.loads(row["error"]), ERROR)


if __name__ == "__main__":
    unittest.main()
