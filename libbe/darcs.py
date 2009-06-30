# Copyright (C) 2007 Chris Ball <chris@printf.net>,
#               2009 W. Trevor King <wking@drexel.edu>
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

import codecs
import os
import re
import sys
import unittest
import doctest

import rcs
from rcs import RCS

def new():
    return Darcs()

class Darcs(RCS):
    name="darcs"
    client="darcs"
    versioned=True
    def _rcs_help(self):
        status,output,error = self._u_invoke_client("--help")
        return output
    def _rcs_detect(self, path):
        if self._u_search_parent_directories(path, "_darcs") != None :
            return True
        return False 
    def _rcs_root(self, path):
        """Find the root of the deepest repository containing path."""
        # Assume that nothing funny is going on; in particular, that we aren't
        # dealing with a bare repo.
        if os.path.isdir(path) != True:
            path = os.path.dirname(path)
        darcs_dir = self._u_search_parent_directories(path, "_darcs")
        if darcs_dir == None:
            return None
        return os.path.dirname(darcs_dir)
    def _rcs_init(self, path):
        self._u_invoke_client("init", directory=path)
    def _rcs_get_user_id(self):
        # following http://darcs.net/manual/node4.html#SECTION00410030000000000000
        # as of June 29th, 2009
        if self.rootdir == None:
            return None
        darcs_dir = os.path.join(self.rootdir, "_darcs")
        if darcs_dir != None:
            for pref_file in ["author", "email"]:
                pref_path = os.path.join(darcs_dir, "prefs", pref_file)
                if os.path.exists(pref_path):
                    return self.get_file_contents(pref_path)
        for env_variable in ["DARCS_EMAIL", "EMAIL"]:
            if env_variable in os.environ:
                return os.environ[env_variable]
        return None
    def _rcs_set_user_id(self, value):
        if self.rootdir == None:
            self.root(".")
            if self.rootdir == None:
                raise rcs.SettingIDnotSupported
        author_path = os.path.join(self.rootdir, "_darcs", "prefs", "author")
        f = codecs.open(author_path, "w", self.encoding)
        f.write(value)
        f.close()
    def _rcs_add(self, path):
        if os.path.isdir(path):
            return
        self._u_invoke_client("add", path)
    def _rcs_remove(self, path):
        if not os.path.isdir(self._u_abspath(path)):
            os.remove(os.path.join(self.rootdir, path)) # darcs notices removal
    def _rcs_update(self, path):
        pass # darcs notices changes
    def _rcs_get_file_contents(self, path, revision=None, binary=False):
        if revision == None:
            return RCS._rcs_get_file_contents(self, path, revision,
                                              binary=binary)
        else:
            try:
                return self._u_invoke_client("show", "contents", "--patch", revision, path)
            except rcs.CommandError:
                # Darcs versions < 2.0.0pre2 lack the "show contents" command

                status,output,error = self._u_invoke_client("diff", "--unified",
                                                            "--from-patch",
                                                            revision, path)
                major_patch = output
                status,output,error = self._u_invoke_client("diff", "--unified",
                                                            "--patch",
                                                            revision, path)
                target_patch = output
                
                # "--output -" to be supported in GNU patch > 2.5.9
                # but that hasn't been released as of June 30th, 2009.

                # Rewrite path to status before the patch we want
                args=["patch", "--reverse", path]
                status,output,error = self._u_invoke(args, stdin=major_patch)
                # Now apply the patch we want
                args=["patch", path]
                status,output,error = self._u_invoke(args, stdin=target_patch)

                if os.path.exists(os.path.join(self.rootdir, path)) == True:
                    contents = RCS._rcs_get_file_contents(self, path,
                                                          binary=binary)
                else:
                    contents = ""

                # Now restore path to it's current incarnation
                args=["patch", "--reverse", path]
                status,output,error = self._u_invoke(args, stdin=target_patch)
                args=["patch", path]
                status,output,error = self._u_invoke(args, stdin=major_patch)
                current_contents = RCS._rcs_get_file_contents(self, path,
                                                              binary=binary)
                return contents
    def _rcs_duplicate_repo(self, directory, revision=None):
        if revision==None:
            RCS._rcs_duplicate_repo(self, directory, revision)
        else:
            self._u_invoke_client("put", "--no-pristine-tree",
                                  "--to-patch", revision, directory)
    def _rcs_commit(self, commitfile):
        id = self.get_user_id()
        if '@' not in id:
            id = "%s <%s@invalid.com>" % (id, id)
        # Darcs doesn't like commitfiles without trailing endlines.
        f = codecs.open(commitfile, 'r', self.encoding)
        contents = f.read()
        f.close()
        if contents[-1] != '\n':
            f = codecs.open(commitfile, 'a', self.encoding)
            f.write('\n')
            f.close()
        status,output,error = self._u_invoke_client('record', '--all',
                                                    '--author', id,
                                                    '--logfile', commitfile)
        revision = None

        revline = re.compile("Finished recording patch '(.*)'")
        match = revline.search(output)
        assert match != None, output+error
        assert len(match.groups()) == 1
        revision = match.groups()[0]
        return revision

    
rcs.make_rcs_testcase_subclasses(Darcs, sys.modules[__name__])

unitsuite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])