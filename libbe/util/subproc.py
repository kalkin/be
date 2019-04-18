# -*- coding: utf-8 -*-
# Copyright (C) 2009-2019 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
#                         Chris Ball <cjb@laptop.org>
#                         Matěj Cepl <mcepl@redhat.com>
#                         W. Trevor King <wking@tremily.us>
#
# This file is part of Bugs Everywhere.
#
# Bugs Everywhere is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option) any
# later version.
#
# Bugs Everywhere is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# Bugs Everywhere.  If not, see <http://www.gnu.org/licenses/>.

"""
Functions for running external commands in subprocesses.
"""

from subprocess import Popen, PIPE
import sys
import types

import libbe
from libbe.util.encoding import get_encoding

_MSWINDOWS = sys.platform == 'win32'
_POSIX = not _MSWINDOWS


class CommandError(Exception):
    def __init__(self, command, status, stdout=None, stderr=None):
        strerror = ['Command failed (%d):\n  %s\n' % (status, stderr),
                    'while executing\n  %s' % str(command)]
        Exception.__init__(self, '\n'.join(strerror))
        self.command = command
        self.status = status
        self.stdout = stdout
        self.stderr = stderr


def invoke(args, stdin=None, stdout=PIPE, stderr=PIPE, expect=(0,),
           cwd=None, shell=None, unicode_output=True, encoding=None, **kwargs):
    """
        :param expect: should be a tuple of allowed exit codes.
        :param cwd: should be the directory from which the command will be
                    executed.
        :param unicode_output: When `True`, convert stdout and stdin strings to
                               unicode before returing them.
    """
    if cwd is None:
        cwd = '.'
    if isinstance(shell, types.StringTypes):
        list_args = ' '.split(args)  # sloppy, but just for logging
        str_args = args
    else:
        list_args = args
        str_args = ' '.join(args)  # sloppy, but just for logging
    libbe.LOG.debug('%s$ %s', cwd, str_args)

    try:
        if _POSIX:
            if shell is None:
                shell = False
            popen = Popen(args, stdin=PIPE, stdout=stdout, stderr=stderr,
                          shell=shell, cwd=cwd, **kwargs)
        else:
            assert _MSWINDOWS, 'invalid platform'
            if shell is None:
                shell = True
            # win32 don't have os.execvp() so have to run command in a shell
            popen = Popen(args, stdin=PIPE, stdout=stdout, stderr=stderr,
                          shell=shell, cwd=cwd, **kwargs)
    except OSError, exc:
        raise CommandError(list_args, status=exc.args[0], stderr=exc)

    stdout, stderr = popen.communicate(input=stdin)
    status = popen.wait()

    if unicode_output:
        if encoding is None:
            encoding = get_encoding()
        if stdout is not None:
            stdout = unicode(stdout, encoding)
        if stderr is not None:
            stderr = unicode(stderr, encoding)
        libbe.LOG.debug(u'%s\n%s%s', status, stdout, stderr)
    else:
        libbe.LOG.debug('%s\n%s%s', status, stdout, stderr)

    if status not in expect:
        raise CommandError(list_args, status, stdout, stderr)

    return status, stdout, stderr
