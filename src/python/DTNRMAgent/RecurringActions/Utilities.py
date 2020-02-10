"""
TODO: Move all of these to MainUtilities, as it is not a place for it...

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
import subprocess
import shlex
import psutil

def externalCommand(command):
    """Execute External Commands and return stdout and stderr"""
    command = shlex.split(command)
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.communicate()

def tryConvertToNumeric(value):
    """Convert str to float or int. Returns what should be expected, t.y.:
       if str is float, int will fail and float will be returned;
       if str is int, float and int will succeed, returns int;
       if any of these fail, returns value"""
    floatVal = None
    intVal = None
    try:
        floatVal = float(value)
    except ValueError:
        return value
    try:
        intVal = int(value)
    except ValueError:
        return floatVal if floatVal else value
    return intVal

def runPipedCmd(cmd1, cmd2):
    """ Run two commands, in which second is executed after first.
        Like in bash | t.y.: ls -l | grep '123' """
    cmd1 = shlex.split(cmd1)
    cmd2 = shlex.split(cmd2)
    proc1 = subprocess.Popen(cmd1, stdout=subprocess.PIPE)
    proc2 = subprocess.Popen(cmd2, stdin=proc1.stdout, stdout=subprocess.PIPE)
    proc1.stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
    return proc2.communicate()

def getProcInfo(procID):
    """ Get Process informationa about specific process """
    procOutInfo = {}
    procS = psutil.Process(int(procID))
    procOutInfo['CreateTime'] = procS.create_time()
    ioCounters = procS.io_counters()
    procOutInfo['IOCounters'] = {}
    procOutInfo['IOCounters']['ReadCount'] = ioCounters.read_count
    procOutInfo['IOCounters']['WriteCount'] = ioCounters.write_count
    procOutInfo['IOCounters']['ReadBytes'] = ioCounters.read_bytes
    procOutInfo['IOCounters']['WriteBytes'] = ioCounters.write_bytes
    procOutInfo['IOCounters']['ReadChars'] = ioCounters.read_chars
    procOutInfo['IOCounters']['WriteChars'] = ioCounters.write_chars
    procOutInfo['IOCounters']['NumFds'] = procS.num_fds()
    memInfo = procS.memory_full_info()
    procOutInfo['MemUseInfo'] = {}
    procOutInfo['MemUseInfo']['Rss'] = memInfo.rss
    procOutInfo['MemUseInfo']['Vms'] = memInfo.vms
    procOutInfo['MemUseInfo']['Shared'] = memInfo.shared
    procOutInfo['MemUseInfo']['Text'] = memInfo.text
    procOutInfo['MemUseInfo']['Lib'] = memInfo.lib
    procOutInfo['MemUseInfo']['Data'] = memInfo.data
    procOutInfo['MemUseInfo']['Dirty'] = memInfo.dirty
    procOutInfo['MemUseInfo']['Uss'] = memInfo.uss
    procOutInfo['MemUseInfo']['Pss'] = memInfo.pss
    procOutInfo['MemUseInfo']['Swap'] = memInfo.swap
    procOutInfo['Connections'] = {}
    for item in procS.connections():
        if item.status not in procOutInfo['Connections'].keys():
            procOutInfo['Connections'][item.status] = 0
        procOutInfo['Connections'][item.status] += 1
    return procOutInfo
