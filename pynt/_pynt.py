"""
Lightweight Python Build Tool

"""

import inspect
import argparse
import logging
import os
from os import path
import re
import imp
import sys
from pynt import __version__

_CREDIT_LINE = "Powered by pynt %s - A Lightweight Python Build Tool." % __version__
_LOGGING_FORMAT = "[ %(name)s - %(message)s ]"
_TASK_PATTERN = re.compile("^([^\[]+)(\[([^\]]*)\])?$")
#"^([^\[]+)(\[([^\],=]*(,[^\],=]+)*(,[^\],=]+=[^\],=]+)*)\])?$"
def build(args):
    """
    Build the specified module with specified arguments.
    
    @type module: module
    @type args: list of arguments
    """
    # Build the command line.
    parser = _create_parser()

    #No args passed. 
    #if not args: #todo: execute default task.
    #    parser.print_help()
    #    print("\n\n"+_CREDIT_LINE)
    #    exit
    # Parse arguments.
    args = parser.parse_args(args)

    if args.version:
        print('pynt %s' % __version__)
        sys.exit(0)
        
    #load build file as a module
    module = _load_buildscript(args.file)
    
    # Run task and all its dependencies.
    if args.list_tasks:
        print_tasks(module, args.file)
    elif not args.tasks:
        if not _run_default_task(module):
            parser.print_help()
            print("\n")
            print_tasks(module,  args.file)
    else:
        _run_from_task_names(module,args.tasks)

def print_tasks(module, file):
    # Get all tasks.
    tasks = _get_tasks(module)
    
    # Build task_list to describe the tasks.
    task_list = "Tasks in build file %s:" % file
    name_width = _get_max_name_length(module)+4
    task_help_format = "\n  {0:<%s} {1: ^10} {2}" % name_width
    default = _get_default_task(module)
    for task in sorted(tasks, key=lambda task: task.name):
        attributes = []
        if task.ignored:
            attributes.append('Ignored')
        if default and task.name == default.name:
            attributes.append('Default')
    
        task_list += task_help_format.format(task.name,
                                            ('[' + ', '.join(attributes) + ']')
                                             if attributes else '', 
                                             task.doc)
    print(task_list + "\n\n"+_CREDIT_LINE)

def _load_buildscript(file_path):
    if not path.isfile(file_path):
        print("Build file '%s' does not exist. Please specify a build file\n" % file_path) 
        parser.print_help()
        sys.exit(1)

    script_dir, script_base = path.split(file_path)

    # Append directory of build script to path, to allow importing modules relatively to the script
    sys.path.append(path.abspath(script_dir))

    module_name, suffix = path.splitext(script_base)
    description = (suffix, 'r', imp.PY_SOURCE)

    with open(file_path, 'r') as script_file:
        return imp.load_module(module_name, script_file, file_path, description)

def _match_task_names_heuristically(module) -> bool:
    for name, value in inspect.getmembers(module, lambda v: isinstance(v, str)):
        if name == '__TASK_NAME_RESOLVER__':
            return value.strip().lower() != 'strict'
    return True

def _get_default_task(module):
    matching_tasks = [task for name,task in inspect.getmembers(module,Task.is_task)
                      if name == "__DEFAULT__"]
    if matching_tasks:
        return matching_tasks[0]
    
def _run_default_task(module):
    default_task = _get_default_task(module)
    if not default_task:
        return False
    _run(module, _get_logger(module), default_task, set())
    return True


def _run_from_task_names(module,task_names):
    """
    @type module: module
    @type task_name: string
    @param task_name: Task name, exactly corresponds to function name.
    """
    # Create logger.
    logger = _get_logger(module)
    all_tasks = _get_tasks(module)
    completed_tasks = set([])
    for task_name in task_names:
        task, args, kwargs= _get_task(module, task_name, all_tasks)
        _run(module, logger, task, completed_tasks, True, args, kwargs)

def _get_task(module, name, tasks):
    # Get all tasks.
    match = _TASK_PATTERN.match(name)
    if not match:
        raise Exception("Invalid task argument %s" % name)
    task_name, _, args_str = match.groups()
    
    args, kwargs= _parse_args(args_str)
    if hasattr(module, task_name):
        return getattr(module, task_name), args, kwargs

    if _match_task_names_heuristically(module):
        matching_tasks = [task for task in tasks if task.name.startswith(task_name)]
        if len(matching_tasks) == 1:
            return matching_tasks[0], args, kwargs
        elif len(matching_tasks) > 1:
            raise Exception("Conflicting matches %s for task %s" % (
                ', '.join([task.name for task in matching_tasks]), task_name
            ))
    raise Exception("Invalid task '%s'. Task should be one of %s" %
            (name, 
            ', '.join([task.name for task in tasks])))

