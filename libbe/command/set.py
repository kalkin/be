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

""" Bugs Everywhere - Show/Set bug directory settings

Usage:
    be set [-b DIR] [SETTING [VALUE]]

Options:
   -b ID, --bugdir=ID  Short bugdir UUID to act on.  You only need to set this
                       if you have multiple bugdirs in your repository.


 If name and value are supplied, the name is set to a new value.
 If no value is specified, the current value is printed.
 If no arguments are provided, all names and values are listed.

 To unset a setting, set it to "none".

 Allowed settings are:

 %s

 active_status
   The allowed active bug states and their descriptions.  This property
   defaults to None.
 extra_strings
   Space for an array of extra strings.  Useful for storing state for
   functionality implemented purely in becommands/<some_function>.py.
   This property defaults to [].  This property is checked with
   <function _extra_strings_check_fn at 0x7473402a5668>.
 inactive_status
   The allowed inactive bug states and their descriptions.  This
   property defaults to None.
 severities
   The allowed bug severities and their descriptions.  This property
   defaults to None.
 target
   The current project development target.  This property defaults to
   None.

 Note that this command does not provide a good interface for some of
 these settings (yet!).  You may need to edit the bugdir settings file
 (`.be/<bugdir>/settings`) manually.  Examples for each troublesome
 setting are given below.

 Add the following lines to override the default severities and use
 your own:

   severities:
     - - target
       - The issue is a target or milestone, not a bug.
     - - wishlist
       - A feature that could improve usefulness, but not a bug.

 You may add as many name/description pairs as you wish to have; they
 are sorted in order from least important at the top, to most important
 at the bottom.  The target severity gets special handling by `be
 target`.

 Note that the values here _override_ the defaults. That means that if
 you like the defaults, and wish to keep them, you will have to copy
 them here before adding any of your own.  See `be severity --help` for
 the current list.

 Add the following lines to override the default statuses and use your
 own:

   active_status:
     - - unconfirmed
       - A possible bug which lacks independent existence confirmation.
"""

import textwrap

from docopt import docopt

import libbe
import libbe.bugdir
import libbe.command
import libbe.command.util
from libbe.storage.util.settings_object import EMPTY


class Set(libbe.command.Command):
    """Change bug directory settings

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bd.storage)
    >>> cmd = Set(ui=ui)

    >>> ui.setup_command(cmd)

    >>> ret = cmd.run(['target'])
    None
    >>> ret = cmd.run(['target', 'abcdefg'])
    >>> ret = cmd.run(['target'])
    abcdefg
    >>> ret = cmd.run(['target', 'none'])
    >>> ret = cmd.run(['target'])
    None
    >>> ui.cleanup()
    >>> bd.cleanup()
    """
    name = 'set'

    def run(self, args=None):
        args = args or []
        params = docopt(__doc__ % ('\n'.join(get_bugdir_settings())),
                        argv=[Set.name] + args)
        bugdirs = self._get_bugdirs()  # pylint: disable=no-member
        if params['--bugdir']:
            bugdir = bugdirs[params['--bugdir']]
        elif len(bugdirs) == 1:
            bugdir = bugdirs.values()[0]
        else:
            raise libbe.command.UserError(
                'Ambiguous bugdir {}'.format(sorted(bugdirs.values())))
        if params['SETTING'] is None:
            keys = bugdir.settings_properties
            keys.sort()
            for key in keys:
                # pylint: disable=no-member
                print >> self.stdout, \
                    '%16s: %s' % (key, _value_string(bugdir, key))
            return 0
        if params['SETTING'] not in bugdir.settings_properties:
            msg = 'Invalid setting %s\n' % params['SETTING']
            msg += 'Allowed settings:\n  '
            msg += '\n  '.join(bugdir.settings_properties)
            raise libbe.command.UserError(msg)
        if params['VALUE'] is None:
            print _value_string(bugdir, params['SETTING'])
        else:
            if params['VALUE'] == 'none':
                params['VALUE'] = EMPTY
            # pylint: disable=protected-access
            attr = bugdir._setting_name_to_attr_name(params['SETTING'])
            setattr(bugdir, attr, params['VALUE'])
        return 0


def get_bugdir_settings():  # pylint: disable=missing-docstring
    settings = []
    for setting in libbe.bugdir.BugDir.settings_properties:
        settings.append(setting)
    settings.sort()
    documented_settings = []
    for setting in settings:
        _set = getattr(libbe.bugdir.BugDir, setting)
        dstr = _set.__doc__.strip()
        # per-setting comment adjustments
        if setting == 'vcs_name':
            lines = dstr.split('\n')
            while not lines[0].startswith('This property defaults to'):
                lines.pop(0)
            assert len(lines) is not None, \
                'Unexpected vcs_name docstring:\n  "%s"' % dstr
            lines.insert(
                0, 'The name of the revision control system to use.\n')
            dstr = '\n'.join(lines)
        doc = textwrap.wrap(dstr, width=70, initial_indent='  ',
                            subsequent_indent='  ')
        documented_settings.append('%s\n%s' % (setting, '\n'.join(doc)))
    return documented_settings


def _value_string(bugdir, setting):
    val = bugdir.settings.get(setting, EMPTY)
    if val == EMPTY:
        # pylint: disable=protected-access
        default = getattr(bugdir, bugdir._setting_name_to_attr_name(setting))
        if default not in [None, EMPTY]:
            val = 'None (%s)' % default
        else:
            val = None
    return str(val)
