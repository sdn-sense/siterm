#!/usr/bin/python
"""
Chown database file automatically. This is needed because we do
our new site deployments automatically via git configurations.
Copyright 2020 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title             : siterm
Author            : Justas Balcas
Email             : justas.balcas (at) cern.ch
@Copyright        : Copyright (C) 2020 California Institute of Technology
Date            : 2020/07/28
"""
import os
import pwd
import grp
from DTNRMLibs.MainUtilities import getGitConfig

DEFAULT_USERNAME = 'apache'
DEFAULT_GROUP = 'apache'

DEFAULT_GID = grp.getgrnam(DEFAULT_GROUP).gr_gid
DEFAULT_UID = pwd.getpwnam(DEFAULT_USERNAME).pw_uid

if __name__ == "__main__":
    gitConf = getGitConfig()
    for sitename in gitConf['MAIN']['general']['sites']:
        dbname = '/opt/config/%s/sqlite.db' % sitename
        if os.path.isfile(dbname):
            fstat = os.stat(dbname)
            username = pwd.getpwuid(fstat.st_uid).pw_name
            group = grp.getgrgid(fstat.st_gid).gr_name
            if username != DEFAULT_USERNAME or group != DEFAULT_GROUP:
                print 'Chowning database file. New Site? %s' % sitename
                os.chown(dbname, DEFAULT_UID, DEFAULT_GID)

