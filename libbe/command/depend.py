# Copyright (C) 2009-2018 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
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

import libbe
import libbe.bug
import libbe.bugdir
import libbe.command
import libbe.command.util
import libbe.util.tree

BLOCKS_TAG = "BLOCKS:"
BLOCKED_BY_TAG = "BLOCKED-BY:"


class Filter(object):
    # pylint: disable=too-few-public-methods, missing-docstring
    def __init__(self, status='all', severity='all', assigned='all',
                 target='all', extra_strings_regexps=None):
        self.status = status
        self.severity = severity
        self.assigned = assigned
        self.target = target
        self.extra_strings_regexps = extra_strings_regexps or []

    def __call__(self, bugdirs, bug):
        if not (self._match_attr(bug, 'status') and
                self._match_attr(bug, 'severity') and
                self._match_attr(bug, 'assigned')):
            return False

        if not self._match_target(bugdirs, bug):
            return False

        return self._match_extra_strings(bug)

    def _match_attr(self, bug, attr):
        allowed_attributes = ['status', 'severity', 'assigned']
        assert attr in allowed_attributes,\
            'Attribute %s not in %s' % (attr, allowed_attributes)
        assert hasattr(self, attr), 'Unknown attribute %s' % attr

        self_att = getattr(self, attr)
        bug_att = getattr(bug, attr)
        return self_att == 'all' or bug_att in self_att

    def _match_target(self, bugdirs, bug):
        if self.target == 'all':
            return True

        target_bug = libbe.command.target.bug_target(bugdirs, bug)

        if self.target in ['none', None] and target_bug.summary is None:
            return True

        if target_bug.summary == self.target:
            return True

        return False

    def _match_extra_strings(self, bug):
        if not self.extra_strings_regexps:
            return True

        if bug.extra_strings:
            for string in bug.extra_strings:
                for regexp in self.extra_strings_regexps:
                    if regexp.match(string):
                        return True
        else:
            for regexp in self.extra_strings_regexps:
                if regexp.match(''):
                    return True

        return False


def parse_status(status):
    if status == 'all':
        status = libbe.bug.status_values
    elif status == 'active':
        status = list(libbe.bug.active_status_values)
    elif status == 'inactive':
        status = list(libbe.bug.inactive_status_values)
    else:
        status = libbe.command.util.select_values(
            status, libbe.bug.status_values)
    return status


def parse_severity(severity, important=False):
    if important:
        serious = libbe.bug.severity_values.index('serious')
        severity = list(libbe.bug.severity_values[serious:])
    elif severity == 'all':
        severity = libbe.bug.severity_values
    else:
        severity = libbe.command.util.select_values(severity,
                                                    libbe.bug.severity_values)
    return severity


class BrokenLink(Exception):
    def __init__(self, blocked_bug, blocking_bug, blocks=True):
        if blocks:
            msg = "Missing link: %s blocks %s" \
                % (blocking_bug.id.user(), blocked_bug.id.user())
        else:
            msg = "Missing link: %s blocked by %s" \
                % (blocked_bug.id.user(), blocking_bug.id.user())
        super(BrokenLink, self).__init__(msg)
        self.blocked_bug = blocked_bug
        self.blocking_bug = blocking_bug


