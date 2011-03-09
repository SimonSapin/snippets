# coding: utf8
"""
    WSGI MyIP
    ~~~~~~~~~
    
    A trivial WSGI application that tells you what IP address
    you’re connecting from.
    
    Running as of this writing at http://myip.ep.io/ and http://ip.exyr.org/
    
    This was made just to try http://www.ep.io/ out. They use IPv6 so
    IPv4 addresses may look like ::ffff:127.0.0.1

    Author: Simon Sapin
    License: BSD

"""

def application(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain')])
    # ep.io uses IPv6, and a Gunicorn bug makes REMOTE_ADDR empty in that case.
    return [environ['HTTP_X_FORWARDED_FOR']]

