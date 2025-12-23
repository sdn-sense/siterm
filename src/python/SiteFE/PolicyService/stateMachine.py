#!/usr/bin/env python3
# pylint: disable=line-too-long
"""Everything goes here when they do not fit anywhere else.

Copyright 2017 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2016 California Institute of Technology
Date                    : 2018/11/26
"""
import json

from SiteRMLibs.DefaultParams import DELTA_COMMIT_TIMEOUT, DELTA_REMOVE_TIMEOUT
from SiteRMLibs.MainUtilities import getLoggingObject, getUTCnow


class StateMachine:
    """State machine for Frontend and policy service."""

    def __init__(self, config):
        self.config = config
        self.logger = getLoggingObject(config=self.config, service="PolicyService")
        self.limit = 100

    def stateChangerDelta(self, dbObj, newState, **kwargs):
        """Delta State change."""
        tNow = getUTCnow()
        self.logger.info(f"Changing delta {kwargs['uid']} to {newState}")
        dbObj.update("deltas", [{"uid": kwargs["uid"], "state": newState, "updatedate": tNow}])
        dbObj.insert(
            "states",
            [{"deltaid": kwargs["uid"], "state": newState, "insertdate": tNow}],
        )

    @staticmethod
    def modelstatechanger(dbObj, newState, **kwargs):
        """Model State change."""
        tNow = getUTCnow()
        dbObj.update(
            "deltasmod",
            [{"uid": kwargs["uid"], "modadd": newState, "updatedate": tNow}],
        )

    def modelstatecancel(self, dbObj, **kwargs):
        """Cancel Model addition."""
        if kwargs["modadd"] in ["idle"]:
            self.modelstatechanger(dbObj, "removed", **kwargs)
        elif kwargs["modadd"] in ["add", "added"]:
            self.modelstatechanger(dbObj, "remove", **kwargs)

    def _newdelta(self, dbObj, delta, state):
        """Add new delta to db."""
        dbOut = {
            "uid": delta["ID"],
            "insertdate": int(delta["insertdate"]),
            "updatedate": int(delta["updatedate"]),
            "state": str(state),
            "deltat": str(delta["Type"]),
            "content": json.dumps(delta["content"]),
            "modelid": str(delta["modelId"]),
            "modadd": str(delta["modadd"]),
            "error": "" if "Error" not in list(delta.keys()) else str(delta["Error"]),
        }
        dbObj.insert("deltas", [dbOut])
        dbOut["state"] = delta["State"]
        self.stateChangerDelta(dbObj, delta["State"], **dbOut)

    def accepting(self, dbObj, delta):
        """Marks delta as accepted."""
        self._newdelta(dbObj, delta, "accepted")

    def accepted(self, dbObj):
        """Marks delta as accepted."""
        # Get all deltas in accepted state and check timeout
        for dbentry in dbObj.get("deltas", search=[["state", "accepted"], ["insertdate", "<", getUTCnow() - DELTA_COMMIT_TIMEOUT]], limit=50):
            self.logger.info(f"Delta {dbentry['uid']} is in accepted state for more than {DELTA_COMMIT_TIMEOUT} seconds. Changing to remove state.")
            self.stateChangerDelta(dbObj, "remove", **dbentry)

    def commit(self, dbObj, delta):
        """Marks delta as committing."""
        self.stateChangerDelta(dbObj, "committing", **delta)

    def committing(self, dbObj):
        """Committing state Check."""
        # it should change state only if there are no activating deltas right now
        # Otherwise print message that I have to wait
        for delta in dbObj.get("deltas", search=[["state", "activating"]]):
            if delta["updatedate"] < int(getUTCnow() - 180):
                msg = f"Not able to accept new deltas. Delta {delta['uid']} is still in state activating after 3 minutes. Will not commit anything until it is done"
                return msg
            self.logger.info("There are deltas still in activating state. Will not commit anything until it is done")
            return None
        for delta in dbObj.get("deltas", search=[["state", "committing"]]):
            self.stateChangerDelta(dbObj, "committed", **delta)
            self.modelstatechanger(dbObj, "add", **delta)

    def committed(self, dbObj):
        """Committed state Check."""
        for delta in dbObj.get("deltas", search=[["state", "committed"]]):
            self.stateChangerDelta(dbObj, "activating", **delta)

    def activating(self, dbObj):
        """Check on all deltas in state activating."""
        for delta in dbObj.get("deltas", search=[["state", "activating"]]):
            if delta["modadd"] in ["added", "removed"]:
                self.stateChangerDelta(dbObj, "activated", **delta)
            if delta["modadd"] == "failed":
                self.stateChangerDelta(dbObj, "failed", **delta)

    def activated(self, dbObj):
        """Check on all activated state deltas."""
        for delta in dbObj.get("deltas", search=[["state", "activated"]]):
            if delta["modadd"] == "removed":
                self.stateChangerDelta(dbObj, "remove", **delta)

    def remove(self, dbObj):
        """Check on all remove state deltas."""
        # Remove fully from database
        for delta in dbObj.get("deltas", search=[["state", "remove"], ["updatedate", "<", int(getUTCnow() - DELTA_REMOVE_TIMEOUT)]]):
            self.stateChangerDelta(dbObj, "removed", **delta)
            self.modelstatecancel(dbObj, **delta)

    @staticmethod
    def removed(dbObj):
        """Check on all remove state deltas."""
        # Remove fully from database
        for delta in dbObj.get("deltas", search=[["state", "removed"]]):
            print(f"Remove {delta['id']} delta")
            dbObj.delete("deltas", [["id", delta["id"]]])

    def failed(self, dbObj, delta):
        """Marks delta as failed. This is only during submission"""
        self._newdelta(dbObj, delta, "failed")
