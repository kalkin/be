# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
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

""" Bugs Everywhere - Compare bug reports with older revision.

Usage:
    be diff [-u] [-s ID_TYPE] [REVISION]
    be diff [-u] [-s ID_TYPE] REPO [-- REVISION]

Options:
    -h, --help                        Show this screen.
    -u, --uuids                       Only print the bug ids.
    -s ID_TYPE, --subscribe=ID_TYPE   Only print changes matching ID_TYPE.
                                      You can specify multiple ID_TYPEs as a
                                      comma-separated list.
                                      See `be subscribe --help` for
                                      descriptions of ID and TYPE.

 When using '-u' or '--uuids' option, the output can be piped to 'be show'
"""

from docopt import docopt

import libbe
import libbe.bugdir
import libbe.bug
import libbe.command
import libbe.command.util
import libbe.storage

import libbe.diff


class Diff(libbe.command.Command):
    # pylint: disable=missing-docstring
    __doc__ = """ Compare bug reports with older tree

        >>> import sys
        >>> import libbe.bugdir
        >>> bd = libbe.bugdir.SimpleBugDir(memory=False, versioned=True)
        >>> io = libbe.command.StringInputOutput()
        >>> io.stdout = sys.stdout
        >>> ui = libbe.command.UserInterface(io=io)
        >>> ui.storage_callbacks.set_storage(bd.storage)
        >>> cmd = Diff()

        >>> ui.setup_command(cmd)

        >>> original = bd.storage.commit('Original status')
        >>> bug = bd.bug_from_uuid('a')
        >>> bug.status = 'closed'
        >>> changed = bd.storage.commit('Closed bug a')
        >>> cmd.run([original])
        Modified bugs:
          abc/a:cm: Bug A
            Changed bug settings:
              status: open -> closed
        >>> cmd.run(['--subscribe=%(bugdir_id)s:mod', '--uuids', original])
        a
        >>> bd.storage.versioned = False
        >>> cmd.run([original])
        Traceback (most recent call last):
        ...
        UserError: This repository is not revision-controlled.
        >>> ui.cleanup()
        >>> bd.cleanup()
    """ % {'bugdir_id': libbe.diff.BUGDIR_ID}

    name = 'diff'

    def run(self, args=None):
        args = args or []
        params = docopt(__doc__, argv=[Diff.name] + args)

        try:
            subscriptions = libbe.diff.subscriptions_from_string(
                params['--subscribe'])
        except ValueError as exc:
            raise libbe.command.UserError(exc)

        bugdirs = self._get_bugdirs()  # pylint: disable=no-member
        for bugdir in sorted(bugdirs.values()):
            self.diff(bugdir, subscriptions, params['REPO'],
                      params['REVISION'], params['--uuids'])

    # pylint: disable=too-many-arguments
    def diff(self, bugdir, subscriptions, repo=None, revision=None,
             uuids=False):
        if repo is None:
            if not bugdir.storage.versioned:
                raise libbe.command.UserError(
                    'This repository is not revision-controlled.')

            if revision is None:  # get the most recent revision
                revision = bugdir.storage.revision_id(-1)
            old_bd = libbe.bugdir.RevisionedBugDir(bugdir, revision)
        else:
            old_storage = libbe.storage.get_storage(repo)
            old_storage.connect()
            # pylint: disable=unexpected-keyword-arg
            old_bd_current = libbe.bugdir.BugDir(old_storage, from_disk=True)
            if revision is None:  # use the current working state
                old_bd = old_bd_current
            elif not old_bd_current.storage.versioned:
                msg = "Repo '%s' is not revision-controlled."
                raise libbe.command.UserError(msg % bugdir.storage.repo)
            else:
                old_bd = libbe.bugdir.RevisionedBugDir(old_bd_current,
                                                       revision)

        tree = libbe.diff.Diff(old_bd, bugdir).report_tree(subscriptions)

        if uuids:
            uuids = []
            bugs = tree.child_by_path('/bugs')
            for bug_type in bugs:
                uuids.extend([bug.name for bug in bug_type])
            print >> self.stdout, '\n'.join(uuids)  # pylint: disable=no-member
        else:
            rep = tree.report_string()
            if rep is not None:
                print >> self.stdout, rep  # pylint: disable=no-member
        return 0