class Depend(libbe.command.Command):
    """Add/remove bug dependencies

    >>> import sys
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bd.storage)
    >>> cmd = Depend(ui=ui)

    >>> ret = ui.run(cmd, args=['/a', '/b'])
    abc/a blocked by:
    abc/b
    >>> ret = ui.run(cmd, args=['/a'])
    abc/a blocked by:
    abc/b
    >>> ret = ui.run(cmd, {'show-status':True}, ['/a']) # doctest: +NORMALIZE_WHITESPACE
    abc/a blocked by:
    abc/b closed
    >>> ret = ui.run(cmd, args=['/b', '/a'])
    abc/b blocked by:
    abc/a
    abc/b blocks:
    abc/a
    >>> ret = ui.run(cmd, {'show-status':True}, ['/a']) # doctest: +NORMALIZE_WHITESPACE
    abc/a blocked by:
    abc/b closed
    abc/a blocks:
    abc/b closed
    >>> ret = ui.run(cmd, {'show-summary':True}, ['/a']) # doctest: +NORMALIZE_WHITESPACE
    abc/a blocked by:
    abc/b       Bug B
    abc/a blocks:
    abc/b       Bug B
    >>> ret = ui.run(cmd, {'repair':True})
    >>> ret = ui.run(cmd, {'remove':True}, ['/b', '/a'])
    abc/b blocks:
    abc/a
    >>> ret = ui.run(cmd, {'remove':True}, ['/a', '/b'])
    >>> ui.cleanup()
    >>> bd.cleanup()
    """
    name = 'depend'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.options.extend([
                libbe.command.Option(name='remove', short_name='r',
                    help='Remove dependency (instead of adding it)'),
                libbe.command.Option(name='show-status', short_name='s',
                    help='Show status of blocking bugs'),
                libbe.command.Option(name='show-summary', short_name='S',
                    help='Show summary of blocking bugs'),
                libbe.command.Option(name='status',
                    help='Only show bugs matching the STATUS specifier',
                    arg=libbe.command.Argument(
                        name='status', metavar='STATUS', default=None,
                        completion_callback=libbe.command.util.complete_status)),
                libbe.command.Option(name='severity',
                    help='Only show bugs matching the SEVERITY specifier',
                    arg=libbe.command.Argument(
                        name='severity', metavar='SEVERITY', default=None,
                        completion_callback=libbe.command.util.complete_severity)),
                libbe.command.Option(name='tree-depth', short_name='t',
                    help='Print dependency tree rooted at BUG-ID with DEPTH levels of both blockers and blockees.  Set DEPTH <= 0 to disable the depth limit.',
                    arg=libbe.command.Argument(
                        name='tree-depth', metavar='INT', type='int',
                        completion_callback=libbe.command.util.complete_severity)),
                libbe.command.Option(name='repair',
                    help='Check for and repair one-way links'),
                ])
        self.args.extend([
                libbe.command.Argument(
                    name='bug-id', metavar='BUG-ID', default=None,
                    optional=True,
                    completion_callback=libbe.command.util.complete_bug_id),
                libbe.command.Argument(
                    name='blocking-bug-id', metavar='BUG-ID', default=None,
                    optional=True,
                    completion_callback=libbe.command.util.complete_bug_id),
                ])

    def _run(self, **params):
        if params['repair'] and params['bug-id'] is not None:
            raise libbe.command.UserError(
                'No arguments with --repair calls.')
        elif not params['repair'] and params['bug-id'] is None:
            raise libbe.command.UserError(
                'Must specify either --repair or a BUG-ID')

        if params['tree-depth'] is not None \
                and params['blocking-bug-id'] is not None:
            raise libbe.command.UserError(
                'Only one bug id used in tree mode.')

        bugdirs = self._get_bugdirs()
        if params['repair']:
            _, fixed, broken = check_dependencies(bugdirs,
                                                  repair_broken_links=True)
            assert not broken, broken
            if fixed:
                print >> self.stdout, 'Fixed the following links:'
                print >> self.stdout, \
                    '\n'.join(['%s |-- %s' %
                               (blockee.id.user(), blocker.id.user())
                               for blockee, blocker in fixed])
            return 0

        status = parse_status(params['status'])
        severity = parse_severity(params['severity'])
        _filter = Filter(status, severity)

        _, bug_a, dummy_comment = (
            libbe.command.util.bugdir_bug_comment_from_user_id(
                bugdirs, params['bug-id']))

        if params['tree-depth'] is not None:
            dtree = DependencyTree(bugdirs, bug_a, params['tree-depth'],
                                   _filter)
            if dtree.blocked_by_tree():
                print >> self.stdout, '%s blocked by:' % bug_a.id.user()
                for depth, node in dtree.blocked_by_tree().thread():
                    if depth == 0:
                        continue
                    print >> self.stdout, (
                        '%s%s'
                        % (' '*(depth), Depend.bug_string(node.bug, params)))
            if dtree.blocks_tree():
                print >> self.stdout, '%s blocks:' % bug_a.id.user()
                for depth, node in dtree.blocks_tree().thread():
                    if depth == 0:
                        continue
                    print >> self.stdout, (
                        '%s%s'
                        % (' '*(depth), Depend.bug_string(node.bug, params)))
            return 0

        if params['blocking-bug-id'] is not None:
            bugdirB, bug_b, dummy_comment = (
                libbe.command.util.bugdir_bug_comment_from_user_id(
                    bugdirs, params['blocking-bug-id']))
            if params['remove']:
                remove_block(bug_a, bug_b)
            else:  # add the dependency
                add_block(bug_a, bug_b)

        blocked_by = get_blocked_by(bugdirs, bug_a)

        if blocked_by:
            print >> self.stdout, '%s blocked by:' % bug_a.id.user()
            print >> self.stdout, \
                '\n'.join([Depend.bug_string(_bug, params)
                           for _bug in blocked_by])
        blocks = get_blocks(bugdirs, bug_a)
        if blocks:
            print >> self.stdout, '%s blocks:' % bug_a.id.user()
            print >> self.stdout, \
                '\n'.join([Depend.bug_string(_bug, params)
                           for _bug in blocks])
        return 0

    @staticmethod
    def bug_string(_bug, params):
        fields = [_bug.id.user()]
        if params['show-status']:
            fields.append(_bug.status)
        if params['show-summary']:
            fields.append(_bug.summary)
        return '\t'.join(fields)

    def _long_help(self):
        return """
Set a dependency with the second bug (B) blocking the first bug (A).
If bug B is not specified, just print a list of bugs blocking (A).

To search for bugs blocked by a particular bug, try
  $ be list --extra-strings BLOCKED-BY:<your-bug-uuid>

The --status and --severity options allow you to either blacklist or
whitelist values, for example
  $ be list --status open,assigned
will only follow and print dependencies with open or assigned status.
You select blacklist mode by starting the list with a minus sign, for
example
  $ be list --severity -target
which will only follow and print dependencies with non-target severity.

If neither bug A nor B is specified, check for and repair the missing
side of any one-way links.

The "|--" symbol in the repair-mode output is inspired by the
"negative feedback" arrow common in biochemistry.  See, for example
  http://www.nature.com/nature/journal/v456/n7223/images/nature07513-f5.0.jpg
"""