def _parse_args(args_str):
    args = []
    kwargs = {}
    if not args_str:
        return args, kwargs
    arg_parts = args_str.split(",")

    for i, part in enumerate(arg_parts):
        if "=" in part:
            key, value = [_str.strip() for _str in part.split("=")]
            if key in kwargs:
                raise Exception("duplicate keyword argument %s" % part)
            kwargs[key] = value
        else:
            if len(kwargs) > 0:
                raise Exception("Non keyword arg %s cannot follows a keyword arg %s"
                                % (part, arg_parts[i - 1]))
            args.append(part.strip())
    return args, kwargs
    
def _run(module, logger, task, completed_tasks, from_command_line = False, args = None, kwargs = None):
    """
    @type module: module
    @type logging: Logger
    @type task: Task
    @type completed_tasts: set Task
    @rtype: set Task
    @return: Updated set of completed tasks after satisfying all dependencies.
    """
    # Satsify dependencies recursively. Maintain set of completed tasks so each
    # task is only performed once.
    for dependency in task.dependencies:
        completed_tasks = _run(module,logger,dependency,completed_tasks)

    # Perform current task, if need to.
    if from_command_line or task not in completed_tasks:

        if task.ignored:
        
            logger.info("Ignoring task \"%s\"" % task.name)
            
        else:

            logger.info("Starting task \"%s\"" % task.name)

            try:
                # Run task.
                task(*(args or []),**(kwargs or {}))
            except:
                logger.critical("Error in task \"%s\"" % task.name)
                logger.critical("Aborting build")
                raise
            
            logger.info("Completed task \"%s\"" % task.name)
        
        completed_tasks.add(task)
    
    return completed_tasks

def _create_parser():
    """
    @rtype: argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("tasks", help="perform specified task and all its dependencies",
                        metavar="task", nargs = '*')
    parser.add_argument('-l', '--list-tasks', help = "List the tasks",
                        action =  'store_true')
    parser.add_argument('-v', '--version',
                        help = "Display the version information",
                        action =  'store_true')
    parser.add_argument('-f', '--file',
                        help = "Build file to read the tasks from. 'build.py' is default value assumed if this argument is unspecified",
                        metavar = "file", default =  "build.py")
    
    return parser
        
# Abbreviate for convenience.
#task = _TaskDecorator
def task(*dependencies, **options):
    for i, dependency in enumerate(dependencies):
        if not Task.is_task(dependency):
                if inspect.isfunction(dependency):
                    # Throw error specific to the most likely form of misuse.
                    if i == 0:
                        raise Exception("Replace use of @task with @task().")
                    else:
                        raise Exception("%s is not a task. Each dependency should be a task." % dependency)
                else:
                    raise Exception("%s is not a task." % dependency)

    def decorator(fn):
        return Task(fn, dependencies, options)
    return decorator

class Task(object):
    
    def __init__(self, func, dependencies, options):
        """
        @type func: 0-ary function
        @type dependencies: list of Task objects
        """
        self.func = func
        self.name = func.__name__
        self.doc = inspect.getdoc(func) or ''
        self.dependencies = dependencies
        self.ignored =  bool(options.get('ignore', False))

    def show(self):
        return not self.name.startswith("_")
    
    def __call__(self,*args,**kwargs):
        self.func.__call__(*args,**kwargs)
    
    @classmethod
    def is_task(cls,obj):
        """
        Returns true is an object is a build task.
        """
        return isinstance(obj,cls)
    
def _get_tasks(module):
    """
    Returns all functions marked as tasks.
    
    @type module: module
    """
    # Get all functions that are marked as task and pull out the task object
    # from each (name,value) pair.
    return set(member[1] for member in inspect.getmembers(module,Task.is_task) if member[1].show())
    
def _get_max_name_length(module):
    """
    Returns the length of the longest task name.
    
    @type module: module
    """
    return max([len(task.name) for task in _get_tasks(module)])
    
def _get_logger(module):
    """
    @type module: module
    @rtype: logging.Logger
    """

    # Create Logger
    logger = logging.getLogger(os.path.basename(module.__file__))
    logger.setLevel(logging.DEBUG)

    # Create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # Create formatter
    formatter = logging.Formatter(_LOGGING_FORMAT)

    # Add formatter to ch
    ch.setFormatter(formatter)

    # Add ch to logger
    logger.addHandler(ch)

    return logger

def main():
    build(sys.argv[1:])
