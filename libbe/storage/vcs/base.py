# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Alexander Belchenko <bialix@ukr.net>
#                         Ben Finney <benf@cybersource.com.au>
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

"""Define the base :py:class:`VCS` (Version Control System) class, which
should be subclassed by other Version Control System backends.  The
base class implements a "do not version" VCS.
"""

import codecs
import os
import os.path
import re
import shutil
import sys
import tempfile

import libbe
import libbe.storage
import libbe.storage.base
import libbe.util.encoding
from libbe.storage.base import EmptyCommit, InvalidRevision, InvalidID
from libbe.util.utility import Dir, search_parent_directories
from libbe.util.subproc import invoke
from libbe.util.plugin import import_by_name

from libbe.unidiff import PatchSet

if libbe.TESTING:
    import unittest
    import doctest

    import libbe.ui.util.user

VCS_ORDER = ['bzr', 'darcs', 'git', 'hg', 'monotone']
"""List VCS modules in order of preference.

Don't list this module, it is implicitly last.
"""


def set_preferred_vcs(name):
    """Manipulate :py:data:`VCS_ORDER` to place `name` first.

    This is primarily indended for testing purposes.
    """
    global VCS_ORDER
    assert name in VCS_ORDER, \
        'unrecognized VCS %s not in\n  %s' % (name, VCS_ORDER)
    VCS_ORDER.remove(name)
    VCS_ORDER.insert(0, name)


def _get_matching_vcs(matchfn):
    """Return the first module for which matchfn(VCS_instance) is True.

    Searches in :py:data:`VCS_ORDER`.
    """
    for submodname in VCS_ORDER:
        module = import_by_name('libbe.storage.vcs.%s' % submodname)
        vcs = module.new()
        if matchfn(vcs):
            return vcs
    return VCS()


def vcs_by_name(vcs_name):
    """Return the module for the VCS with the given name.

    Searches in :py:data:`VCS_ORDER`.
    """
    if vcs_name == VCS.name:
        return new()
    return _get_matching_vcs(lambda vcs: vcs.name == vcs_name)


def detect_vcs(dir):
    """Return an VCS instance for the vcs being used in this directory.

    Searches in :py:data:`VCS_ORDER`.
    """
    return _get_matching_vcs(lambda vcs: vcs._detect(dir))


def installed_vcs():
    """Return an instance of an installed VCS.

    Searches in :py:data:`VCS_ORDER`.
    """
    return _get_matching_vcs(lambda vcs: vcs.installed())


class VCSNotRooted(libbe.storage.base.ConnectionError):
    def __init__(self, vcs):
        msg = 'VCS not rooted'
        super(VCSNotRooted, self).__init__(msg)
        self.vcs = vcs


class VCSUnableToRoot(libbe.storage.base.ConnectionError):
    def __init__(self, vcs):
        msg = 'VCS unable to root'
        super(VCSUnableToRoot, self).__init__(msg)
        self.vcs = vcs


class InvalidPath(InvalidID):
    def __init__(self, path, root, msg=None, **kwargs):
        if msg is None:
            msg = 'Path "%s" not in root "%s"' % (path, root)
        super(InvalidPath, self).__init__(msg=msg, **kwargs)
        self.path = path
        self.root = root


class SpacerCollision(InvalidPath):
    def __init__(self, path, spacer):
        msg = 'Path "%s" collides with spacer directory "%s"' % (path, spacer)
        super(SpacerCollision, self).__init__(path, root=None, msg=msg)
        self.spacer = spacer


class NoSuchFile(InvalidID):
    def __init__(self, pathname, root='.'):
        path = os.path.abspath(os.path.join(root, pathname))
        super(NoSuchFile, self).__init__('No such file: %s' % path)


