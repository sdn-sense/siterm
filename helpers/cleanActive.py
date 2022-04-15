#!/usr/bin/env python3
"""Clean up all active deltas and make it empty"""
import sys
import pprint
from DTNRMLibs.FECalls import getDBConn
from DTNRMLibs.MainUtilities import getVal, evaldict, getUTCnow


def cleanup(sitename):
    """ Clan ALL Active Deltas"""
    dbI = getVal(getDBConn('CleanUp'), **{'sitename': sitename})
    activeDeltas = dbI.get('activeDeltas')
    action = 'insert'
    print('='*100)
    print('    Will delete the following active deltas from %s RM' % sitename)
    if activeDeltas:
        activeDeltas = activeDeltas[0]
        activeDeltas['output'] = evaldict(activeDeltas['output'])
        action = 'update'
    if not activeDeltas:
        action = 'insert'
    pprint.pprint(activeDeltas)
    activeDeltas = {'id': activeDeltas['id'],
                    'insertdate': int(getUTCnow()),
                    'updatedate': int(getUTCnow()),
                    'output': '{}'}
    if action ==  'insert':
        dbI.insert('activeDeltas', [activeDeltas])
    elif action == 'update':
        dbI.update('activeDeltas', [activeDeltas])

if __name__ == "__main__":
    cleanup(sys.argv[1])
