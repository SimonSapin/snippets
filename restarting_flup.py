#!/usr/bin/env python
"""

This is the same as the usual .fcgi file[1] for using FastCGI with flup,
except that this one terminates itself when the .fcgi file’s modification
date changes. Assuming you have something[2] that restarts FastCGI processes
as needed (which you should anyway), this effectively allows you to reload
the application by just `touch`ing one file.

[1] http://flask.pocoo.org/docs/deploying/fastcgi/
[2] Something like Circus, Supervisord, or Lighttpd with `bin-path` configured.

"""

from os.path import getmtime
from flup.server.fcgi import WSGIServer


START_TIME = getmtime(__file__)


class RestartingServer(WSGIServer):
    def _mainloopPeriodic(self):
        WSGIServer._mainloopPeriodic(self)
        if getmtime(__file__) != START_TIME:
            self._keepGoing = False


from YOUR_APPLICATION import app
RestartingServer(app).run()
