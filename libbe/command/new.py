# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Andrew Cooper <andrew.cooper@hkcreations.org>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Niall Douglas (s_sourceforge@nedprod.com) <spam@spamtrap.com>
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

""" Bugs Everywhere - Create a new bug, with a new ID.

Usage:
    be new [-a ASSIGNEE] [-b ID] [-f] [-c CREATOR] [-r REPORTER] [-s SEVERITY] [-t STATUS] SUMMARY

Options:
    -a NAME, --assigned=NAME            The developer in charge of the bug
    -b ID, --bugdir=ID                  Short bugdir UUID for the new bug.  You
                                        only need to set this if you have
                                        multiple bugdirs in your repository.
    -c NAME, --creator=NAME             The user who created the bug
    -f, --full-uuid                     Print the full UUID for the new bug
    -r NAME, --reporter=NAME            The user who reported the bug
    -s SEVERITY, --severity=SEVERITY    The bug's severity
    -t STATUS, --status=STATUS          The bug's status level


The SUMMARY specified on the commandline is a string (only one line) that
describes the bug briefly or "-", in which case the string will be read from
stdin.
"""

import libbe
import libbe.command
import libbe.command.util

from docopt import docopt


class New(libbe.command.Command):
    """
        Create a new bug

        >>> import os
        >>> import sys
        >>> import time
        >>> import libbe.bugdir
        >>> import libbe.util.id
        >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
        >>> io = libbe.command.StringInputOutput()
        >>> io.stdout = sys.stdout
        >>> ui = libbe.command.UserInterface(io=io)
        >>> ui.storage_callbacks.set_storage(bd.storage)
        >>> cmd = New()

        >>> ui.setup_command(cmd)

        >>> uuid_gen = libbe.util.id.uuid_gen
        >>> libbe.util.id.uuid_gen = lambda: 'X'
        >>> ui._user_id = u'Fran\\xe7ois'
        >>> ret = cmd.run(['--assigned=none', 'this is a test',])
        Created bug with ID abc/X
        >>> libbe.util.id.uuid_gen = uuid_gen
        >>> bd.flush_reload()
        >>> bug = bd.bug_from_uuid('X')
        >>> print bug.summary
        this is a test
        >>> bug.creator
        u'Fran\\xe7ois'
        >>> bug.reporter
        u'Fran\\xe7ois'
        >>> bug.time <= int(time.time())
        True
        >>> print bug.severity
        minor
        >>> print bug.status
        open
        >>> print bug.assigned
        None
        >>> ui.cleanup()
        >>> bd.cleanup()
    """
    name = 'new'

    def run(self, args=None):
        # pylint: disable=too-many-branches
        args = args or []
        params = docopt(__doc__, argv=[New.name] + args)
        if params['SUMMARY'] == '-':  # read summary from stdin
            # pylint: disable=no-member
            summary = self.stdin.readline()
        else:
            summary = params['SUMMARY']
        storage = self._get_storage()  # pylint: disable=no-member
        bugdirs = self._get_bugdirs()  # pylint: disable=no-member
        if params['--bugdir']:
            bugdir = bugdirs[params['--bugdir']]
        elif len(bugdirs) == 1:
            bugdir = bugdirs.values()[0]
        else:
            raise libbe.command.UserError('Ambiguous bugdir %s'
                                          % sorted(bugdirs.values()))
        storage.writeable = False
        bug = bugdir.new_bug(summary=summary.strip())
        if params['--creator'] is not None:
            bug.creator = params['--creator']
        else:
            bug.creator = self._get_user_id()  # pylint: disable=no-member
        if params['--reporter'] is not None:
            bug.reporter = params['--reporter']
        else:
            bug.reporter = bug.creator
        if params['--assigned'] is not None:
            bug.assigned = parse_assigned(self, params['--assigned'])
        if params['--status'] is not None:
            bug.status = params['--status']
        if params['--severity'] is not None:
            bug.severity = params['--severity']
        storage.writeable = True
        bug.save()
        if params['--full-uuid']:
            bug_id = bug.id.long_user()
        else:
            bug_id = bug.id.user()
        # pylint: disable=no-member
        self.stdout.write('Created bug with ID %s\n' % (bug_id))
        return 0


def parse_assigned(command, assigned):
    """Standard processing for the 'assigned' Argument.
    """
    if assigned == 'none':
        assigned = None
    elif assigned == '-':
        assigned = command._get_user_id()  # pylint: disable=protected-access
    return assigned
