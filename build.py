#!/usr/bin/python

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
    subprocess.call(["pytest"] + list(args))

@task()
def generate_rst():
    
    subprocess.call(['pandoc', '-f', 'markdown', '-t', 'rst', '-o', 'README.rst', 'README.md'])

@task(generate_rst)
def upload():
    subprocess.call(['ssh-add', '~/.ssh/id_rsa'])
    subprocess.call(['python', 'setup.py', 'sdist', 'bdist_wininst', 'upload'])

__DEFAULT__ = test