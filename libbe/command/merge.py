# Copyright (C) 2008-2012 Chris Ball <cjb@laptop.org>
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

""" Bugs Everywhere - Merge bugs.

Usage:
    be merge BUG_A BUG_B

 The second bug (B) is merged into the first (A).  This adds merge comments to
 both bugs, closes B, and appends B's comment tree to A's merge comment.
"""

import copy

from docopt import docopt

import libbe
import libbe.command
import libbe.command.util


class Merge(libbe.command.Command):
    """
        Merge duplicate bugs

    >>> import sys
    >>> import libbe.bugdir
    >>> import libbe.comment
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bd.storage)
    >>> cmd = Merge(ui=ui)

    >>> ui.setup_command(cmd)

    >>> a = bd.bug_from_uuid('a')
    >>> a.comment_root.time = 0
    >>> dummy = a.new_comment('Testing')
    >>> dummy.time = 1
    >>> dummy = dummy.new_reply('Testing...')
    >>> dummy.time = 2
    >>> b = bd.bug_from_uuid('b')
    >>> b.status = 'open'
    >>> b.comment_root.time = 0
    >>> dummy = b.new_comment('1 2')
    >>> dummy.time = 1
    >>> dummy = dummy.new_reply('1 2 3 4')
    >>> dummy.time = 2

    >>> ret = cmd.run(['/a', '/b'])
    Merged bugs #abc/a# and #abc/b#
    >>> bd.flush_reload()
    >>> a = bd.bug_from_uuid('a')
    >>> a.load_comments()
    >>> a_comments = sorted([c for c in a.comments()],
    ...                     cmp=libbe.comment.cmp_time)
    >>> mergeA = a_comments[0]
    >>> mergeA.time = 3
    >>> print a.string(show_comments=True)
    ... # doctest: +ELLIPSIS, +REPORT_UDIFF
              ID : a
      Short name : abc/a
        Severity : minor
          Status : open
        Assigned : 
        Reporter : 
         Creator : John Doe <jdoe@example.com>
         Created : ...
    Bug A
    --------- Comment ---------
    Name: abc/a/...
    From: ...
    Date: ...
    <BLANKLINE>
    Testing
      --------- Comment ---------
      Name: abc/a/...
      From: ...
      Date: ...
    <BLANKLINE>
      Testing...
    --------- Comment ---------
    Name: abc/a/...
    From: ...
    Date: ...
    <BLANKLINE>
    Merged from bug #abc/b#
      --------- Comment ---------
      Name: abc/a/...
      From: ...
      Date: ...
    <BLANKLINE>
      1 2
        --------- Comment ---------
        Name: abc/a/...
        From: ...
        Date: ...
    <BLANKLINE>
        1 2 3 4
    >>> b = bd.bug_from_uuid('b')
    >>> b.load_comments()
    >>> b_comments = sorted([c for c in b.comments()],
    ...                     libbe.comment.cmp_time)
    >>> mergeB = b_comments[0]
    >>> mergeB.time = 3
    >>> print b.string(show_comments=True)
    ... # doctest: +ELLIPSIS, +REPORT_UDIFF
              ID : b
      Short name : abc/b
        Severity : minor
          Status : closed
        Assigned : 
        Reporter : 
         Creator : Jane Doe <jdoe@example.com>
         Created : ...
    Bug B
    --------- Comment ---------
    Name: abc/b/...
    From: ...
    Date: ...
    <BLANKLINE>
    1 2
      --------- Comment ---------
      Name: abc/b/...
      From: ...
      Date: ...
    <BLANKLINE>
      1 2 3 4
    --------- Comment ---------
    Name: abc/b/...
    From: ...
    Date: ...
    <BLANKLINE>
    Merged into bug #abc/a#
    >>> print b.status
    closed
    >>> ui.cleanup()
    >>> bd.cleanup()
    """
    name = 'merge'

    def run(self, args=None):
        args = args or []
        params = docopt(__doc__, argv=[Merge.name] + args)
        storage = self._get_storage()  # pylint: disable=no-member
        bugdirs = self._get_bugdirs()  # pylint: disable=no-member
        _, bug_a, comment = (
            libbe.command.util.bugdir_bug_comment_from_user_id(
                bugdirs, params['BUG_A']))
        bug_a.load_comments()
        _, bug_b, dummy_comment = (
            libbe.command.util.bugdir_bug_comment_from_user_id(
                bugdirs, params['BUG_B']))
        bug_b.load_comments()
        merge_a = bug_a.new_comment('Merged from bug #%s#'
                                    % bug_b.id.long_user())
        new_comm_tree = copy.deepcopy(bug_b.comment_root)
        for comment in new_comm_tree.traverse():  # all descendant comments
            comment.bug = bug_a
            # uuids must be unique in storage
            if comment.alt_id is None:
                comment.storage = None
                comment.alt_id = comment.uuid
                comment.storage = storage
            comment.uuid = libbe.util.id.uuid_gen()
            comment.save()  # force onto disk under bug_a

        for comment in new_comm_tree:  # just the child comments
            merge_a.add_reply(comment, allow_time_inversion=True)
        bug_b.new_comment('Merged into bug #%s#' % bug_a.id.long_user())
        bug_b.status = 'closed'
        # pylint: disable=no-member
        print >> self.stdout, 'Merged bugs #%s# and #%s#' \
            % (bug_a.id.user(), bug_b.id.user())
        return 0
