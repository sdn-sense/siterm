#!/usr/bin/python
"""
Plugin which gathers all sysctl parameters

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
import pprint
from DTNRMAgent.RecurringActions.Utilities import externalCommand, tryConvertToNumeric
from DTNRMLibs.MainUtilities import getConfig

NAME = 'SystemKernelParams'


def get(config):
    """Get System kernel parameters information"""
    del config
    kernelInfo = {}
    tmpOut = externalCommand('sysctl -a')
    for item in tmpOut:
        for desc in item.split('\n'):
            vals = desc.split(' = ')
            if len(vals) == 2:
                kernelInfo[vals[0].strip()] = tryConvertToNumeric(vals[1].strip())
            else:
                print 'KernelParams: Skipped this item: ', vals
    return kernelInfo

if __name__ == "__main__":
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(get(getConfig(['/etc/dtnrm/main.conf', 'main.conf'])))
