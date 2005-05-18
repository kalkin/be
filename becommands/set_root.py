# Copyright (C) 2005 Aaron Bentley and Panometrics, Inc.
# <abentley@panoramicfeedback.com>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Assign the root directory for bug tracking"""
from libbe import bugdir, cmdutil, rcs

def execute(args):
    """
    >>> from libbe import tests
    >>> import os
    >>> dir = tests.Dir()
    >>> try:
    ...     bugdir.tree_root(dir.name)
    ... except bugdir.NoBugDir, e:
    ...     True
    True
    >>> execute([dir.name])
    No revision control detected.
    Directory initialized.
    >>> bd = bugdir.tree_root(dir.name)
    >>> bd.root = dir.name
    >>> dir = tests.arch_dir()
    >>> os.chdir(dir.name)
    >>> execute('.')
    Using Arch for revision control.
    Directory initialized.
    >>> bd = bugdir.tree_root(dir.name+"/{arch}")
    >>> bd.root = dir.name
    >>> tests.clean_up()
    >>> execute(('/highly-unlikely-to-exist',))
    Traceback (most recent call last):
    UserError: No such directory: /highly-unlikely-to-exist
    """
    if len(args) != 1:
        raise cmdutil.UserError("Please supply a directory path")
    dir_rcs = rcs.detect(args[0])
    if dir_rcs.name is not "None":
        print "Using %s for revision control." % dir_rcs.name
    else:
        print "No revision control detected."
    try:
        bugdir.create_bug_dir(args[0], dir_rcs)
    except bugdir.NoRootEntry:
        raise cmdutil.UserError("No such directory: %s" % args[0])
    print "Directory initialized."
