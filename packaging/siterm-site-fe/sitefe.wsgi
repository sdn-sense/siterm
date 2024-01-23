""" Main WSGI application """
import os
import traceback
from SiteFE.REST.app import Frontend

class Application():
    """Application class for WSGI"""
    def __init__(self):
        self.threadcalls = {}

    def __getwrapper(self, environ):
        """ Get the wrapper for the current thread """
        thread_id = environ.get('mod_wsgi.thread_id', 0)
        os_pid = os.getpid()
        req_id = f"{thread_id}-{os_pid}"
        if req_id not in self.threadcalls:
            self.threadcalls[req_id] = Frontend()
        return self.threadcalls[req_id]

    def __call__(self, environ, start_fn):
        """ WSGI call """
        try:
            wrapper = self.__getwrapper(environ)
            return wrapper.mainCall(environ, start_fn)
        except:
            print(traceback.print_exc())
            raise

application = Application()
