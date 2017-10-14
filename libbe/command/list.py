# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Oleg Romanyshyn <oromanyshyn@panoramicfeedback.com>
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

""" Bugs Everywhere - List bugs.

Usage:
    be list [--status=STATUS] [--severity=SEVERITY] [--important] [-a ASSIGNED|--assigned=ASSIGNED] [-m|--mine] [-e STRINGS|--extra-strings=STRINGS] [-S SORT|--sort=SORT] [-t tags] [-i ids] [-x| --xml]
    be list --complete
    be list -h | --help

Options:
    -h, --help                            Show this screen.
    --status=STATUS                       Filter by STATUS.   [default: active]
    --severity=SEVERITY                   Filter by SEVERITY. [default: all]
    --important                           List bugs with >= "serious" severity.
    -a ASSIGNED, --assigned=ASSIGNED      Filter by ASSIGNED.
    -m, --mine                            List bugs assigned to you.
    -e STRINGS, --extra-strings=STRINGS   Only show bugs matching STRINGS.
                                          I.e.: --extra-strings TAG:foo,TAG:xml.
    -S SORT, --sort=SORT                  Comma-separated list of cireteria
    -t, --tags                            Show tags field.
    -i, --ids                             Only print the bug ids.
    -x, --xml                             Dump output in XML format.

Status:
    %s, all

Severity:
    %s, all

Blocked By:
    To search for bugs blocked by a particular bug, try
        $ be list --extra-strings BLOCKED-BY:<your-bug-uuid>

Assigned:
    free form, with the string '-' being a shortcut for yourself.

Listing Explanation:
    This command lists bugs.  Normally it prints a short string like
        bea/576:om:[TAGS:] Allow attachments

    Where:  bea/576   the bug id
            o         the bug status is 'open' (first letter)
            m         the bug severity is 'minor' (first letter)
            TAGS      comma-separated list of bug tags (if --tags is set)
            Allo...   the bug summary string
"""

import itertools
import re

from docopt import docopt

import libbe
import libbe.bug
import libbe.command
import libbe.command.depend
from libbe.command.depend import Filter, parse_status, parse_severity
import libbe.command.tag
import libbe.command.target
import libbe.command.util

# get a list of * for cmp_*() comparing two bugs.
AVAILABLE_CMPS = [fn[4:] for fn in dir(libbe.bug) if fn[:4] == 'cmp_']
AVAILABLE_CMPS.remove('attr')  # a cmp_* template.


class List(libbe.command.Command):
    """List bugs

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bd.storage)
    >>> cmd = List(ui=ui)

    >>> ui.setup_command(cmd)

    >>> ret = cmd.run()
    abc/a:om: Bug A
    >>> ret = cmd.run(['--status', 'closed'])
    abc/b:cm: Bug B
    >>> ret = cmd.run(['--status', 'all', '--sort', 'time'])
    abc/a:om: Bug A
    abc/b:cm: Bug B
    >>> bd.storage.writeable
    True
    >>> ui.cleanup()
    >>> bd.cleanup()
    """

    name = 'list'

    def run(self, args=None):
        args = args or []
        params = docopt(__doc__ % (', '.join(libbe.bug.status_values),
                                   ', '.join(libbe.bug.severity_values)),
                        argv=[List.name] + args)
        storage = self._get_storage()
        bugdirs = self._get_bugdirs()
        writeable = storage.writeable
        storage.writeable = False
        cmp_list = List._parse_sort(params['--sort'])
        assigned = self._parse_assigned(bugdirs, params['--assigned'])
        extra_strings_regexps = List._parse_extras(params['--extra-strings'])
        status = parse_status(params['--status'])
        severity = parse_severity(params['--severity'],
                                  important=params['--important'])
        _filter = Filter(status, severity, assigned,
                         extra_strings_regexps=extra_strings_regexps)
        bugs = list(itertools.chain(*list(
            [bugdir.bug_from_uuid(uuid) for uuid in bugdir.uuids()]
            for bugdir in bugdirs.values())))
        bugs = [b for b in bugs if _filter(bugdirs, b)]
        self.result = bugs
        if not bugs and params['--xml']:
            print >> self.stdout, 'No matching bugs found'

        # sort bugs
        bugs = List._sort_bugs(bugs, cmp_list)

        # print list of bugs
        if params['--ids']:
            for bug in bugs:
                print >> self.stdout, bug.id.user()
        else:
            self._list_bugs(bugs, show_tags=params['--tags'],
                            xml=params['--xml'])
        storage.writeable = writeable
        return 0

    @staticmethod
    def _parse_sort(cmp_list):
        result = []
        if not cmp_list:
            return result

        for val in cmp_list.split(','):
            if val not in AVAILABLE_CMPS:
                raise libbe.command.UserError(
                    'Invalid sort on "%s".\nValid sorts:\n  %s'
                    % (val, '\n  '.join(AVAILABLE_CMPS)))
            result.append(getattr(libbe.bug, 'cmp_%s' % val))
        return result

    def _parse_assigned(self, bugdirs, assigned):
        if not assigned:
            return 'all'
        elif assigned == '-':
            assigned = self._get_user_id()

        if assigned.count(','):
            tmp = assigned.split(',')
            for key, val in enumerate(tmp):
                if val == '-':
                    tmp[key] = self._get_user_id()
                    break
            assigned = ','.join(tmp)

        assignees = libbe.command.util.assignees(bugdirs)
        return libbe.command.util.select_values(assigned, assignees)

    @staticmethod
    def _parse_extras(extras):
        if not extras:
            return []

        return [re.compile(x) for x in extras.split(',')]

    @staticmethod
    def _sort_bugs(bugs, cmp_list=None):
        if cmp_list is None:
            cmp_list = []
        cmp_list.extend(libbe.bug.DEFAULT_CMP_FULL_CMP_LIST)
        cmp_fn = libbe.bug.BugCompoundComparator(cmp_list=cmp_list)
        bugs.sort(cmp_fn)
        return bugs

    def _list_bugs(self, bugs, show_tags=False, xml=False):
        if xml:
            print >> self.stdout, \
                '<?xml version="1.0" encoding="%s" ?>' % self.stdout.encoding
            print >> self.stdout, '<be-xml>'
        if bugs:
            for bug in bugs:
                if xml:
                    print >> self.stdout, bug.xml(show_comments=True)
                else:
                    bug_string = bug.string(shortlist=True)
                    if show_tags:
                        attrs, summary = bug_string.split(' ', 1)
                        bug_string = (
                            '%s%s: %s'
                            % (attrs,
                               ','.join(libbe.command.tag.get_tags(bug)),
                               summary))
                    print >> self.stdout, bug_string
        if xml:
            print >> self.stdout, '</be-xml>'
