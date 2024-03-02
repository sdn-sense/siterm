#!/usr/bin/env python3
# pylint: disable=E1101
"""
    Base Debug Action class for stdout, stderr, jsonout

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2023/03/22
"""
from SiteRMLibs.MainUtilities import contentDB


class BaseDebugAction:
    """Base Debug Action class for stdout, stderr, jsonout and calling main function."""
    def __init__(self):
        self.workDir = self.config.get('general', 'privatedir') + "/SiteRM/background/"
        self.outfiles = {'stdout': self.workDir + f"/background-process-{self.backgConfig['id']}.stdout",
                         'stderr': self.workDir + f"/background-process-{self.backgConfig['id']}.stderr",
                         'jsonout': self.workDir + f"/background-process-{self.backgConfig['id']}.jsonout"}
        self.stdout = []
        self.stderr = []
        self.jsonout = {}
        self.diragent = contentDB()

    def refreshthread(self, *_args):
        """Call to refresh thread for this specific class and reset parameters"""
        self.logger.warning("NOT IMPLEMENTED call {self.backgConfig} to refresh thread")

    def __clean(self):
        """Clean all output"""
        self.stdout = []
        self.stderr = []
        self.jsonout = {}

    def __appendOutput(self, fname, content):
        """Append content to file"""
        with open(fname, 'a', encoding='utf-8') as fd:
            fd.write('\n' + content)
            for line in content:
                fd.write(line + '\n')

    def startwork(self):
        """Main work function"""
        try:
            self.main()
        except (ValueError, KeyError, OSError) as ex:
            self.stdout = []
            self.stderr = [str(ex).split('\n')]
            self.jsonout = {}
        self.__appendOutput(self.outfiles['stdout'], self.stdout)
        self.__appendOutput(self.outfiles['stderr'], self.stderr)
        self.diragent.dumpFileContentAsJson(self.outfiles['jsonout'], self.jsonout)
        self.__clean()
