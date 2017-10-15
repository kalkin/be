# Copyright (C) 2009-2012 Chris Ball <cjb@laptop.org>
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

""" Bugs Everywhere - Show/Set bug due dates.

Usage:
    be due BUG_ID [DATE]

Arguments:
    BUG_ID          A bug id.
    DATE            A date or 'none' to unset due date

 If no DATE is specified, the bug's current due date is printed.
"""

from docopt import docopt

import libbe
import libbe.command
import libbe.command.util
import libbe.util.utility


DUE_TAG = 'DUE:'


class Due(libbe.command.Command):
    """ Set bug due dates

        >>> import sys
        >>> import libbe.bugdir
        >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
        >>> io = libbe.command.StringInputOutput()
        >>> io.stdout = sys.stdout
        >>> ui = libbe.command.UserInterface(io=io)
        >>> ui.storage_callbacks.set_storage(bd.storage)
        >>> cmd = Due(ui=ui)

        >>> ui.setup_command(cmd)

        >>> ret = cmd.run(['/a'])
        No due date assigned.
        >>> ret = cmd.run(['/a', 'Thu, 01 Jan 1970 00:00:00 +0000'])
        >>> ret = cmd.run(['/a'])
        Thu, 01 Jan 1970 00:00:00 +0000
        >>> ret = cmd.run(['/a', 'none'])
        >>> ret = cmd.run(['/a'])
        No due date assigned.
        >>> ui.cleanup()
        >>> bd.cleanup()
    """

    name = 'due'

    def run(self, args=None):
        args = args or []
        params = docopt(__doc__, argv=[Due.name] + args)
        bugdirs = self._get_bugdirs()  # pylint: disable=no-member
        _, bug, __ = (libbe.command.util.bugdir_bug_comment_from_user_id(
            bugdirs, params['BUG_ID']))

        if params['DATE'] is None:
            # pylint: disable=no-member
            due_time = _get_due(bug)
            if due_time is None:
                print >> self.stdout, 'No due date assigned.'
            else:
                print >> self.stdout, libbe.util.utility.time_to_str(due_time)
        else:
            if params['DATE'] == 'none':
                _remove_due(bug)
            else:
                due_time = libbe.util.utility.str_to_time(params['DATE'])
                _set_due(bug, due_time)


# internal helper functions

def _generate_due_string(time):
    return "%s%s" % (DUE_TAG, libbe.util.utility.time_to_str(time))


def _parse_due_string(string):
    assert string.startswith(DUE_TAG)
    return libbe.util.utility.str_to_time(string[len(DUE_TAG):])


def _get_due(bug):
    matched = []
    for line in bug.extra_strings:
        if line.startswith(DUE_TAG):
            matched.append(_parse_due_string(line))
    if not matched:
        return None
    if len(matched) > 1:
        raise Exception('Several due dates for %s?:\n  %s'
                        % (bug.uuid, '\n  '.join(matched)))
    return matched[0]


def _remove_due(bug):
    estrs = bug.extra_strings
    for due_str in [s for s in estrs if s.startswith(DUE_TAG)]:
        estrs.remove(due_str)
    bug.extra_strings = estrs  # reassign to notice change


def _set_due(bug, time):
    _remove_due(bug)
    estrs = bug.extra_strings
    estrs.append(_generate_due_string(time))
    bug.extra_strings = estrs  # reassign to notice change
