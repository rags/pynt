#!/usr/bin/python

from pynt import task

tasks_run = []
    
@task()
def clean(directory='/tmp'):
    tasks_run.append('clean[%s]' % repr(directory))

    
@task(clean)
def html():
    tasks_run.append('html')


@task()
def tests(*test_names):
    tasks_run.append('tests[%s]' % ','.join(map(repr, test_names)))


@task(clean)
def copy_file(from_, to, fail_on_error=True):
    tasks_run.append('copy_file[%s,%s,%s]' % (repr(from_), repr(to), repr(fail_on_error)))


@task(clean)
def start_server(port=80, debug=True):
    tasks_run.append('start_server[%s,%s]' % (repr(port), repr(debug)))

@task(ignore=True)
def ignored(file, contents):
    tasks_run.append('append_to_file[%s,%s]' % (repr(file), repr(contents)))

@task(clean, ignored)
def append_to_file(file, contents):
    tasks_run.append('append_to_file[%s,%s]' % (repr(file), repr(contents)))

    
@task(ignored)
def echo(*args,**kwargs):
    args_str = []
    if args:
        args_str.append(','.join(map(repr, args)))
    if kwargs:
        args_str.append(','.join("%s=%s" %  (kw, repr(kwargs[kw])) for kw in sorted(kwargs)))

    tasks_run.append('echo[%s]' % ','.join(args_str))
