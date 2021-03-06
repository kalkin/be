# -*- coding: utf-8 -*-

# The MIT License (MIT)
# Copyright (C) 2017-2018 Bahtiar `kalkin-` Gadimov <bahtiar@gadimov.de>
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


"""Classes used by the unified diff parser to keep the diff data."""

from __future__ import unicode_literals

import codecs
import sys
import re


class UnidiffParseError(Exception):
    """Exception when parsing the unified diff data."""


RE_SOURCE_FILENAME = re.compile(
    r'^--- (?P<filename>[^\t\n]+)(?:\t(?P<timestamp>[^\n]+))?'
    '|^rename from (?P<renamefile>[^\t\n]+)$')
RE_TARGET_FILENAME = re.compile(
    r'^\+\+\+ (?P<filename>[^\t\n]+)(?:\t(?P<timestamp>[^\n]+))?'
    '|^rename to (?P<renamefile>[^\t\n]+)')

# @@ (source offset, length) (target offset, length) @@ (section header)
RE_HUNK_HEADER = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))?\ @@[ ]?(.*)")

#    kept line (context)
# \n empty line (treat like context)
# +  added line
# -  deleted line
# \  No newline case
RE_HUNK_BODY_LINE = re.compile(
    r'^(?P<line_type>[- \+\\])(?P<value>.*)', re.DOTALL)
RE_HUNK_EMPTY_BODY_LINE = re.compile(
    r'^(?P<line_type>[- \+\\]?)(?P<value>[\r\n]{1,2})', re.DOTALL)

RE_NO_NEWLINE_MARKER = re.compile(r'^\\ No newline at end of file')

DEFAULT_ENCODING = 'UTF-8'

LINE_TYPE_ADDED = '+'
LINE_TYPE_REMOVED = '-'
LINE_TYPE_CONTEXT = ' '
LINE_TYPE_EMPTY = ''
LINE_TYPE_NO_NEWLINE = '\\'
LINE_VALUE_NO_NEWLINE = ' No newline at end of file'


PY2 = sys.version_info[0] == 2
if PY2:
    # pylint: disable=invalid-name,unused-import
    from StringIO import StringIO
    open_file = codecs.open
    make_str = lambda x: x.encode(DEFAULT_ENCODING)

    def implements_to_string(cls):
        """ Workaround for python 2 """
        cls.__unicode__ = cls.__str__
        cls.__str__ = lambda x: x.__unicode__().encode(DEFAULT_ENCODING)
        return cls
else:
    from io import StringIO
    # pylint: disable=invalid-name,redefined-builtin
    open_file = open
    make_str = str
    implements_to_string = lambda x: x
    unicode = str
    basestring = str

# pylint: disable=missing-docstring,too-many-arguments,too-many-statements
# pylint: disable=too-many-instance-attributes,too-many-locals,too-many-branches


@implements_to_string
class Line(object):
    """A diff line."""

    def __init__(self, value, line_type,
                 source_line_no=None, target_line_no=None, diff_line_no=None):
        super(Line, self).__init__()
        self.source_line_no = source_line_no
        self.target_line_no = target_line_no
        self.diff_line_no = diff_line_no
        self.line_type = line_type
        self.value = value

    def __repr__(self):
        return make_str("<Line: %s>") % make_str(self)

    def __str__(self):
        return "%s%s" % (self.line_type, self.value)

    @property
    def is_added(self):
        return self.line_type == LINE_TYPE_ADDED

    @property
    def is_removed(self):
        return self.line_type == LINE_TYPE_REMOVED

    @property
    def is_context(self):
        return self.line_type == LINE_TYPE_CONTEXT


