#!/usr/bin/env python3
"""Remote connection via ssh to switches (for config retrieval, vlan, routing assignments)

Copyright 2021 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title                   : dtnrm
Author                  : Justas Balcas
Email                   : justas.balcas (at) cern.ch
@Copyright              : Copyright (C) 2021 California Institute of Technology
Date                    : 2021/11/08
"""
import select
import time
import paramiko

# TODO: Support SSH Key authentication.

class RemoteConn():
    """ Remote Connection open and command sender class"""
    def __init__(self, connDetails, logger, cmds):
        self.conn = connDetails
        self.cmds = cmds
        self.logger = logger
        self.remoteConnPre = None
        self.remoteConn = None
        self._connect()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._terminate()

    def _connect(self):
        """ Open Connection to Remote Instance """
        self.logger.debug('New OpenSSH Connection to %s', self.conn['ipaddr'])
        self.remoteConnPre = paramiko.SSHClient()
        self.remoteConnPre.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.remoteConnPre.connect(self.conn['ipaddr'], username = self.conn['username'],
                                       password = self.conn['passwords']['ssh'], look_for_keys=False,
                                       allow_agent=False)
            self.remoteConn = self.remoteConnPre.invoke_shell()
        except paramiko.ssh_exception.AuthenticationException as ex:
            msg = "Failed to authenticate to %s with %s. Exception %s" % (self.conn['ipaddr'], self.conn['username'], ex)
            self.logger.debug(msg)
        except paramiko.ssh_exception.NoValidConnectionsError as ex:
            msg = "No valid connection to this host %s. Exception %s" % (self.conn['ipaddr'], ex)
            self.logger.debug(msg)
        except:
            msg = 'Received Error. Will try to change look_for_keys value and ssh again'
            self.logger.debug(msg)
            paramiko.Transport._preferred_ciphers = ('3des-cbc',)
            self.remoteConnPre.connect(self.conn['ipaddr'], username = self.conn['username'],
                                       password = self.conn['passwords']['ssh'], look_for_keys=True,
                                        allow_agent=False)
            self.remoteConn = self.remoteConnPre.invoke_shell()
        # Enable terminal
        self.sendCommand("%s%s" % (self.cmds.CMD_ENABLE, self.cmds.LT))
        if 'enable' in self.conn['passwords'] and self.conn['passwords']['enable']:
            self.sendCommand("%s\n" % self.conn['passwords']['enable'])
        self.sendCommand("%s" % self.cmds.LT)
        self.sendCommand("%s%s" % (self.cmds.CMD_TLENGTH, self.cmds.LT))

    def _terminate(self):
        """ Terminate connection """
        self.logger.debug('Called connection terminate for %s', self.conn['ipaddr'])
        if self.remoteConn and not self.remoteConn.closed:
            self.remoteConn.close()
            self.remoteConn = None
        if self.remoteConnPre:
            self.remoteConnPre.close()
            self.remoteConnPre = None

    def dopaging(self, inLine):
        """ Check if paging is needed """
        if inLine.startswith(bytes(self.cmds.PAGGING_LINE, 'utf-8')):
            return True
        return False

    def sendCommand(self, cmd):
        """ Send command to remote Instance """
        self.logger.debug('Execute cmd "%s" for (%s)', cmd, self.conn['ipaddr'])
        if not self.remoteConn or not self.remoteConnPre:
            self._terminate()  # Do full clean-up and connection close
            self._connect()  # Reconnect
        if isinstance(cmd, bytes):
            cmd = cmd.decode('utf-8')
        self.remoteConn.send(cmd)
        time.sleep(self.conn['timeout']*3) # It is getting output in chunks... we need to sleep a bit
        # read stdout/stderr in order to prevent read block hangs
        stdout = [] + self.remoteConn.recv(len(self.remoteConn.in_buffer)).split(b'\r\n')
        # keep stat of not received new lines... if reaches 2 times, break
        noNewLines = 0
        lineCount = 0
        # chunk read to prevent stalls
        while not self.remoteConn.closed:
            readq, _, _ = select.select([self.remoteConn], [], [], self.conn['timeout'])
            for rlist in readq:
                if rlist.recv_ready():
                    stdout += self.remoteConn.recv(len(rlist.in_buffer)).split(b'\n')
                if rlist.recv_stderr_ready():
                    # make sure to read stderr to prevent stall
                    print(self.remoteConn.recv_stderr(len(rlist.in_stderr_buffer)))
            if self.remoteConn.exit_status_ready() and \
               not self.remoteConn.recv_stderr_ready() and \
               not self.remoteConn.recv_ready():
                break    # exit as remote side finished and our buffers are empty
            if lineCount != len(stdout):
                lineCount = len(stdout)
            else:
                lastLine = stdout[-1:][0]
                if self.dopaging(lastLine):
                    stdout = stdout[:-1]
                    self.remoteConn.send(' ')
                    time.sleep(self.conn['timeout'])
                    continue
                noNewLines += 1
                time.sleep(self.conn['timeout'])
            if noNewLines >= 2:
                break
        return stdout
