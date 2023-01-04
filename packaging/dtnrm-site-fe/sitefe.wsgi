""" Main WSGI application """
import traceback
from SiteFE.REST.app import Frontend

class Application():
    def __init__(self):
        self.wrapper = Frontend()

    def __call__(self, environ, start_fn):
        try:
            return self.wrapper.mainCall(environ, start_fn)
        except:
            print(traceback.print_exc())

application = Application()
