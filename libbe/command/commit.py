# Copyright (C) 2009-2012 Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
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

""" Bugs Everywhere - Commit the staged bug changes to the repository.

Usage:
    be commit (-b FILE|--body=FILE)
    be commit (-a|--allow-empty)
    be commit [SUMMARY]

Options:
    -h, --help              Show this screen.
    -b FILE, --body=FILE    Take the commit message from file
    -a, --allow-empty       Allow empty commit

Arguments:
    SUMMARY                 If no summary is specified, $EDITOR is started.
                            If summary is '-', it is read from stdin
                            If no $EDITOR and SUMMARY is specified, an error
                            will be raised.
"""

import sys

from docopt import docopt

import libbe
import libbe.bugdir
import libbe.command
import libbe.command.util
import libbe.storage
import libbe.ui.util.editor


class Commit (libbe.command.Command):
    """Commit the currently pending changes to the repository

        >>> import sys
        >>> import libbe.bugdir
        >>> bd = libbe.bugdir.SimpleBugDir(memory=False, versioned=True)
        >>> io = libbe.command.StringInputOutput()
        >>> io.stdout = sys.stdout
        >>> ui = libbe.command.UserInterface(io=io)
        >>> ui.storage_callbacks.set_storage(bd.storage)
        >>> cmd = Commit(ui=ui)

        >>> ui.setup_command(cmd)

        >>> bd.extra_strings = ['hi there']
        >>> bd.flush_reload()
        >>> cmd.run(['Making a commit']) # doctest: +ELLIPSIS
        Committed ...
        >>> ui.cleanup()
        >>> bd.cleanup()
    """
    name = 'commit'

    def run(self, args=None):
        args = args or []
        params = docopt(__doc__, argv=[Commit.name] + args)
        storage = self._get_storage()

        if params['SUMMARY'] == '-':  # read content from stdin
            content = sys.stdin.readline()
        elif params['SUMMARY']:
            content = params['SUMMARY']
        elif params['--body']:
            self._check_restricted_access(storage, params['--body'])
            content = libbe.util.encoding.get_file_contents(params['--body'],
                                                            decode=True)
        else:
            msg = 'Please enter your commit message above'
            body = libbe.ui.util.editor.editor_string(msg)

        lines = content.splitlines()
        summary = lines[0]
        body = '\n'.join(lines[1:]).strip() + '\n'

        try:
            revision = storage.commit(summary, body=body,
                                      allow_empty=params['--allow-empty'])
            print >> self.stdout, 'Committed %s' % revision
        except libbe.storage.EmptyCommit, e:
            print >> self.stdout, e
            return 1
