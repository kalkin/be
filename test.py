# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Marien Zwart <marien.zwart@gmail.com>
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

import doctest
import os
import os.path
import pkgutil
import sys
import unittest

import libbe
libbe.TESTING = True
from libbe.version import version

def add_module_tests(suite, modname):
    try:
        mod = __import__(modname, fromlist="dummy")
    except ValueError as e:
        sys.stderr.write('Failed to import "{}"\n'.format(modname))
        raise e
    if hasattr(mod, 'suite'):
        s = mod.suite
    else:
        s = unittest.TestLoader().loadTestsFromModule(mod)
        try:
            sdoc = doctest.DocTestSuite(mod)
            suite.addTest(sdoc)
        except ValueError:
            pass
    suite.addTest(s)

if __name__ == '__main__':
    import optparse
    parser = optparse.OptionParser(usage='%prog [options] [modules ...]',
                                   description=
"""When called without optional module names, run the test suites for
*all* modules.  This may raise lots of errors if you haven't installed
one of the versioning control systems.

When called with module name arguments, only run the test suites from
those modules and their submodules.  For example::

    $ python test.py libbe.bugdir libbe.storage
""")
    parser.add_option('-q', '--quiet', action='store_true', default=False,
                      help='Run unittests in quiet mode (verbosity 1).')
    options,args = parser.parse_args()
    sys.stderr.write('Testing BE\n{}\n'.format(version(verbose=True)))

    verbosity = 2
    if options.quiet == True:
        verbosity = 1

    suite = unittest.TestSuite()
    package = libbe
    prefix = package.__name__ + "."

    for _, modname, __ in pkgutil.walk_packages(package.__path__, prefix):
        if args == [] or 'libbe' in args or modname in args:
            if not modname.startswith("libbe.interfaces.web.cfbe")\
            and not modname.startswith('libbe.storage.vcs.arch')\
            and not modname.startswith('libbe.storage.vcs.monotone'):
                add_module_tests(suite, modname)
    
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    
    numErrors = len(result.errors)
    numFailures = len(result.failures)
    numBad = numErrors + numFailures
    if numBad > 126:
        numBad = 1
    sys.exit(numBad)