@implements_to_string
class Hunk(list):
    """Each of the modified blocks of a file."""

    def __init__(self, src_start=0, src_len=0, tgt_start=0, tgt_len=0,
                 section_header=''):
        super(Hunk, self).__init__()
        if src_len is None:
            src_len = 1
        if tgt_len is None:
            tgt_len = 1
        self.added = 0  # number of added lines
        self.removed = 0  # number of removed lines
        self.source = []
        self.source_start = int(src_start)
        self.source_length = int(src_len)
        self.target = []
        self.target_start = int(tgt_start)
        self.target_length = int(tgt_len)
        self.section_header = section_header

    def __repr__(self):
        value = "<Hunk: @@ %d,%d %d,%d @@ %s>" % (self.source_start,
                                                  self.source_length,
                                                  self.target_start,
                                                  self.target_length,
                                                  self.section_header)
        return make_str(value)

    def __str__(self):
        head = "@@ -%d,%d +%d,%d @@ %s\n" % (
            self.source_start, self.source_length,
            self.target_start, self.target_length, self.section_header)

        content = '\n'.join(unicode(line) for line in self)
        return head + content

    def append(self, line):
        """Append the line to hunk, and keep track of source/target lines."""
        super(Hunk, self).append(line)
        text = str(line)
        if line.is_added:
            self.added += 1
            self.target.append(text)
        elif line.is_removed:
            self.removed += 1
            self.source.append(text)
        elif line.is_context:
            self.target.append(text)
            self.source.append(text)

    def is_valid(self):
        """Check hunk header data matches entered lines info."""
        return (len(self.source) == self.source_length and
                len(self.target) == self.target_length)

    def source_lines(self):
        """Hunk lines from source file (generator)."""
        return (l for l in self if l.is_context or l.is_removed)

    def target_lines(self):
        """Hunk lines from target file (generator)."""
        return (l for l in self if l.is_context or l.is_added)


class PatchedFile(list):
    """Patch updated file, it is a list of Hunks."""

    def __init__(self, source='', target='', source_timestamp=None,
                 target_timestamp=None, rename=False):
        super(PatchedFile, self).__init__()
        self.source_file = source
        self.source_timestamp = source_timestamp
        self.target_timestamp = target_timestamp
        if source.startswith('old-')\
        and target.startswith('new-')\
        and source[4:] == target[4:]:
            self.source_file = source[4:].split('/', 1)[1]
            self.target_file = target[4:].split('/', 1)[1]
        else:
            self.source_file = source
            self.target_file = target
        self.is_renamed_file = rename

    def __repr__(self):
        return make_str("<PatchedFile: %s>") % make_str(self.path)

    def __str__(self):
        source = "--- %s\n" % self.source_file
        target = "+++ %s\n" % self.target_file
        hunks = '\n'.join(unicode(hunk) for hunk in self)
        return source + target + hunks

    def parse_hunk(self, header, diff, encoding):
        """Parse hunk details."""
        header_info = RE_HUNK_HEADER.match(header)
        hunk_info = header_info.groups()
        hunk = Hunk(*hunk_info)

        source_line_no = hunk.source_start
        target_line_no = hunk.target_start
        expected_source_end = source_line_no + hunk.source_length
        expected_target_end = target_line_no + hunk.target_length

        for diff_line_no, line in diff:
            if encoding is not None:
                line = line.decode(encoding)
            valid_line = RE_HUNK_BODY_LINE.match(line)
            if not valid_line:
                raise UnidiffParseError('Hunk diff line expected: %s' % line)

            line_type = valid_line.group('line_type')
            if line_type == LINE_TYPE_EMPTY:
                line_type = LINE_TYPE_CONTEXT
            value = valid_line.group('value')
            original_line = Line(value, line_type=line_type)
            if line_type == LINE_TYPE_ADDED:
                original_line.target_line_no = target_line_no
                target_line_no += 1
            elif line_type == LINE_TYPE_REMOVED:
                original_line.source_line_no = source_line_no
                source_line_no += 1
            elif line_type == LINE_TYPE_CONTEXT:
                original_line.target_line_no = target_line_no
                target_line_no += 1
                original_line.source_line_no = source_line_no
                source_line_no += 1
            else:
                original_line = None

            if original_line:
                original_line.diff_line_no = diff_line_no
                hunk.append(original_line)

            # if hunk source/target lengths are ok, hunk is complete
            if source_line_no == expected_source_end and\
                    target_line_no == expected_target_end:
                break

        self.append(hunk)

    @property
    def path(self):
        """Return the file path abstracted from VCS."""
        if (self.source_file.startswith('a/') and
                self.target_file.startswith('b/')):
            filepath = self.source_file[2:]
        elif (self.source_file.startswith('a/') and
              self.target_file == '/dev/null'):
            filepath = self.source_file[2:]
        elif (self.target_file.startswith('b/') and
              self.source_file == '/dev/null'):
            filepath = self.target_file[2:]
        else:
            filepath = self.source_file
        return filepath

    @property
    def added(self):
        """Return the file total added lines."""
        return sum([hunk.added for hunk in self])

    @property
    def removed(self):
        """Return the file total removed lines."""
        return sum([hunk.removed for hunk in self])

    @property
    def is_added_file(self):
        """Return True if this patch adds the file."""
        return self.is_renamed_file or (len(self) == 1 and
                                        self[0].source_start == 0 and
                                        self[0].source_length == 0)

    @property
    def is_removed_file(self):
        """Return True if this patch removes the file."""
        return self.is_renamed_file or (len(self) == 1 and
                                        self[0].target_start == 0 and
                                        self[0].target_length == 0)

    @property
    def is_modified_file(self):
        """Return True if this patch modifies the file."""
        return not (self.is_added_file or self.is_removed_file)


