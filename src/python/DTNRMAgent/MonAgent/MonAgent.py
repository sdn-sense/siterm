#!/usr/bin/python
# This is still for TESTING. TODO
"""
DTN Main Agent code, which executes all Plugins and publishes values to FE

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
Title 			: dtnrm
Author			: Justas Balcas
Email 			: justas.balcas (at) cern.ch
@Copyright		: Copyright (C) 2016 California Institute of Technology
Date			: 2017/09/26
"""
import json
import tempfile
import urllib2
import requests
import potsdb
from DTNRMLibs.MainUtilities import getDefaultConfigAgent
from DTNRMLibs.MainUtilities import contentDB, getConfig

COMPONENT = "MonAgent"

def makeGETRequest(url, headers=None):
    """ Make get Request with headers and url params using request """
    print 'Making GET Request to: %s' % url
    req = requests.request('GET', url, headers=headers)
    try:
        return req.status_code, json.loads(req.content), req.headers
    except ValueError:
        return req.status_code, req.content, req.headers

def getNetdataConfig():
    """
    Get netdata server config and also check backend configuration
    Returns: boolean: True - success in getting config and all parameters defined correctly.
                      False - Failure in retrieving one or another configuration parameters.
             dict: {} - if boolean return is False, always empty as failed to retrieve.
                   otherwise dictionary of all parsed configuration parameters
    """
    outDict = {}
    with tempfile.NamedTemporaryFile(delete=False) as fd:
        try:
            tmpConf = makeGETRequest("http://localhost:19999/netdata.conf")
            for line in tmpConf[1].splitlines():
                fd.write(line.replace('\t', '') + "\n")
        except urllib2.URLError as ex:
            print 'Received URLError %s. Checking if config file is present locally' % ex
            return False, {}
    tempfileName = fd.name
    hostConfig = getConfig([tempfileName])
    for option in ['enabled', 'destination']:
        if not hostConfig.has_option('backend', option):
            print 'Netdata server is not configured to publish anything to any backend'
            print '* Skipping this node check.'
            return False, {}
    for optionKey in hostConfig.options('backend'):
        outDict[optionKey] = hostConfig.get('backend', optionKey)
    # Make boolean from send names instead of ids
    if 'send names instead of ids' in outDict:
        if outDict['send names instead of ids'] == 'yes':
            outDict['dimensionids'] = True
        elif outDict['send names instead of ids'] == 'no':
            outDict['dimensionids'] = False
        else:
            outDict['dimensionids'] = True
    else:
        outDict['dimensionids'] = False
        outDict['send names instead of ids'] = 'no'
    if 'host tags' in outDict:
        outDict['tags'] = {}
        for item in outDict['host tags'].split(" "):
            tmpTags = item.split('=')
            outDict['tags'][tmpTags[0]] = tmpTags[1]
        # host tags = hostname=sensei3.ultralight.org nodetype=sense-service sitename=T2_US_Caltech
    return True, outDict

def getAgentStatus():
    """Get Agent Status and mark one or another flag for monitoring"""
    return
# TODO: This mon agent should read all configs prepared by loop execute, which has a timestamp;
# ok < 5minutes;
# warning > 5 minutes < 10minutes;
# fail > 10 minutes;
# TODO later, have it as a configurable option


def execute(configIn=None, loggerIn=None):
    """ Execute main script for DTN-RM Agent output preparation """
    config, logger = getDefaultConfigAgent(COMPONENT, configIn, loggerIn)
    if not config.getboolean(COMPONENT, 'enabled'):
        logger.info('Component is not enabled in configuration.')
        return
    success, outConfig = getNetdataConfig()
    if not success:
        logger.warning('Failure receiving netdata configuration file. Exiting')
        exit(1)
    workDir = config.get('agent', 'PRIVATE_DIR') + "/DTNRM/"
    agentDB = contentDB(logger=logger, config=config)
    # TODO Implement enabled option and debug per each component.
    # if not config.getboolean(COMPONENT, 'enabled'):
    #    return  # http://vocms025.cern.ch:19999/api/v1/alarms?active&_=1508422746160
    agents = makeGETRequest("http://localhost:19999/api/v1/alarms?active")
    out = {'netdata.warnings': 0, 'netdata.critical': 0, 'sense.nodes': 1, 'sense.vlansInUse': 0,
           'sense.vlansFree': 0, 'sense.vlansTotal': 0, 'sense.agentError': 0, 'sense.agentWarning': 0,
           'sense.agent.recurringactions.status': 0, 'sense.agent.recurringactions.runtime': 0,
           'sense.agent.ruler.status': 0, 'sense.agent.ruler.runtime': 0}
    for _dKey, dVals in agents[1]['alarms'].items():
        if dVals['status'] == 'WARNING':
            out['netdata.warnings'] += 1
        elif dVals['status'] == 'CRITICAL':
            out['netdata.critical'] += 1
    agentOut = agentDB.getFileContentAsJson(workDir + "/latest-out.json")
    for _interf, interfDict in agentOut['NetInfo'].items():
        if 'vlan_range' in interfDict:
            lowR, highR = interfDict['vlan_range'].split(',')
            out['sense.agentError'] += 1 if int(int(highR) - int(lowR)) < 0 else 0
            out['sense.vlansTotal'] += int(int(highR) - int(lowR))
        out['sense.vlansInUse'] = len(interfDict['vlans'])
    out['sense.agentError'] += 1 if int(out['sense.vlansTotal'] - out['sense.vlansInUse']) < 0 else 0
    out['sense.vlansFree'] = int(out['sense.vlansTotal'] - out['sense.vlansInUse'])
    if 'destination' in outConfig:
        if len(outConfig['destination'].split(':')) == 3:
            destHostname = outConfig['destination'].split(':')[1]
            destPort = outConfig['destination'].split(':')[2]
        elif len(outConfig['destination'].split(':')) == 2:
            destHostname = outConfig['destination'].split(':')[0]
            destPort = outConfig['destination'].split(':')[1]
        else:
            print 'FAILURE. Was expecting protocol:ip:port or ip:port... Got Value: %s' % outConfig['destination']
            return
    else:
        print 'FAILURE. Backend is not configured'
        return
    metrics = potsdb.Client(destHostname, port=destPort, qsize=1000, host_tag=True, mps=100, check_host=True)
    for key, value in out.items():
        metrics.send("monit.%s" % key, value, **outConfig['tags'])
    # waits for all outstanding metrics to be sent and background thread closes
    metrics.wait()

if __name__ == '__main__':
    execute()