class CachedPathID (object):
    """Cache Storage ID <-> path policy.
 
    Paths generated following::

       .../.be/BUGDIR/bugs/BUG/comments/COMMENT
          ^-- root path

    See :py:mod:`libbe.util.id` for a discussion of ID formats.

    Examples
    --------

    >>> dir = Dir()
    >>> os.mkdir(os.path.join(dir.path, '.be'))
    >>> os.mkdir(os.path.join(dir.path, '.be', 'abc'))
    >>> os.mkdir(os.path.join(dir.path, '.be', 'abc', 'bugs'))
    >>> os.mkdir(os.path.join(dir.path, '.be', 'abc', 'bugs', '123'))
    >>> os.mkdir(os.path.join(dir.path, '.be', 'abc', 'bugs', '123', 'comments'))
    >>> os.mkdir(os.path.join(dir.path, '.be', 'abc', 'bugs', '123', 'comments', 'def'))
    >>> os.mkdir(os.path.join(dir.path, '.be', 'abc', 'bugs', '456'))
    >>> open(os.path.join(dir.path, '.be', 'abc', 'values'),
    ...      'w').close()
    >>> open(os.path.join(dir.path, '.be', 'abc', 'bugs', '123', 'values'),
    ...      'w').close()
    >>> open(os.path.join(dir.path, '.be', 'abc', 'bugs', '123', 'comments', 'def', 'values'),
    ...      'w').close()
    >>> c = CachedPathID()
    >>> c.root(dir.path)
    >>> c.id(os.path.join(dir.path, '.be', 'abc', 'bugs', '123', 'comments', 'def', 'values'))
    'def/values'
    >>> c.init()
    >>> sorted(os.listdir(os.path.join(c._root, '.be')))
    ['abc', 'id-cache']
    >>> c.connect()
    >>> c.path('123/values') # doctest: +ELLIPSIS
    u'.../.be/abc/bugs/123/values'
    >>> c.disconnect()
    >>> c.destroy()
    >>> sorted(os.listdir(os.path.join(c._root, '.be')))
    ['abc']
    >>> c.connect() # demonstrate auto init
    >>> sorted(os.listdir(os.path.join(c._root, '.be')))
    ['abc', 'id-cache']
    >>> c.add_id(u'xyz', parent=None) # doctest: +ELLIPSIS
    u'.../.be/xyz'
    >>> c.add_id('xyz/def', parent='xyz') # doctest: +ELLIPSIS
    u'.../.be/xyz/def'
    >>> c.add_id('qrs', parent='123') # doctest: +ELLIPSIS
    u'.../.be/abc/bugs/123/comments/qrs'
    >>> c.disconnect()
    >>> c.connect()
    >>> c.path('qrs') # doctest: +ELLIPSIS
    u'.../.be/abc/bugs/123/comments/qrs'
    >>> c.remove_id('qrs')
    >>> c.path('qrs')
    Traceback (most recent call last):
      ...
    InvalidID: qrs in revision None
    >>> c.disconnect()
    >>> c.destroy()
    >>> dir.cleanup()
    """
    def __init__(self, encoding=None):
        self.encoding = libbe.util.encoding.get_text_file_encoding()
        self._cache = {}  # key: uuid, value: path
        self._changed = False
        self._spacer_dirs = ['.be', 'bugs', 'comments']

    def root(self, path):
        self._root = os.path.abspath(path).rstrip(os.path.sep)
        self._cache_path = os.path.join(
            self._root, self._spacer_dirs[0], 'id-cache')

    def init(self, cache=None):
        """Create cache file for an existing .be directory.

        The file contains multiple lines of the form::

            UUID\tPATH
        """
        if cache is not None:
            self._cache = cache

        spaced_root = os.path.join(self._root, self._spacer_dirs[0])
        for dirpath, _, __ in os.walk(spaced_root, followlinks=True):
            if dirpath == spaced_root:
                continue
            try:
                _id = self.id(dirpath)
                relpath = dirpath[len(self._root + os.path.sep):]
                if _id.count('/') == 0:
                    if _id in self._cache:
                        libbe.LOG.warning(
                            'multiple paths for {0}:\n  {1}\n  {2}'.format(
                                _id, self._cache[_id], relpath))
                    self._cache[_id] = relpath
            except InvalidPath:
                pass
        if self._cache != cache:
            self._changed = True
        if cache is None:
            self.disconnect()

    def destroy(self):
        if os.path.exists(self._cache_path):
            os.remove(self._cache_path)

    def connect(self):
        if not os.path.exists(self._cache_path):
            try:
                self.init()
            except IOError:
                raise libbe.storage.base.ConnectionError
        self._changed = False
        with(codecs.open(self._cache_path, 'r', self.encoding)) as f:
            for line in f:
                fields = line.rstrip('\n').split('\t')
                self._cache[fields[0]] = fields[1]

    def disconnect(self):
        if self._changed:
            f = codecs.open(self._cache_path, 'w', self.encoding)
            for uuid, path in self._cache.items():
                f.write('%s\t%s\n' % (uuid, path))
            f.close()
        self._cache = {}

    def path(self, _id, relpath=False):
        fields = _id.split('/', 1)
        uuid = fields[0]
        if len(fields) == 1:
            extra = []
        else:
            extra = fields[1:]
        if uuid not in self._cache:
            self.init(cache=self._cache)
            if uuid not in self._cache:
                raise InvalidID(uuid)
        if relpath:
            return os.path.join(self._cache[uuid], *extra)
        return os.path.join(self._root, self._cache[uuid], *extra)

    def add_id(self, _id, parent=None):
        if _id.count('/') > 0:
            # not a UUID-level path
            assert _id.startswith(parent), \
                'Strange ID: "%s" should start with "%s"' % (_id, parent)
            path = self.path(_id)
        elif _id in self._cache:
            # already added
            path = self.path(_id)
        else:
            if parent is None:
                parent_path = ''
                spacer = self._spacer_dirs[0]
            else:
                assert parent.count('/') == 0, \
                    'Strange parent ID: "%s" should be UUID' % parent
                parent_path = self.path(parent, relpath=True)
                parent_spacer = parent_path.split(os.path.sep)[-2]
                i = self._spacer_dirs.index(parent_spacer)
                spacer = self._spacer_dirs[i+1]
            path = os.path.join(parent_path, spacer, _id)
            self._cache[_id] = path
            self._changed = True
            path = os.path.join(self._root, path)
        return path

    def remove_id(self, _id):
        if _id.count('/') > 0:
            return  # not a UUID-level path
        self._cache.pop(_id)
        self._changed = True

    def id(self, path):
        path = os.path.join(self._root, path)
        if not path.startswith(self._root + os.path.sep):
            raise InvalidPath(path, self._root)
        path = path[len(self._root + os.path.sep):]
        orig_path = path
        if not path.startswith(self._spacer_dirs[0] + os.path.sep):
            raise InvalidPath(path, self._spacer_dirs[0])
        for spacer in self._spacer_dirs:
            if not path.startswith(spacer + os.path.sep):
                break
            _id = path[len(spacer + os.path.sep):]
            fields = path[len(spacer + os.path.sep):].split(os.path.sep, 1)
            if len(fields) == 1:
                break
            path = fields[1]
        for spacer in self._spacer_dirs:
            if _id.endswith(os.path.sep + spacer):
                raise SpacerCollision(orig_path, spacer)
        if os.path.sep != '/':
            _id = _id.replace(os.path.sep, '/')
        return _id


