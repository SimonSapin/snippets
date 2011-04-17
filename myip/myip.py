# coding: utf8
"""
    WSGI MyIP
    ~~~~~~~~~
    
    A trivial WSGI application that tells you what IP address
    you’re connecting from.
    
    Running as of this writing at http://myip.ep.io/ and http://ip.exyr.org/
    
    This was made just to try http://www.ep.io/ out.

    Author: Simon Sapin
    License: BSD

"""

import re
import socket


def application(environ, start_response):
    # ep.io uses IPv6, and a Gunicorn bug makes REMOTE_ADDR empty in that case.
    ip = environ['HTTP_X_FORWARDED_FOR']
    if re.match('::ffff:\d+\.\d+\.\d+.\d+', ip):
        # IPv4 in v6, eg ::ffff:127.0.0.1
        ip = ip[len('::ffff:'):]
    host = socket.getfqdn(ip)
    start_response('200 OK', [('Content-Type', 'text/html')])
    return ['Connecting from <strong>%(ip)s</strong> @ '
            '<strong>%(host)s</strong>.' % locals()]