@implements_to_string
class PatchSet(list):
    """A list of PatchedFiles."""

    def __init__(self, f, encoding=None):
        super(PatchSet, self).__init__()
        # make sure we pass an iterator object to parse
        data = iter(f)
        # if encoding is None, assume we are reading unicode data
        self._parse(data, encoding=encoding)

    def __repr__(self):
        return make_str('<PatchSet: %s>') % super(PatchSet, self).__repr__()

    def __str__(self):
        return '\n'.join(unicode(patched_file) for patched_file in self)

    def _parse(self, diff, encoding):
        current_file = None

        diff = enumerate(diff, 1)
        rename = False
        for _, line in diff:
            if encoding is not None:
                line = line.decode(encoding)
            # check for source file header
            is_source_filename = RE_SOURCE_FILENAME.match(line)
            if is_source_filename:
                source_file = is_source_filename.group('filename')
                if source_file:
                    rename = False
                else:
                    source_file = is_source_filename.group('renamefile')
                    rename = True
                source_timestamp = is_source_filename.group('timestamp')
                # reset current file
                current_file = None
                continue

            # check for target file header
            is_target_filename = RE_TARGET_FILENAME.match(line)
            if is_target_filename:
                if current_file is not None:
                    raise UnidiffParseError('Target without source: %s' % line)
                target_file = is_target_filename.group('filename')
                if not target_file:
                    target_file = is_target_filename.group('renamefile')
                target_timestamp = is_target_filename.group('timestamp')
                # add current file to PatchSet
                current_file = PatchedFile(source_file, target_file,
                                           source_timestamp, target_timestamp,
                                           rename=rename)
                self.append(current_file)
                continue

            # check for hunk header
            is_hunk_header = RE_HUNK_HEADER.match(line)
            if is_hunk_header:
                if current_file is None:
                    raise UnidiffParseError('Unexpected hunk found: %s' % line)
                current_file.parse_hunk(line, diff, encoding)

    @classmethod
    def from_filename(cls, filename, encoding=DEFAULT_ENCODING, errors=None):
        """Return a PatchSet instance given a diff filename."""
        with open_file(filename, 'r', encoding=encoding, errors=errors) as _:
            instance = cls(_)
        return instance

    @property
    def added_files(self):
        """Return patch added files as a list."""
        return [f for f in self if f.is_added_file]

    @property
    def removed_files(self):
        """Return patch removed files as a list."""
        return [f for f in self if f.is_removed_file]

    @property
    def modified_files(self):
        """Return patch modified files as a list."""
        return [f for f in self if f.is_modified_file]

    @property
    def changed_files(self):
        added = []
        modified = []
        removed = []
        for patch in self:
            if patch.is_renamed_file:
                removed.append(patch.source_file)
                added.append(patch.target_file)
            elif patch.is_added_file:
                added.append(patch.path)
            elif patch.is_modified_file:
                modified.append(patch.path)
            elif patch.is_removed_file:
                removed.append(patch.path)
            else:
                raise SystemError("This should not happen")

        return (set(added), set(modified), set(removed))

    @staticmethod
    def _convert_string(data, encoding=None, errors='strict'):
        """Return a PatchSet instance given a diff string."""
        if encoding is not None:
            # if encoding is given, assume bytes and decode
            data = unicode(data, encoding=encoding, errors=errors)
        return StringIO(data)

    @classmethod
    def from_string(cls, data, encoding=None, errors='strict'):
        return cls(cls._convert_string(data, encoding, errors))
