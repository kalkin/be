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

""" Bugs Everywhere - Distributed bug tracking - main command

Usage:
    be [-r REPO |-s URL] [--paginate|--no-pager] COMMAND [[COMMAND_OPTIONS...] [COMMAND_ARGS...]]
    be -h | --help
    be --full-version

Options:
    --full-version          Print full version information.
    --no-pager              Do not pipe output into a pager
    --paginate              Pipe all output into less (or if set, $PAGER)
    -h --help               Show this screen.
    -r REPO, --repo=REPO    Select BE repositor rather than current directory
    -s URL, --server=URL    Select BE command server instead of local repo
    --version               Print version string.

Commands:
"""

import sys
import locale
import pkgutil

from docopt import docopt

import libbe
import libbe.bugdir
import libbe.command
import libbe.command.help
import libbe.command.util
import libbe.storage
import libbe.version
import libbe.ui.util.pager
import libbe.util.encoding
import libbe.util.http


class CommandLine(libbe.command.UserInterface):
    def __init__(self, *args, **kwargs):
        libbe.command.UserInterface.__init__(self, *args, **kwargs)
        self.restrict_file_access = False
        self.storage_callbacks = None


def main():  # pylint: disable=missing-docstring
    locale.setlocale(locale.LC_ALL, '')
    io = libbe.command.StdInputOutput()
    ui = CommandLine(io)
    _usage = __doc__ + '    ' +\
        '\n    '.join([modname for _, modname, ispkg in
                       pkgutil.iter_modules(libbe.command.__path__)
                       if not ispkg and modname != 'base'])

    arguments = docopt(_usage, options_first=True,
                       version=libbe.version.version(verbose=False))

    if arguments['--full-version']:
        print >> ui.io.stdout, libbe.version.version(verbose=True)
        return 0

    command_name = arguments['COMMAND']
    try:
        klass = libbe.command.get_command_class(command_name=command_name)
    except libbe.command.UnknownCommand, e:
        print >> ui.io.stdout, e
        return 1

    ui.storage_callbacks = libbe.command.StorageCallbacks(
        location=arguments['--repo'])
    command = klass(ui=ui, server=arguments['--server'])
    ui.setup_command(command)

    if command.name in ['new', 'comment', 'commit', 'html', 'import-xml',
                        'serve-storage', 'serve-commands', 'web']:
        paginate = 'never'
    else:
        paginate = 'auto'
    if arguments['--paginate']:
        paginate = 'always'
    if arguments['--no-pager']:
        paginate = 'never'
    libbe.ui.util.pager.run_pager(paginate)

    ret = command.run(arguments['COMMAND_OPTIONS'] + arguments['COMMAND_ARGS'])

    try:
        ui.cleanup()
    except IOError, e:
        print >> ui.io.stdout, 'IOError:\n', e
        return 1

    return ret


if __name__ == '__main__':
    sys.exit(main())
