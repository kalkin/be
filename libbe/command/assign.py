# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Marien Zwart <marien.zwart@gmail.com>
#                         Robert Lehmann <mail@robertlehmann.de>
#                         Thomas Gerigk <tgerigk@gmx.de>
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

""" Bugs Everywhere - Assign an idividual or group to fix a bug

Usage:
    be assign ASSIGNEE BUG-ID...
    be assign -h | --help

Arguments:
    ASSIGNEE    Assign a person to fix a bug.
    BUG-ID      A bug id i.e. /abc

Options:
    -h, --help  Show this screen.

Assigneds should be the person's Bugs Everywhere identity,
the same string that appears in Creator fields.
"""

from docopt import docopt

import libbe
import libbe.command
from libbe.command.util import bugdir_bug_comment_from_user_id


class Assign (libbe.command.Command):
    u"""Assign an individual or group to fix a bug

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bd.storage)
    >>> cmd = Assign(ui=ui)

    >>> ui.setup_command(cmd)

    >>> bd.bug_from_uuid('a').assigned is None
    True
    >>> ui._user_id = u'Fran\xe7ois'
    >>> ret = cmd.run(['-', '/a'])
    >>> bd.flush_reload()
    >>> bd.bug_from_uuid('a').assigned
    u'Fran\\xe7ois'

    >>> ret = cmd.run(['someone', '/a', '/b'])
    >>> bd.flush_reload()
    >>> bd.bug_from_uuid('a').assigned
    u'someone'
    >>> bd.bug_from_uuid('b').assigned
    u'someone'

    >>> ret = cmd.run(['none', '/a'])
    >>> bd.flush_reload()
    >>> bd.bug_from_uuid('a').assigned is None
    True
    >>> ui.cleanup()
    >>> bd.cleanup()
    """
    name = 'assign'

    def run(self, args=None):
        args = args or []
        params = docopt(__doc__, argv=[Assign.name] + args)
        assigned = params['ASSIGNEE']
        if assigned == 'none':
            assigned = None
        elif assigned == '-':
            assigned = self._get_user_id()
        bugdirs = self._get_bugdirs()
        for bug_id in params['BUG-ID']:
            _, bug, __ = (bugdir_bug_comment_from_user_id(bugdirs, bug_id))
            if bug.assigned != assigned:
                bug.assigned = assigned
                if bug.status == 'open':
                    bug.status = 'assigned'
        return 0