# internal helper functions


def _generate_blocks_string(blocked_bug):
    return '%s%s' % (BLOCKS_TAG, blocked_bug.uuid)


def _generate_blocked_by_string(blocking_bug):
    return '%s%s' % (BLOCKED_BY_TAG, blocking_bug.uuid)


def _parse_blocks_string(string):
    assert string.startswith(BLOCKS_TAG)
    return string[len(BLOCKS_TAG):]


def _parse_blocked_by_string(string):
    assert string.startswith(BLOCKED_BY_TAG)
    return string[len(BLOCKED_BY_TAG):]


def _add_remove_extra_string(bug, string, add):
    estrs = bug.extra_strings
    if add == True:
        estrs.append(string)
    else: # remove the string
        estrs.remove(string)
    bug.extra_strings = estrs # reassign to notice change


def _get_blocks(bug):
    uuids = []
    for line in bug.extra_strings:
        if line.startswith(BLOCKS_TAG):
            uuids.append(_parse_blocks_string(line))
    return uuids


def _get_blocked_by(bug):
    uuids = []
    for line in bug.extra_strings:
        if line.startswith(BLOCKED_BY_TAG):
            uuids.append(_parse_blocked_by_string(line))
    return uuids


def _repair_one_way_link(blocked_bug, blocking_bug, blocks=None):
    if blocks == True: # add blocks link
        blocks_string = _generate_blocks_string(blocked_bug)
        _add_remove_extra_string(blocking_bug, blocks_string, add=True)
    else: # add blocked by link
        blocked_by_string = _generate_blocked_by_string(blocking_bug)
        _add_remove_extra_string(blocked_bug, blocked_by_string, add=True)

# functions exposed to other modules

def add_block(blocked_bug, blocking_bug):
    blocked_by_string = _generate_blocked_by_string(blocking_bug)
    _add_remove_extra_string(blocked_bug, blocked_by_string, add=True)
    blocks_string = _generate_blocks_string(blocked_bug)
    _add_remove_extra_string(blocking_bug, blocks_string, add=True)

def remove_block(blocked_bug, blocking_bug):
    blocked_by_string = _generate_blocked_by_string(blocking_bug)
    _add_remove_extra_string(blocked_bug, blocked_by_string, add=False)
    blocks_string = _generate_blocks_string(blocked_bug)
    _add_remove_extra_string(blocking_bug, blocks_string, add=False)

