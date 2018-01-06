#!/usr/bin/env python
#
# Copyright (C) 2006-2017 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Anand Aiyer <aaiyer@gmail.com>
#                         Gianluca Montecchi <gian@grys.it>
#                         Jelmer Vernooij <jelmer@samba.org>
#                         Kalkin <bahtiar@gadimov.de>
#                         Marien Zwart <marien.zwart@gmail.com>
#                         Niall Douglas (s_sourceforge@nedprod.com) <spam@spamtrap.com>
#                         Thomas Levine <occurrence@thomaslevine.com>
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

from distutils.core import setup
import os.path

from libbe import version


_this_dir = os.path.dirname(__file__)

rev_id = version.version_info['revision']
rev_date = version.version_info['date']

data_files = []

man_path = os.path.join('doc', 'man', 'be.1')
if os.path.exists(man_path):
    data_files.append(('share/man/man1', [man_path]))

setup(
    name='bugs-everywhere',
    version='{}'.format(version.version()),
    maintainer='Bahtiar `kalkin` Gadimov',
    maintainer_email='bahtiar@gadimov.de',
    url='https://github.com/kalkin/be',
    download_url=('https://github.com/kalkin/be/archive/v{}.tar.gz'
                  .format(version.version())),
    license='GNU General Public License (GPL)',
    platforms=['all'],
    description='Bugtracker supporting distributed revision control',
    long_description=open(os.path.join(_this_dir, 'README.rst'), 'r').read(),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Framework :: CherryPy',
        'Intended Audience :: Customer Service',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Bug Tracking',
        ],
    packages=['libbe',
              'libbe.command',
              'libbe.storage',
              'libbe.storage.util',
              'libbe.storage.vcs',
              'libbe.ui',
              'libbe.ui.util',
              'libbe.util',
              'libbe.interfaces',
              'libbe.interfaces.web'],
    package_data={'libbe.interfaces.web': ['templates/*.html',
                                           'static/**/*.js',
                                           'static/**/*.css']},
    entry_points={
        'console_scripts': {
            'be = libbe.ui.command_line:main'
            }
        },
    data_files=data_files,
    requires=[
        'Jinja2 (>=2.6)',
        'CherryPy (>=3.2)',
        'semver'
        ]
    )
