# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Marien Zwart <marien.zwart@gmail.com>
#                         Thomas Gerigk <tgerigk@gmx.de>
#                         Tim Guirgies <lt.infiltrator@gmail.com>
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

""" Bugs Everywhere - Show/Set a bug's severity level.

Usage:
    be severity SEVERITY BUG_ID...

 If no severity is specified, the current value is printed.  If
 a severity level is specified, it will be assigned to the bug.

 Severity levels are:
    %s

    You can override the list of allowed severities on a
    per-repository basis.
"""

from docopt import docopt

import libbe
import libbe.bug
import libbe.command
import libbe.command.util


class Severity(libbe.command.Command):
    """ Change a bug's severity level

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bd.storage)
    >>> cmd = Severity(ui=ui)

    >>> ui.setup_command(cmd)

    >>> bd.bug_from_uuid('a').severity
    'minor'
    >>> ret = cmd.run(['wishlist', '/a'])
    >>> bd.flush_reload()
    >>> bd.bug_from_uuid('a').severity
    u'wishlist'
    >>> ret = cmd.run(['none', '/a'])
    Traceback (most recent call last):
    UserError: Invalid severity level: none
    >>> ui.cleanup()
    >>> bd.cleanup()
    """
    name = 'severity'

    def run(self, args=None):
        args = args or []
        params = docopt(__doc__ % ('\n  '.join(self.severity_levels)),
                        argv=[Severity.name] + args)
        bugdirs = self._get_bugdirs()
        for bug_id in params['BUG_ID']:
            bug = (
                libbe.command.util.bugdir_bug_comment_from_user_id(
                    bugdirs, bug_id))[1]
            if bug.severity != params['SEVERITY']:
                try:
                    bug.severity = params['SEVERITY']
                except ValueError, e:
                    if e.name != 'severity':
                        raise e
                    msg = 'Invalid severity level: %s' % e.value
                    raise libbe.command.UserError(msg)
        return 0

    @property
    def severity_levels(self):
        ''' Return all severity levels '''
        try:  # See if there are any per-tree severity configurations
            bugdirs = self._get_bugdirs()
        except NotImplementedError:
            pass  # No tree, just show the defaults
        longest_severity_len = max([len(s) for s in libbe.bug.severity_values])
        severity_levels = []
        for severity in libbe.bug.severity_values:
            description = libbe.bug.severity_description[severity]
            sev = '%*s : %s' % (longest_severity_len, severity, description)
            severity_levels.append(sev)
        return severity_levels
