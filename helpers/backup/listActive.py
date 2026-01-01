#!/usr/bin/env python3
"""List Active configuration"""

import pprint
import sys

from SiteRMLibs.MainUtilities import evaldict, getDBConn, getVal


def listActive(sitename):
    """List Active"""
    dbI = getVal(getDBConn("List"), **{"sitename": sitename})
    activeDeltas = dbI.get("activeDeltas")
    print("=" * 100)
    if activeDeltas:
        activeDeltas = activeDeltas[0]
        activeDeltas["output"] = evaldict(activeDeltas["output"])
    pprint.pprint(activeDeltas)


if __name__ == "__main__":
    listActive(sys.argv[1])