def new():
    return VCS()


class VCS(libbe.storage.base.VersionedStorage):
    """Implement a 'no-VCS' interface.

    Support for other VCSs can be added by subclassing this class, and
    overriding methods `_vcs_*()` with code appropriate for your VCS.

    The methods `_u_*()` are utility methods available to the `_vcs_*()`
    methods.
    """
    name = 'None'
    client = 'false'  # command-line tool for _u_invoke_client

    def __init__(self, *args, **kwargs):
        if 'encoding' not in kwargs:
            kwargs['encoding'] = libbe.util.encoding.get_text_file_encoding()
        libbe.storage.base.VersionedStorage.__init__(self, *args, **kwargs)
        self.versioned = False
        self._cached_path_id = CachedPathID()
        self._rooted = False
        self._parsed_version = None
        self._version = None

    def _vcs_version(self):  # pylint: disable=no-self-use
        """
        Return the VCS version string.
        """
        return '0'

    def _vcs_get_user_id(self):  # pylint: disable=no-self-use
        """
        Get the VCS's suggested user id (e.g. "John Doe <jdoe@example.com>").
        If the VCS has not been configured with a username, return None.
        """
        return None

    def _vcs_detect(self, path=None):
        """ Detect whether a directory is revision controlled with this VCS.
        """  # pylint: disable=unused-argument,no-self-use
        return True

    def _vcs_root(self, path):  # pylint: disable=no-self-use
        """
        Get the VCS root.  This is the default working directory for
        future invocations.  You would normally set this to the root
        directory for your VCS.
        """
        if not os.path.isdir(path):
            path = os.path.dirname(path)
            if path == '':
                path = os.path.abspath('.')
        return path

    def _vcs_init(self, path):
        """
        Begin versioning the tree based at path.
        """

    def _vcs_destroy(self):
        """
        Remove any files used in versioning (e.g. whatever _vcs_init()
        created).
        """

    def _vcs_add(self, path):
        """
        Add the already created file at path to version control.
        """

    def _vcs_exists(self, path, revision=None):
        """
        Does the path exist in a given revision? (True/False)
        """
        raise NotImplementedError('Lazy BE developers')

    def _vcs_remove(self, path):
        """
        Remove the file at path from version control.  Optionally
        remove the file from the filesystem as well.
        """

    def _vcs_update(self, path):
        """
        Notify the versioning system of changes to the versioned file
        at path.
        """

    def _vcs_get_file_contents(self, path, revision=None):
        """
        Get the file contents as they were in a given revision.
        Revision==None specifies the current revision.
        """
        if revision is not None:
            msg = 'The %s VCS does not support revision specifiers' % self.name
            raise libbe.storage.base.InvalidRevision(msg)
        path = os.path.join(self.repo, path)

        if not os.path.exists(path):
            return libbe.util.InvalidObject

        if os.path.isdir(path):
            return libbe.storage.base.InvalidDirectory

        with open(path, 'rb') as f:
            contents = f.read()

        return contents

    def _vcs_path(self, id, revision):
        """
        Return the relative path to object id as of revision.

        Revision will not be None.
        """
        raise NotImplementedError

    def _vcs_isdir(self, path, revision):
        """
        Return True if path (as returned by _vcs_path) was a directory
        as of revision, False otherwise.

        Revision will not be None.
        """
        raise NotImplementedError

    def _vcs_listdir(self, path, revision):
        """
        Return a list of the contents of the directory path (as
        returned by _vcs_path) as of revision.

        Revision will not be None, and ._vcs_isdir(path, revision)
        will be True.
        """
        raise NotImplementedError

    def _vcs_commit(self, commitfile, allow_empty=False):
        """
        Commit the current working directory, using the contents of
        commitfile as the comment.  Return the name of the old
        revision (or None if commits are not supported).

        If allow_empty == False, raise EmptyCommit if there are no
        changes to commit.
        """  # pylint: disable=no-self-use
        return None

    def _vcs_revision_id(self, index):
        """
        Return the name of the <index>th revision.  Index will be an
        integer (possibly <= 0).  The choice of which branch to follow
        when crossing branches/merges is not defined.

        Return None if revision IDs are not supported, or if the
        specified revision does not exist.
        """  # pylint: disable=unused-argument,no-self-use
        return None

    def _diff(self, revision):
        """ Return the output string of a vcs specific diff command """
        raise NotImplementedError

    def _vcs_changed(self, revision):
        """
        Return a tuple of lists of ids
          (new, modified, removed)
        from the specified revision to the current situation.
        """
        output = self._diff(revision)
        patch = PatchSet.from_string(output)
        return patch.changed_files

    def version(self):
        # Cache version string for efficiency.
        if self._version is None:
            self._version = self._vcs_version()
        return self._version

    def version_cmp(self, *args):
        """Compare the installed VCS version `V_i` with another version
        `V_o` (given in `*args`).  Returns

           === ===============
            1  if `V_i > V_o`
            0  if `V_i == V_o`
           -1  if `V_i < V_o`
           === ===============

        Examples
        --------

        >>> v = VCS(repo='.')
        >>> v._version = '2.3.1 (release)'
        >>> v.version_cmp(2,3,1)
        0
        >>> v.version_cmp(2,3,2)
        -1
        >>> v.version_cmp(2,3,'a',5)
        1
        >>> v.version_cmp(2,3,0)
        1
        >>> v.version_cmp(2,3,1,'a',5)
        1
        >>> v.version_cmp(2,3,1,1)
        -1
        >>> v.version_cmp(3)
        -1
        >>> v._version = '2.0.0pre2'
        >>> v._parsed_version = None
        >>> v.version_cmp(3)
        -1
        >>> v.version_cmp(2,0,1)
        -1
        >>> v.version_cmp(2,0,0,'pre',1)
        1
        >>> v.version_cmp(2,0,0,'pre',2)
        0
        >>> v.version_cmp(2,0,0,'pre',3)
        -1
        >>> v.version_cmp(2,0,0,'a',3)
        1
        >>> v.version_cmp(2,0,0,'rc',1)
        -1
        """
        if self._parsed_version is None:
            num_part = self.version().split(' ')[0]
            self._parsed_version = []
            for num in num_part.split('.'):
                try:
                    self._parsed_version.append(int(num))
                except ValueError:
                    # bzr version number might contain non-numerical tags
                    splitter = re.compile(r'[\D]')  # Match non-digits
                    splits = splitter.split(num)
                    # if len(tag) > 1 some splits will be empty; remove
                    splits = [s for s in splits if s]
                    tag_starti = len(splits[0])
                    num_starti = num.find(splits[1], tag_starti)
                    tag = num[tag_starti:num_starti]
                    self._parsed_version.append(int(splits[0]))
                    self._parsed_version.append(tag)
                    self._parsed_version.append(int(splits[1]))
        for current, other in zip(self._parsed_version, args):
            if not isinstance(current, other.__class__):
                # one of them is a pre-release string
                if not isinstance(current, int):
                    return -1
                return 1
            c = cmp(current, other)
            if c != 0:
                return c
        # see if one is longer than the other
        verlen = len(self._parsed_version)
        arglen = len(args)
        if verlen == arglen:
            return 0
        elif verlen > arglen:
            if not isinstance(self._parsed_version[arglen], int):
                return -1  # self is a prerelease

            return 1

        if not isinstance(args[verlen], int):
            return 1  # args is a prerelease

        return -1

    def installed(self):
        if self.version() is not None:
            return True
        return False

    def get_user_id(self):
        """
        Get the VCS's suggested user id (e.g. "John Doe <jdoe@example.com>").
        If the VCS has not been configured with a username, return None.
        You can override the automatic lookup procedure by setting the
        VCS.user_id attribute to a string of your choice.
        """
        if not hasattr(self, 'user_id'):
            self.user_id = self._vcs_get_user_id()
            if self.user_id is None:
                # guess missing info
                name = libbe.ui.util.user.get_fallback_fullname()
                email = libbe.ui.util.user.get_fallback_email()
                self.user_id = libbe.ui.util.user.create_user_id(name, email)
        return self.user_id

    def _detect(self, path='.'):
        """
        Detect whether a directory is revision controlled with this VCS.
        """
        return self._vcs_detect(path)

    def root(self):
        """Set the root directory to the path's VCS root.

        This is the default working directory for future invocations.
        Consider the following usage case:

        You have a project rooted in::

          /path/to/source/

        by which I mean the VCS repository is in, for example::

          /path/to/source/.bzr

        However, you're of in some subdirectory like::

          /path/to/source/ui/testing

        and you want to comment on a bug.  `root` will locate your VCS
        root (``/path/to/source/``) and set the repo there.  This
        means that it doesn't matter where you are in your project
        tree when you call "be COMMAND", it always acts as if you called
        it from the VCS root.
        """
        if not self._detect(self.repo):
            raise VCSUnableToRoot(self)
        root = self._vcs_root(self.repo)
        self.repo = os.path.realpath(root)
        if not os.path.isdir(self.repo):
            self.repo = os.path.dirname(self.repo)
        self.be_dir = os.path.join(self.repo,
                                   self._cached_path_id._spacer_dirs[0])
        self._cached_path_id.root(self.repo)
        self._rooted = True

    def _init(self):
        """
        Begin versioning the tree based at self.repo.
        Also roots the vcs at path.

        See Also
        --------
        root : called if the VCS has already been initialized.
        """
        if not os.path.exists(self.repo) or not os.path.isdir(self.repo):
            raise VCSUnableToRoot(self)

        if not self._vcs_detect(self.repo):
            self._vcs_init(self.repo)

        if not self._rooted:
            self.root()

        os.mkdir(self.be_dir)
        self._vcs_add(self._u_rel_path(self.be_dir))
        self._setup_storage_version()
        self._cached_path_id.init()

    def _destroy(self):
        self._vcs_destroy()
        self._cached_path_id.destroy()
        if os.path.exists(self.be_dir):
            shutil.rmtree(self.be_dir)

    def _connect(self):
        if not self._rooted:
            self.root()
        if not os.path.isdir(self.be_dir):
            raise libbe.storage.base.ConnectionError(self)
        self._cached_path_id.connect()
        self.check_storage_version()

    def _disconnect(self):
        self._cached_path_id.disconnect()

    def path(self, id, revision=None, relpath=True):
        if revision is None:
            path = self._cached_path_id.path(id)
            if relpath:
                return self._u_rel_path(path)
            return path
        path = self._vcs_path(id, revision)
        if relpath:
            return path
        return os.path.join(self.repo, path)

    def _add_path(self, path, directory=False):
        relpath = self._u_rel_path(path)
        reldirs = relpath.split(os.path.sep)
        if not directory:
            reldirs = reldirs[:-1]
        dir = self.repo
        for reldir in reldirs:
            dir = os.path.join(dir, reldir)
            if not os.path.exists(dir):
                os.mkdir(dir)
                self._vcs_add(self._u_rel_path(dir))
            elif not os.path.isdir(dir):
                raise libbe.storage.base.InvalidDirectory
        if not directory:
            if not os.path.exists(path):
                open(path, 'w').close()
            self._vcs_add(self._u_rel_path(path))

    def _add(self, id, parent=None, **kwargs):
        path = self._cached_path_id.add_id(id, parent)
        self._add_path(path, **kwargs)

    def _exists(self, id, revision=None):
        if revision is None:
            try:
                path = self.path(id, revision, relpath=False)
            except InvalidID:
                return False
            return os.path.exists(path)
        path = self.path(id, revision, relpath=True)
        return self._vcs_exists(path, revision)

    def _remove(self, id):
        path = self._cached_path_id.path(id)
        if os.path.exists(path):
            if os.path.isdir(path) and self.children(id):
                raise libbe.storage.base.DirectoryNotEmpty(id)
            self._vcs_remove(self._u_rel_path(path))
            if os.path.exists(path):
                if os.path.isdir(path):
                    os.rmdir(path)
                else:
                    os.remove(path)
        self._cached_path_id.remove_id(id)

    def _recursive_remove(self, id):
        path = self._cached_path_id.path(id)
        for dirpath, dirnames, filenames in os.walk(path, topdown=False):
            filenames.extend(dirnames)
            for f in filenames:
                fullpath = os.path.join(dirpath, f)
                if not os.path.exists(fullpath):
                    continue
                self._vcs_remove(self._u_rel_path(fullpath))
        if os.path.exists(path):
            shutil.rmtree(path)
        path = self._cached_path_id.path(id, relpath=True)
        for _id, cache_path in self._cached_path_id._cache.items():
            if cache_path.startswith(path):
                self._cached_path_id.remove_id(_id)

    def _ancestors(self, id=None, revision=None):
        if id is None:
            path = self.be_dir
        else:
            path = self.path(id, revision, relpath=False)
        ancestors = []
        while True:
            if not path.startswith(self.repo + os.path.sep):
                break
            path = os.path.dirname(path)
            try:
                id = self._u_path_to_id(path)
                ancestors.append(id)
            except (SpacerCollision, InvalidPath):
                pass
        return ancestors

    def _children(self, id=None, revision=None):
        if revision is None:
            isdir = os.path.isdir
            listdir = os.listdir
        else:
            isdir = lambda path: self._vcs_isdir(
                self._u_rel_path(path), revision)
            listdir = lambda path: self._vcs_listdir(
                self._u_rel_path(path), revision)

        if id is None:
            path = self.be_dir
        else:
            path = self.path(id, revision, relpath=False)

        if not isdir(path):
            return []

        children = listdir(path)

        for i, child in enumerate(children):
            if child in self._cached_path_id._spacer_dirs:
                children[i] = None
                cache_files = listdir(os.path.join(path, child))
                children.extend([os.path.join(child, c2) for c2 in cache_files])
            elif child in ['id-cache', 'version']:
                children[i] = None

        for i, child in enumerate(children):
            if child is None:
                continue

            cpath = os.path.join(path, child)
            children[i] = self._u_path_to_id(cpath)

        return [c for c in children if c is not None]

    def _get(self, id, default=libbe.util.InvalidObject, revision=None):
        try:
            relpath = self.path(id, revision, relpath=True)
            contents = self._vcs_get_file_contents(relpath, revision)
        except InvalidID, e:
            if default == libbe.util.InvalidObject:
                raise e
            return default

        if contents in [libbe.storage.base.InvalidDirectory,
                        libbe.util.InvalidObject] or not contents:
            if default == libbe.util.InvalidObject:
                raise InvalidID(id, revision)
            return default
        return contents

    def _set(self, id, value):
        try:
            path = self._cached_path_id.path(id)
        except InvalidID:
            raise

        if not os.path.exists(path):
            raise InvalidID(id)
        elif os.path.isdir(path):
            raise libbe.storage.base.InvalidDirectory(id)

        with open(path, "wb") as f:
            f.write(value)

        self._vcs_update(self._u_rel_path(path))

    def _commit(self, summary, body=None, allow_empty=False):
        summary = summary.strip()+'\n'
        if body is not None:
            summary += '\n' + body.strip() + '\n'
        descriptor, filename = tempfile.mkstemp()
        revision = None
        try:
            temp_file = os.fdopen(descriptor, 'wb')
            temp_file.write(summary)
            temp_file.flush()
            revision = self._vcs_commit(filename, allow_empty=allow_empty)
            temp_file.close()
        finally:
            os.remove(filename)
        return revision

    def revision_id(self, index=None):
        if index is None:
            return None

        try:
            if int(index) != index:
                raise InvalidRevision(index)
        except ValueError:
            raise InvalidRevision(index)

        revid = self._vcs_revision_id(index)
        if revid is None:
            raise libbe.storage.base.InvalidRevision(index)
        return revid

    def changed(self, revision):
        add, mod, rem = self._vcs_changed(revision)

        def paths_to_ids(paths):
            for p in paths:
                try:
                    _id = self._u_path_to_id(p)
                    yield _id
                except (SpacerCollision, InvalidPath):
                    pass

        add_id = list(paths_to_ids(add))
        mod_id = list(paths_to_ids(mod))
        rem_id = list(paths_to_ids(rem))
        return (add_id, mod_id, rem_id)

    def _u_any_in_string(self, str_list, string):
        """Return True if any of the strings in list are in string.
        Otherwise return False.
        """
        for txt in str_list:
            if txt in string:
                return True
        return False

    def _u_invoke(self, *args, **kwargs):
        if 'cwd' not in kwargs:
            kwargs['cwd'] = self.repo
        if 'encoding' not in kwargs:
            kwargs['encoding'] = self.encoding
        return invoke(*args, **kwargs)

    def _u_invoke_client(self, *args, **kwargs):
        cl_args = [self.client]
        cl_args.extend(args)
        return self._u_invoke(cl_args, **kwargs)

    def _u_search_parent_directories(self, path, filename):
        """Find the file (or directory) named filename in path or in any of
        path's parents.

        e.g.
          search_parent_directories("/a/b/c", ".be")
        will return the path to the first existing file from
          /a/b/c/.be
          /a/b/.be
          /a/.be
          /.be
        or None if none of those files exist.
        """  # pylint: disable=no-self-use
        try:
            ret = search_parent_directories(path, filename)
        except AssertionError:
            return None
        return ret

    def _u_find_id_from_manifest(self, id, manifest, revision=None):
        """Search for the relative path to id using manifest, a list of all
        files.
        
        Returns None if the id is not found.
        """
        be_dir = self._cached_path_id._spacer_dirs[0]
        be_dir_sep = self._cached_path_id._spacer_dirs[0] + os.path.sep
        files = [f for f in manifest if f.startswith(be_dir_sep)]
        for file in files:
            if not file.startswith(be_dir+os.path.sep):
                continue
            parts = file.split(os.path.sep)
            dir = parts.pop(0)  # don't add the first spacer dir
            for part in parts[:-1]:
                dir = os.path.join(dir, part)
                if dir not in files:
                    files.append(dir)
        for file in files:
            try:
                p_id = self._u_path_to_id(file)
                if p_id == id:
                    return file
            except (SpacerCollision, InvalidPath):
                pass
        raise InvalidID(id, revision=revision)

    def _u_find_id(self, id, revision):
        """Search for the relative path to id as of revision.

        Returns None if the id is not found.
        """
        assert self._rooted
        be_dir = self._cached_path_id._spacer_dirs[0]
        stack = [(be_dir, be_dir)]
        while stack:
            path, long_id = stack.pop()
            if long_id.endswith('/'+id):
                return path
            if not self._vcs_isdir(path, revision):
                continue
            for child in self._vcs_listdir(path, revision):
                stack.append((os.path.join(path, child),
                              '/'.join([long_id, child])))
        raise InvalidID(id, revision=revision)

    def _u_path_to_id(self, path):
        return self._cached_path_id.id(path)

    def _u_rel_path(self, path, root=None):
        """Return the relative path to path from root.

        Examples:

        >>> vcs = new()
        >>> vcs._u_rel_path("/a.b/c/.be", "/a.b/c")
        '.be'
        >>> vcs._u_rel_path("/a.b/c/", "/a.b/c")
        '.'
        >>> vcs._u_rel_path("/a.b/c/", "/a.b/c/")
        '.'
        >>> vcs._u_rel_path("./a", ".")
        'a'
        """
        if root is None:
            if self.repo is None:
                raise VCSNotRooted(self)
            root = self.repo

        path = os.path.abspath(path)
        abs_root = os.path.abspath(root)
        abs_root_slashed_dir = os.path.join(abs_root, "")
        if path in [abs_root, abs_root_slashed_dir]:
            return '.'
        elif not path.startswith(abs_root_slashed_dir):
            raise InvalidPath(path, abs_root_slashed_dir)

        return path[len(abs_root_slashed_dir):]

    def _u_abspath(self, path, root=None):
        """Return the absolute path from a path relative to root.

        Examples
        --------

        >>> vcs = new()
        >>> vcs._u_abspath(".be", "/a.b/c")
        '/a.b/c/.be'
        """
        if root is None:
            assert self.repo is not None, "VCS not rooted"
            root = self.repo
        return os.path.abspath(os.path.join(root, path))

    def _u_parse_commitfile(self, commitfile):
        """Split the commitfile created in self.commit() back into summary and
        header lines.
        """
        with codecs.open(commitfile, 'r', self.encoding) as f:
            summary = f.readline()
            body = f.read()
            body.lstrip('\n')
            if not body:
                body = None

        return (summary, body)

    def check_storage_version(self):
        version = self.storage_version()
        if version != libbe.storage.STORAGE_VERSION:
            msg = 'Unsupported version %s\n' +\
                  'Please use bugseverywhere version <1.2 to upgrade\n'
            raise Exception(msg % version)

    def storage_version(self, revision=None, path=None):
        """ Return the storage version of the on-disk files. """
        if path is None:
            path = os.path.join(self.repo, '.be', 'version')
        elif not os.path.exists(path):
            raise libbe.storage.InvalidStorageVersion(None)

        if revision is None:  # don't require connection
            return libbe.util.encoding.get_file_contents(
                path, decode=True).rstrip()

        relpath = self._u_rel_path(path)
        contents = self._vcs_get_file_contents(relpath, revision=revision)
        if not isinstance(contents, unicode):
            contents = unicode(contents, self.encoding)

        return contents.strip()

    def _setup_storage_version(self):
        """ Requires disk access.  """
        assert self._rooted
        path = os.path.join(self.be_dir, 'version')
        if not os.path.exists(path):
            libbe.util.encoding.set_file_contents(path,
                libbe.storage.STORAGE_VERSION+'\n')
            self._vcs_add(self._u_rel_path(path))


