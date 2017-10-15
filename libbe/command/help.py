# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Marien Zwart <marien.zwart@gmail.com>
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

""" Bugs Everywhere - Print help for specified topic.

Usage:
    be help TOPIC
    be (-h| --help)

Topics:
    repo
    server
"""

from docopt import docopt


import libbe
import libbe.command
import libbe.command.util


TOPICS = {'repo': """A BE repository containing child bugdirs

BE repositories are stored in an abstract `Storage` instance, which
may or may not be versioned.  If you're using BE to track bugs in your
local software, you'll probably be using an on-disk storage based on
the VCS you use to version the storage.  See `be help init` for
details about automatic VCS-detection.

While most users will be using local storage, BE also supports remote
storage servers.  This allows projects to publish their local
repository in a way that's directly accessible to remote users.  The
remote users can then use a local BE client to interact with the
remote repository, without having to create a local copy of the
repository.  The remote server will be running something like:

    $ be serve-storage --host 123.123.123.123 --port 54321

And the local client can run:

    $ be --repo http://123.123.123.123:54321 list

or whichever command they like.

Because the storage server serves repositories at the `Storage` level,
it can be inefficient.  For example, `be list` will have to transfer
the data for all the bugs in a repository over the wire.  The storage
server can also be harder to lock down, because users with write
access can potentially store data that cannot be parsed by BE.  For a
more efficient server, see `be serve-commands`.
""",
          'server': """A server for remote BE command execution

The usual way for a user to interact with a BE bug tracker for a
particular project is to clone the project repository.  They can then
use their local BE client to browse the repository and make changes,
before pushing their changes back upstream.  For the average user
seeking to file a bug or comment, this can be too much work.  One way
to simplify the process is to use a storage server (see `be help
repo`), but this is not always ideal.  A more robust approach is to
use a command server.

The remote server will be running something like:

    $ be serve-commands --host 123.123.123.123 --port 54321

And the local client can run:

    $ be --server http://123.123.123.123:54321 list

or whichever command they like.  The command line arguments are parsed
locally, and then POSTed to the command server, where the command is
executed.  The output of the command is returned to the client for
display.  This requires much less traffic over the wire than running
the same command via a storage server.
"""}


class Help(libbe.command.Command):
    """ Print help for given topic. """
    name = 'help'

    def run(self, args=None):
        args = args or []
        params = docopt(__doc__, argv=[Help.name] + args)
        topic = params['TOPIC']
        if topic in TOPICS:
            # pylint: disable=no-member
            print >> self.stdout, TOPICS[topic].rstrip('\n')
        else:
            raise libbe.command.UserError('"%s" is an uknown topic' % topic)
        return 0
