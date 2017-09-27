Bugs Everywhere
===============

|build-status| |read-the-docs| |coverage| |scrutinizer|

This is Bugs Everywhere (BE), a bugtracker built on distributed version
control.  It works with Bazaar, Darcs, Git, Mercurial, and Monotone
at the moment, but is easily extendable.  It can also function with no
VCS at all.

The idea is to package the bug information with the source code, so that
bugs can be marked "fixed" in the branches that fix them.  So, instead of
numbers, bugs have globally unique ids.


Getting BE
==========

BE is available as a Git repository::

    $ git clone https://github.com/kalkin/be.git be

See the documentation_ for details.  If you clone the Git repo, you'll
need to run::

    $ make

to build some auto-generated files (e.g. ``libbe/_version.py``), and::

    $ make install

to install BE.  By default BE will install into your home directory, but you can
tweak the ``INSTALL_OPTIONS`` variable in ``Makefile`` to install to another
location.

.. _documentation: http://bugs-everywhere.readthedocs.io/en/master


Getting started
===============

To get started, you must set the bugtracker root.  Typically, you will want to
set the bug root to your project root, so that Bugs Everywhere works in any
part of your project tree.::

    $ be init -r $PROJECT_ROOT

To create bugs, use ``be new $DESCRIPTION``.  To comment on bugs, you
can can use ``be comment $BUG_ID``.  To close a bug, use
``be close $BUG_ID`` or ``be status $BUG_ID fixed``.  For more
commands, see ``be help``.  You can also look at the usage examples in
``test_usage.sh``.


Documentation
=============

If ``be help`` isn't scratching your itch, the full documentation is
available in the doc directory as reStructuredText_ .  You can build
the full documentation with Sphinx_ , convert single files with
docutils_ , or browse through the doc directory by hand.
``doc/index.txt`` is a good place to start.  If you do use Sphinx,
you'll need to install numpydoc_ for automatically generating API
documentation.  See the ``NumPy/SciPy documentation guide``_ for an
introduction to the syntax.

.. _reStructuredText:
  http://docutils.sourceforge.net/docs/user/rst/quickref.html
.. _Sphinx: http://sphinx.pocoo.org/
.. _docutils: http://docutils.sourceforge.net/
.. _numpydoc: http://pypi.python.org/pypi/numpydoc
.. _NumPy/SciPy documentation guide:
  https://github.com/numpy/numpy/blob/master/doc/HOWTO_DOCUMENT.rst.txt

.. |build-status| image:: https://img.shields.io/travis/kalkin/be.svg?style=flat
    :alt: build status
    :scale: 100%
    :target: https://travis-ci.org/kalkin/be

.. |read-the-docs| image:: https://readthedocs.org/projects/bugs-everywhere/badge/?version=master
    :alt: Doc Build Status
    :scale: 100%
    :target: documentation_

.. |scrutinizer| image:: https://scrutinizer-ci.com/g/kalkin/be/badges/quality-score.png?b=master
   :target: https://scrutinizer-ci.com/g/kalkin/be/
   :alt: scrutinizer-ci.com

.. |coverage| image:: https://scrutinizer-ci.com/g/kalkin/be/badges/coverage.png?b=master
   :target: https://scrutinizer-ci.com/g/kalkin/be/
   :alt: scrutinizer-ci.com
