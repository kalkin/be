# Copyright (C) 2010-2012 Chris Ball <cjb@laptop.org>
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

"""Monotone_ backend.

.. _Monotone: http://www.monotone.ca/
"""

import distutils.spawn
import os
import os.path
import random
import shutil
import unittest

import libbe
import libbe.ui.util.user
from libbe.storage.vcs import base
from libbe.util.subproc import CommandError

if libbe.TESTING:
    import doctest
    import sys


def new():
    return Monotone()


class Monotone(base.VCS):
    """ :py:class:`base.VCS` implementation for Monotone. """
    name = 'monotone'
    client = 'mtn'

    def __init__(self, *args, **kwargs):
        base.VCS.__init__(self, *args, **kwargs)
        self._branch_name = 'bugs-everywhere-test'
        self._db_path = None
        self._key = 'bugseverywhere-%d@test.com' % random.randint(0, 1e6)
        self._key_dir = None
        self._passphrase = ''
        self.versioned = True
        self.__vcs_version = None

    @staticmethod
    def _vcs_installed():
        return distutils.spawn.find_executable(Monotone.client)

    @property
    def _vcs_version(self):
        if not self.__vcs_version:
            try:
                _, output, __ = self._u_invoke_client('automate',
                                                      'interface_version')
            except CommandError:  # command not found?
                return None
            self.__vcs_version = output.strip() + ".0"
        return self.__vcs_version

    def _require_version_ge(self, version):
        """Require installed interface version >= `*args`.

        >>> m = Monotone(repo='.')
        >>> m.__vcs_version = '7.1.0'
        >>> m._require_version_ge('6.0')
        >>> m._require_version_ge('7.1')
        >>> m._require_version_ge('7.2')
        Traceback (most recent call last):
          ...
        NotImplementedError: Operation not supported for monotone automation interface version 7.1.  Requires 7.2
        """
        version += '.0'
        if self < version:
            raise NotImplementedError(
                'Operation not supported for %s automation interface version'
                ' %s.  Requires %s' % (self.name, self._vcs_version, version))

    def _vcs_get_user_id(self):
        _, output, __ = self._u_invoke_client('list', 'keys')
        # output ~=
        # ...
        # [private keys]
        # f7791378b49dfb47a740e9588848b510de58f64f john@doe.com
        if '[private keys]' in output:
            private = False
            for line in output.splitlines():
                line = line.strip()
                if private is True:  # HACK.  Just pick the first key.
                    return line.split(' ', 1)[1]
                if line == '[private keys]':
                    private = True
        return None  # Monotone has no infomation

    def _vcs_detect(self, path):
        return self._u_search_parent_directories(path, '_MTN') is not None

    def _vcs_root(self, path):
        """Find the root of the deepest repository containing path."""
        if self >= '8.0':
            if not os.path.isdir(path):
                dirname = os.path.dirname(path)
            else:
                dirname = path
            _, output, __ = self._invoke_client('automate',
                                                'get_workspace_root',
                                                cwd=dirname)
        else:
            mtn_dir = self._u_search_parent_directories(path, '_MTN')
            if mtn_dir is None:
                return None
            return os.path.dirname(mtn_dir)
        return output.strip()

    def _invoke_client(self, *args, **kwargs):
        """ Invoke the client on our branch. """
        arglist = []
        if self._db_path is None:
            arglist.extend(['--db', self._db_path])
        if self._key is None:
            arglist.extend(['--key', self._key])
        if self._key_dir is None:
            arglist.extend(['--keydir', self._key_dir])
        arglist.extend(args)
        args = tuple(arglist)
        return self._u_invoke_client(*args, **kwargs)

    def _vcs_init(self, path):
        self._require_version_ge('4.0')
        self._db_path = os.path.abspath(os.path.join(path, 'bugseverywhere.db'))
        self._key_dir = os.path.abspath(os.path.join(path, '_monotone_keys'))
        self._u_invoke_client('db', 'init', '--db', self._db_path, cwd=path)
        os.mkdir(self._key_dir)
        self._u_invoke_client('--db', self._db_path,
                              '--keydir', self._key_dir,
                              'automate', 'genkey', self._key, self._passphrase)
        self._invoke_client('setup', '--db', self._db_path,
                            '--branch', self._branch_name, cwd=path)

    def _vcs_destroy(self):
        vcs_dir = os.path.join(self.repo, '_MTN')
        for _dir in [vcs_dir, self._key_dir]:
            if os.path.exists(_dir):
                shutil.rmtree(_dir)
        if os.path.exists(self._db_path):
            os.remove(self._db_path)

    def _vcs_add(self, path):
        if os.path.isdir(path):
            return
        self._invoke_client('add', path)

    def _vcs_remove(self, path):
        if not os.path.isdir(self._u_abspath(path)):
            self._invoke_client('rm', path)

    def _vcs_update(self, path):
        pass

    def _vcs_get_file_contents(self, path, revision=None):
        if revision is None:
            return base.VCS._vcs_get_file_contents(self, path, revision)

        self._require_version_ge('4.0')
        _, output, __ = self._invoke_client('automate', 'get_file_of',
                                            path, '--revision', revision)
        return output

    def _dirs_and_files(self, revision):
        self._require_version_ge('2.0')
        _, output, __ = self._invoke_client('automate', 'get_manifest_of',
                                            revision)
        dirs = []
        files = []
        children_by_dir = {}
        for line in output.splitlines():
            fields = line.strip().split(' ', 1)
            if len(fields) != 2 or len(fields[1]) < 2:
                continue

            value = fields[1][1:-1]  # [1:-1] for '"XYZ"' -> 'XYZ'
            if value == '':
                value = '.'

            if fields[0] == 'dir':
                dirs.append(value)
                children_by_dir[value] = []
            elif fields[0] == 'file':
                files.append(value)

        for child in dirs+files:
            if child == '.':
                continue
            parent = '.'
            for path in dirs:
                # Does Monotone use native path separators?
                start = path+os.path.sep
                if path != child and child.startswith(start):
                    rel = child[len(start):]
                    if rel.count(os.path.sep) == 0:
                        parent = path
                        break
            children_by_dir[parent].append(child)
        return (dirs, files, children_by_dir)

    def _vcs_path(self, id, revision):
        dirs, files, _ = self._dirs_and_files(revision)
        return self._u_find_id_from_manifest(id, dirs+files, revision=revision)

    def _vcs_isdir(self, path, revision):
        dirs, _, __ = self._dirs_and_files(revision)
        return path in dirs

    def _vcs_listdir(self, path, revision):
        _, __, children_by_dir = self._dirs_and_files(revision)
        children = [self._u_rel_path(c, path) for c in children_by_dir[path]]
        return children

    def _vcs_commit(self, commitfile, allow_empty=False):
        args = ['commit', '--key', self._key, '--message-file', commitfile]
        kwargs = {'expect': (0, 1)}
        status, output, error = self._invoke_client(*args, **kwargs)
        strings = ['no changes to commit']
        current_rev = self._current_revision()
        if status == 1:
            if self._u_any_in_string(strings, error):
                if not allow_empty:
                    raise base.EmptyCommit()
                # note that Monotone does _not_ make an empty revision.
                # this returns the last non-empty revision id...
            else:
                raise CommandError(
                    [self.client] + args, status, output, error)
        else:  # successful commit
            assert current_rev in error, \
                'Mismatched revisions:\n%s\n%s' % (current_rev, error)
        return current_rev

    def _current_revision(self):
        self._require_version_ge('2.0')
        _, output, __ = self._invoke_client('automate', 'get_base_revision_id')
        return output.strip()

    def _vcs_revision_id(self, index):
        current_rev = self._current_revision()
        _, output, __ = self._invoke_client('automate', 'ancestors',
                                            current_rev)
        revs = output.splitlines() + [current_rev]
        _, output, __ = self._invoke_client('automate', 'toposort', *revs)
        revisions = output.splitlines()
        try:
            if index > 0:
                return revisions[index-1]
            elif index < 0:
                return revisions[index]
            return None
        except IndexError:
            return None

    def _diff(self, revision):
        _, output, __ = self._invoke_client('-r', revision, 'diff')
        return output


if libbe.TESTING:
    base.make_vcs_testcase_subclasses(Monotone, sys.modules[__name__])

    unitsuite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