if libbe.TESTING:
    class VCSTestCase(unittest.TestCase):
        """
        Test cases for base VCS class (in addition to the Storage test
        cases).
        """

        Class = VCS

        def __init__(self, *args, **kwargs):
            super(VCSTestCase, self).__init__(*args, **kwargs)
            self.dirname = None

        def setUp(self):
            """ Set up test fixtures for Storage test case. """
            super(VCSTestCase, self).setUp()
            self.dir = Dir()
            self.dirname = self.dir.path
            self.s = self.Class(repo=self.dirname)
            if self.s.installed():
                self.s.init()
                self.s.connect()

        def tearDown(self):
            super(VCSTestCase, self).tearDown()
            if self.s.installed():
                self.s.disconnect()
                self.s.destroy()
            self.dir.cleanup()

    class VCS_installed_TestCase(VCSTestCase):
        def test_installed(self):
            """ See if the VCS is installed. """
            if not self.s.installed():
                self.skipTest('%(name)s VCS not found' % vars(self.Class))

    class VCS_detection_TestCase(VCSTestCase):
        def test_detection(self):
            """ See if the VCS detects its installed repository """
            if self.s.installed():
                self.s.disconnect()
                msg = 'Did not detected %(name)s VCS after initialising'
                self.failUnless(self.s._detect(self.dirname), msg
                                % vars(self.Class))
                self.s.connect()

        def test_no_detection(self):
            """ See if the VCS detects its installed repository """
            if self.s.installed() and self.Class.name != 'None':
                self.s.disconnect()
                self.s.destroy()
                msg = 'Detected %(name)s VCS before initialising'
                self.failUnless(not self.s._detect(self.dirname), msg
                                % vars(self.Class))
                self.s.init()
                self.s.connect()

        def test_vcs_repo_in_specified_root_path(self):
            """ VCS root directory should be in specified root path. """
            rp = os.path.realpath(self.s.repo)
            dp = os.path.realpath(self.dirname)
            vcs_name = self.Class.name
            self.failUnless(
                dp == rp or rp is None,
                "%(vcs_name)s VCS root in wrong dir (%(dp)s %(rp)s)" % vars())

    class VCS_get_user_id_TestCase(VCSTestCase):
        """ Test cases for VCS.get_user_id method. """

        def test_get_existing_user_id(self):
            """ Should get the existing user ID. """
            if self.s.installed():
                user_id = self.s.get_user_id()
                if user_id is None:
                    return
                _, email = libbe.ui.util.user.parse_user_id(user_id)
                if email is not None:
                    self.failUnless('@' in email, email)

    def make_vcs_testcase_subclasses(vcs_class, namespace):
        c = vcs_class()
        if c.installed():
            if c.versioned:
                libbe.storage.base.make_versioned_storage_testcase_subclasses(
                    vcs_class, namespace)
            else:
                libbe.storage.base.make_storage_testcase_subclasses(
                    vcs_class, namespace)

        if namespace != sys.modules[__name__]:
            # Make VCSTestCase subclasses for vcs_class in the namespace.
            vcs_testcase_classes = [c for c in (ob for ob in globals().values()
                                                if isinstance(ob, type))
                                    if issubclass(c, VCSTestCase)
                                    and c.Class == VCS]

            for base_class in vcs_testcase_classes:
                testcase_class_name = vcs_class.__name__ + base_class.__name__
                testcase_class_bases = (base_class,)
                testcase_class_dict = dict(base_class.__dict__)
                testcase_class_dict['Class'] = vcs_class
                testcase_class = type(testcase_class_name, testcase_class_bases,
                                      testcase_class_dict)
                setattr(namespace, testcase_class_name, testcase_class)

    make_vcs_testcase_subclasses(VCS, sys.modules[__name__])

    unitsuite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