def get_blocks(bugdirs, bug):
    """
    Return a list of bugs that the given bug blocks.
    """
    blocks = []
    for uuid in _get_blocks(bug):
        blocks.append(libbe.command.util.bug_from_uuid(bugdirs, uuid))
    return blocks

def get_blocked_by(bugdirs, bug):
    """
    Return a list of bugs blocking the given bug.
    """
    blocked_by = []
    for uuid in _get_blocked_by(bug):
        blocked_by.append(libbe.command.util.bug_from_uuid(bugdirs, uuid))
    return blocked_by

def check_dependencies(bugdirs, repair_broken_links=False):
    """
    Check that links are bi-directional for all bugs in bugdir.

    >>> import libbe.bugdir
    >>> bugdir = libbe.bugdir.SimpleBugDir()
    >>> bugdirs = {bugdir.uuid: bugdir}
    >>> a = bugdir.bug_from_uuid('a')
    >>> b = bugdir.bug_from_uuid('b')
    >>> blocked_by_string = _generate_blocked_by_string(b)
    >>> _add_remove_extra_string(a, blocked_by_string, add=True)
    >>> good,repaired,broken = check_dependencies(
    ...     bugdirs, repair_broken_links=False)
    >>> good
    []
    >>> repaired
    []
    >>> broken
    [(Bug(uuid='a'), Bug(uuid='b'))]
    >>> _get_blocks(b)
    []
    >>> good,repaired,broken = check_dependencies(
    ...     bugdirs, repair_broken_links=True)
    >>> _get_blocks(b)
    ['a']
    >>> good
    []
    >>> repaired
    [(Bug(uuid='a'), Bug(uuid='b'))]
    >>> broken
    []
    >>> bugdir.cleanup()
    """
    for bugdir in bugdirs.values():
        if bugdir.storage is not None:
            bugdir.load_all_bugs()
    good_links = []
    fixed_links = []
    broken_links = []
    for bugdir in bugdirs.values():
        for bug in bugdir:
            for blocker in get_blocked_by(bugdirs, bug):
                blocks = get_blocks(bugdirs, blocker)
                if (bug, blocks) in good_links+fixed_links+broken_links:
                    continue # already checked that link
                if bug not in blocks:
                    if repair_broken_links == True:
                        _repair_one_way_link(bug, blocker, blocks=True)
                        fixed_links.append((bug, blocker))
                    else:
                        broken_links.append((bug, blocker))
                else:
                    good_links.append((bug, blocker))
            for blockee in get_blocks(bugdirs, bug):
                blocked_by = get_blocked_by(bugdirs, blockee)
                if (blockee, bug) in good_links+fixed_links+broken_links:
                    continue # already checked that link
                if bug not in blocked_by:
                    if repair_broken_links == True:
                        _repair_one_way_link(blockee, bug, blocks=False)
                        fixed_links.append((blockee, bug))
                    else:
                        broken_links.append((blockee, bug))
                else:
                    good_links.append((blockee, bug))
    return (good_links, fixed_links, broken_links)

class DependencyTree (object):
    """
    Note: should probably be DependencyDiGraph.
    """
    def __init__(self, bugdirs, root_bug, depth_limit=0, filter=None):
        self.bugdirs = bugdirs
        self.root_bug = root_bug
        self.depth_limit = depth_limit
        self.filter = filter

    def _build_tree(self, child_fn):
        root = libbe.util.tree.Tree()
        root.bug = self.root_bug
        root.depth = 0
        stack = [root]
        while len(stack) > 0:
            node = stack.pop()
            if self.depth_limit > 0 and node.depth == self.depth_limit:
                continue
            for bug in child_fn(self.bugdirs, node.bug):
                if not self.filter(self.bugdirs, bug):
                    continue
                child = libbe.util.tree.Tree()
                child.bug = bug
                child.depth = node.depth+1
                node.append(child)
                stack.append(child)
        return root

    def blocks_tree(self):
        if not hasattr(self, "_blocks_tree"):
            self._blocks_tree = self._build_tree(get_blocks)
        return self._blocks_tree

    def blocked_by_tree(self):
        if not hasattr(self, "_blocked_by_tree"):
            self._blocked_by_tree = self._build_tree(get_blocked_by)
        return self._blocked_by_tree
