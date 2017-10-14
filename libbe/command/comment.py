# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Niall Douglas (s_sourceforge@nedprod.com) <spam@spamtrap.com>
#                         Robert Lehmann <mail@robertlehmann.de>
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

""" Bugs Everywhere - Add a comment to a bug.

Usage:
    be comment [-a AUTHOR|--author=AUTHOR] [--alt-id=ID] [-c MIME|--content-type=MIME] [-f|--full-uuid] ID [COMMENT]

Options:
    -h, --help                      Show this screen.
    -a AUTHOR, --author=AUTHOR      Set the comment author.
    -c MIME, --content-type=MIME    Set the comment content-type.
    -f, --full-uuid                 Print the full UUID for the new bug.

Arguments:
    ID                          The bug or comment id you want to comment on.
    COMMENT                     If no comment is specified, $EDITOR is started.
                                If comment is '-', it is read from stdin
                                If no $EDITOR and COMMENT is specified, an error
                                will be raised.
"""


import os
import sys

from docopt import docopt

import libbe
import libbe.command
from libbe.command.util import bugdir_bug_comment_from_user_id
import libbe.comment
import libbe.ui.util.editor
import libbe.util.id


class Comment (libbe.command.Command):
    """ Add a comment to a bug.

        >>> import time
        >>> import libbe.bugdir
        >>> import libbe.util.id
        >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
        >>> io = libbe.command.StringInputOutput()
        >>> io.stdout = sys.stdout
        >>> ui = libbe.command.UserInterface(io=io)
        >>> ui.storage_callbacks.set_storage(bd.storage)
        >>> cmd = Comment(ui=ui)

        >>> ui.setup_command(cmd)

        >>> uuid_gen = libbe.util.id.uuid_gen
        >>> libbe.util.id.uuid_gen = lambda: 'X'
        >>> ret = cmd.run(['-a', u'Fran\\xe7ois', '/a', 'This is a comment about a'])
        Created comment with ID abc/a/X
        >>> libbe.util.id.uuid_gen = uuid_gen
        >>> bd.flush_reload()
        >>> bug = bd.bug_from_uuid('a')
        >>> bug.load_comments(load_full=False)
        >>> comment = bug.comment_root[0]
        >>> comment.id.storage() == comment.uuid
        True
        >>> print comment.body
        This is a comment about a
        <BLANKLINE>
        >>> comment.author
        u'Fran\\xe7ois'
        >>> comment.time <= int(time.time())
        True
        >>> comment.in_reply_to is None
        True

        >>> if 'EDITOR' in os.environ:
        ...     del os.environ['EDITOR']
        >>> if 'VISUAL' in os.environ:
        ...     del os.environ['VISUAL']
        >>> ret = cmd.run(['-a', u'Frank', '/b'])
        Traceback (most recent call last):
        UserError: No comment supplied, and EDITOR not specified.

        >>> os.environ['EDITOR'] = "echo 'I like cheese' > "
        >>> libbe.util.id.uuid_gen = lambda: 'Y'
        >>> ret = cmd.run(['-a', u'Frank', '/b'])
        Created comment with ID abc/b/Y
        >>> libbe.util.id.uuid_gen = uuid_gen
        >>> bd.flush_reload()
        >>> bug = bd.bug_from_uuid('b')
        >>> bug.load_comments(load_full=False)
        >>> comment = bug.comment_root[0]
        >>> print comment.body
        I like cheese
        <BLANKLINE>
        >>> ui.cleanup()
        >>> bd.cleanup()
        >>> del os.environ["EDITOR"]
    """

    name = 'comment'

    def run(self, args=None):
        args = args or []
        params = docopt(__doc__, argv=[Comment.name] + args)
        bugdirs = self._get_bugdirs()
        _, bug, parent = (bugdir_bug_comment_from_user_id(bugdirs,
                                                          params['ID']))

        if params['COMMENT'] is None:
            body = Comment._body(parent, bug)
        elif params['COMMENT'] == '-':  # read body from stdin
            if not params['--content-type'] is None\
                    and not params['content-type'].startswith("text/"):
                body = self.stdin.read()
                if not body.endswith('\n'):
                    body += '\n'
            else:  # read-in without decoding
                body = sys.stdin.read()
        else:  # body given on command line
            body = params['COMMENT']
            if not body.endswith('\n'):
                body += '\n'
        if params['--author'] is None:
            params['--author'] = self._get_user_id()

        new = parent.new_reply(body=body, content_type=params['--content-type'])
        for key in ['alt-id', 'author']:
            if params["--" + key] is not None:
                # pylint: disable=protected-access
                setattr(new, new._setting_name_to_attr_name(key),
                        params["--" + key])

        if params['--full-uuid']:
            comment_id = new.id.long_user()
        else:
            comment_id = new.id.user()

        self.stdout.write('Created comment with ID %s\n' % (comment_id))
        return 0

    @staticmethod
    def _body(parent, bug):
        try:
            # try to launch an editor for comment-body entry
            body = Comment._body_from_editor(parent, bug)
        except libbe.ui.util.editor.CantFindEditor:
            msg = 'No comment supplied, and EDITOR not specified.'
            raise libbe.command.UserError(msg)

        if body is None:
            raise libbe.command.UserError('No comment entered.')

        return body

    @staticmethod
    def _body_from_editor(parent, bug):
        if parent == bug.comment_root:
            header = "Subject: %s" % bug.summary
            parent_body = parent.string_thread() or "No comments"
        else:
            header = "From: %s\nTo: %s" % (parent.author, bug)
            parent_body = parent.body

        estr = 'Please enter your comment above\n\n%s\n\n> %s\n'\
            % (header, '\n> '.join(parent_body.splitlines()))
        return libbe.ui.util.editor.editor_string(estr)
