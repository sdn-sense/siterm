#!/usr/bin/env python
import sys
from DTNRMLibs.MainUtilities import getVal
from DTNRMLibs.MainUtilities import evaldict
from SiteFE.PolicyService.stateMachine import StateMachine
from DTNRMLibs.MainUtilities import getConfig, getLogger, getStreamLogger
from DTNRMLibs.FECalls import getDBConn

#LOGGER = getStreamLogger()
config = getConfig()
LOGGER = getLogger("%s/%s/" % (config.get('general', 'logDir'), 'local'))
stateMachine = StateMachine(LOGGER)

def getdeltaAll(sitename):
    dbI = getDBConn()
    dbobj = getVal(dbI, sitename=sitename)
    for delta in dbobj.get('deltas'):
        delta['addition'] = evaldict(delta['addition'])
        delta['reduction'] = evaldict(delta['reduction'])
        print '='*80
        print 'Delta UID  :  ', delta['uid']
        print 'Delta RedID:  ', delta['reductionid']
        print 'Delta State:  ', delta['state']
        print 'Delta ModAdd: ', delta['modadd']
        print 'Delta InsDate:', delta['insertdate']
        print 'Delta Update: ', delta['updatedate']
        print 'Delta Model:  ', delta['modelid']
        print 'Delta connID: ', delta['connectionid']
        print 'Delta Deltatype: ', delta['deltat']
        print '-'*20
        print 'Delta times'
        for deltatimes in dbobj.get('states', search=[['deltaid', delta['uid']]]):
            print 'State: %s Date: %s' % (deltatimes['state'], deltatimes['insertdate'])
        if delta['deltat'] not in ['reduction', 'addition']:
            print 'SOMETHING WRONG WITH THIS DELTA. It does not have any type defined. Was not parsed properly'
            continue
        if 'hosts' not in delta[delta['deltat']].keys():
            print 'SOMETHING WRONG WITH THIS DELTA. It does not have any hosts defined.'
            continue
        for hostname in delta[delta['deltat']]['hosts'].keys():
            print '-'*20
            print 'Host States %s' % hostname
            for hoststate in dbobj.get('hoststates', search=[['deltaid', delta['uid']], ['hostname', hostname]]):
                print 'Host %s State %s' % (hostname, hoststate['state'])
                print 'Insertdate %s UpdateDate %s' % (hoststate['insertdate'], hoststate['updatedate'])
                print '-'*20
                print 'Host State History'
                for hstatehistory in dbobj.get('hoststateshistory', search=[['deltaid', delta['uid']], ['hostname', hostname]]):
                    print 'State: %s, Date: %s' % (hstatehistory['state'], hstatehistory['insertdate'])

if __name__ == "__main__":
    getdeltaAll(sys.argv[1])
