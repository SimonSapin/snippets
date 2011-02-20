#!/usr/bin/env python
"""
    Run a command on multiple servers via SSH, each in a GNOME Terminal tab.    
    See http://exyr.org/2011/gnome-terminal-tabs/
"""

import subprocess

command = 'sudo aptitude update && sudo aptitude safe-upgrade'
terminal = ['gnome-terminal']
for host in ('cartonbox', 'hako'):
    terminal.extend(['--tab', '-e', '''
        bash -c '
            echo "%(host)s$ %(command)s"
            ssh -t %(host)s "%(command)s"
            read
        '
    ''' % locals()])
subprocess.call(terminal)
