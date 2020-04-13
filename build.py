#!/usr/bin/python

from __future__ import print_function

import subprocess
from pynt import task

@task()
def apidoc():
    """
    Generate API documentation using epydoc.
    """
    subprocess.call(["epydoc","--config","epydoc.config"])
    
@task()
def test(*args):
    """
    Run unit tests.
    """
    try:
        subprocess.call(["py.test-2.7"] + list(args))
    except FileNotFoundError:
        print("py.test-2.7 not found, trying generic name")
    try:
        subprocess.call(["py.test"] + list(args))
    except FileNotFoundError:
        print("py.test not found")
    try:
        subprocess.call(["py.test-3.3"] + list(args))
    except FileNotFoundError:
        print("py.test-3.3 not found, trying generic name")
    try:
        subprocess.call(["py.test3"] + list(args))
    except FileNotFoundError:
        print("py.test3 not found")


@task()
def generate_rst():
    
    subprocess.call(['pandoc', '-f', 'markdown', '-t', 'rst', '-o', 'README.rst', 'README.md'])

@task(generate_rst)
def upload():
    subprocess.call(['ssh-add', '~/.ssh/id_rsa'])
    subprocess.call(['python', 'setup.py', 'sdist', 'bdist_wininst', 'upload'])

__DEFAULT__ = test
