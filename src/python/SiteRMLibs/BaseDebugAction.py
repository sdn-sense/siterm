#!/usr/bin/env python3
# pylint: disable=E1101
"""
    Base Debug Action class for stdout, stderr, jsonout

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2023/03/22
"""
from SiteRMLibs.MainUtilities import contentDB
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.CustomExceptions import BackgroundException

class CustomWriter:
    """Custom Writer class for writing to file"""
    def __init__(self, filename, mode='w', buffering=-1, encoding=None, errors=None, newline='\n', closefd=True, opener=None):
        self.fd = open(filename, mode, buffering, encoding, errors, newline, closefd, opener)

    def wn(self, inline):
        """Write to file with new line at end"""
        self.fd.write(inline)
        if not inline.endswith('\n'):
            self.fd.write('\n')

    def close(self):
        """Close the file"""
        self.fd.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.fd.close()

class BaseDebugAction:
    """Base Debug Action class for stdout, stderr, jsonout and calling main function."""
    def __init__(self):
        # Logger is used for internal stuff inside SiteRM logging;
        # self.processout is used for writing and reporting back to FE and clients;
        # self.jsonout is used for storing data and dumping it to file - and will be dumped to clients;
        # stdout and stderr - are passed to subprocess if any.
        self.logger = getLoggingObject(config=self.config,
                                       service=self.service,
                                       logOutName=f"api-{self.backgConfig.get('id', 0)}.log")
        self.logger.info(f"====== {self.service} Start Work. Config: {self.backgConfig}")
        self.workDir = self.config.get('general', 'privatedir') + "/SiteRM/background/"
        self.outfiles = {'stdout': self.workDir + f"/background-process-{self.backgConfig['id']}.stdout",
                         'stderr': self.workDir + f"/background-process-{self.backgConfig['id']}.stderr",
                         'processout': self.workDir + f"/background-process-{self.backgConfig['id']}.process",
                         'jsonout': self.workDir + f"/background-process-{self.backgConfig['id']}.jsonout"}
        self.processout = CustomWriter(self.outfiles['processout'], 'w', encoding='utf-8')
        self.jsonout = {}
        self.diragent = contentDB()
        self.flightcheck()

    def flightcheck(self):
        """Check if all required parameters are present"""
        if not self.requestdict:
            self.processout.wn(f"No request dictionary found in request {self.backgConfig}")
            raise BackgroundException(f"No requestdict found in request {self.backgConfig}")

    def refreshthread(self, *_args):
        """Call to refresh thread for this specific class and reset parameters"""
        self.logger.warning(f"NOT IMPLEMENTED call {self.backgConfig} to refresh thread")

    def startwork(self):
        """Main work function"""
        try:
            self.main()
            self.diragent.dumpFileContentAsJson(self.outfiles['jsonout'], self.jsonout)
        except (ValueError, KeyError, OSError, BackgroundException) as ex:
            self.processout.wn(str(ex))
            self.diragent.dumpFileContentAsJson(self.outfiles['jsonout'], self.jsonout)
        finally:
            self.processout.wn(f"====== {self.service} Finish Work. Config: {self.backgConfig}")
            self.processout.close()
            self.logger.info(f"====== {self.service} Finish Work. Config: {self.backgConfig}")
