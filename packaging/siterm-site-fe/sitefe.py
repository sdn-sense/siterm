""" Main WSGI application """

import os
import tracemalloc
import threading
import traceback
import time
from uvicorn.middleware.wsgi import WSGIMiddleware
from SiteFE.REST.app import Frontend


class Application:
    """Application class for WSGI"""

    def __init__(self):
        self.threadcalls = {}
        # Start tracemalloc if debug is set.
        if os.getenv("SITERM_MEMORY_DEBUG"):
            tracemalloc.start()
            threading.Thread(target=self.memLogger, daemon=True).start()

    def memLogger(self):
        """Background thread to log memory snapshots periodically"""
        while True:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics("lineno")[:20]

            with open(
                f"/var/log/httpd/memory_snapshot_{os.getpid()}.log",
                "a",
                encoding="utf-8",
            ) as fd:
                fd.write(f"Memory usage: {tracemalloc.get_traced_memory()}\n")
                fd.write(
                    f"=== Memory snapshot at {time.ctime()} PID {os.getpid()} ===\n"
                )
                for stat in top_stats:
                    fd.write(str(stat) + "\n")
                fd.write("\n\n")
                fd.write("=== End of snapshot ===\n")
                fd.write("======\n\n")
            time.sleep(60)

    def __getwrapper(self, environ):
        """Get the wrapper for the current thread"""
        thread_id = environ.get("mod_wsgi.thread_id", 0)
        os_pid = os.getpid()
        req_id = f"{thread_id}-{os_pid}"
        if req_id not in self.threadcalls:
            self.threadcalls[req_id] = Frontend()
        return self.threadcalls[req_id]

    def __call__(self, environ, start_fn):
        """WSGI call"""
        try:
            wrapper = self.__getwrapper(environ)
            return wrapper.mainCall(environ, start_fn)
        except:
            print(traceback.print_exc())
            raise


application = WSGIMiddleware(Application())
