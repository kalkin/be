#!/usr/bin/env python
#
# Copyright

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
        'docopt',
        'Jinja2 (>=2.6)',
        'CherryPy (>=3.2)',
        'semver'
        ]
    )
