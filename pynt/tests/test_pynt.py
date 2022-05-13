import pytest
import re
from pynt import _pynt, main
import sys
if sys.version.startswith("3."):
    from io import StringIO as SOut
else:
    from StringIO import StringIO as SOut

import os
from os import path
import imp

def fpath(mod):
    return path.splitext(mod.__file__)[0] + '.py'

    
def simulate_dynamic_module_load(mod):
    file_path = fpath(mod)

    #sys.path.append(path.abspath(script_dir))

    module_name, suffix = path.splitext(path.basename(file_path))
    description = (suffix, 'r', imp.PY_SOURCE)

    with open(file_path, 'r') as scriptfile:
        return imp.load_module(module_name, scriptfile, file_path, description)

def reset_build_file(mod):
    mod.tasks_run = []
def build(mod, params=None, init_mod = reset_build_file):
    dynamically_loaded_mod = simulate_dynamic_module_load(mod)
    dynamically_loaded_mod.tasks_run = []
    sys.argv = ['pynt', '-f', fpath(mod)] + (params or [])
    main()
    return dynamically_loaded_mod

class TestParseArgs:
    def test_parsing_commandline(self):
        args = _pynt._create_parser().parse_args(['-f', "foo.py", "task1", "task2"])
        assert "foo.py" == args.file
        assert not args.list_tasks
        assert ['task1', 'task2'] == args.tasks

    def test_parsing_commandline_help(self):
        assert _pynt._create_parser().parse_args(["-l"]).list_tasks
        assert _pynt._create_parser().parse_args([ "--list-tasks"]).list_tasks

    def test_parsing_commandline_build_file(self):
        assert "some_file" == _pynt._create_parser().parse_args(["-f", "some_file"]).file
        assert "build.py" == _pynt._create_parser().parse_args([]).file
        assert "/foo/bar" == _pynt._create_parser().parse_args(
            ["--file", "/foo/bar"]).file
        
        
        with pytest.raises(SystemExit):
            _pynt._create_parser().parse_args(["--file"])
        with pytest.raises(SystemExit):
            _pynt._create_parser().parse_args(["-f"])

class TestBuildSimple:
        
    def test_get_tasks(self):
        from .build_scripts import simple
        ts = _pynt._get_tasks(simple)
        assert len(ts) == 5
        
class TestBuildWithDependencies:
        
    def test_get_tasks(self):
        from .build_scripts import dependencies
        tasks = _pynt._get_tasks(dependencies)#private tasks are not in this list
        assert len(tasks) == 5
        assert 4 == len([task for task in tasks if task.name == 'android'][0].dependencies)
        assert 4 == len([task for task in tasks if task.name == 'ios'][0].dependencies)

    def test_dependencies_for_imported(self):
        from .build_scripts import default_task_and_import_dependencies
        tasks = _pynt._get_tasks(default_task_and_import_dependencies)
        assert 7 == len(tasks)
        assert [task for task in tasks if task.name == 'clean']
        assert [task for task in tasks if task.name == 'local_task']
        assert [task for task in tasks if task.name == 'android']
        assert 3 == len([task for task in tasks
                         if task.name == 'task_with_imported_dependencies'][0].dependencies)
        

    def test_dependencies_that_are_imported_e2e(self):
        from .build_scripts import default_task_and_import_dependencies
        def mod_init(mod):
            mod.tasks_run = []
            mod.build_with_params.tasks_run = []
        module = build(default_task_and_import_dependencies,
                       ["task_with_imported_dependencies"], init_mod = mod_init)
        assert module.tasks_run == ['local_task', 'task_with_imported_dependencies']
        assert module.build_with_params.tasks_run == ['clean[/tmp]', 'html']

class TestDecorationValidation:

    def test_task_without_braces(self):
        with pytest.raises(Exception) as exc:
            from .build_scripts import annotation_misuse_1
        assert 'Replace use of @task with @task().' in str(exc.value)

    def test_dependency_not_a_task(self):
        with pytest.raises(Exception) as exc:
            from .build_scripts import annotation_misuse_2
        assert re.findall('function html.* is not a task.', str(exc.value))

    def test_dependency_not_a_function(self):
        with pytest.raises(Exception) as exc:
            from .build_scripts import annotation_misuse_3
        assert '1234 is not a task.' in str(exc.value)


import contextlib
@contextlib.contextmanager
def mock_stdout():
    oldout, olderr =  sys.stdout,  sys.stderr
    try:
        out = [SOut(),  SOut()]
        sys.stdout, sys.stderr =  out
        yield out
    finally:
        sys.stdout, sys.stderr =  oldout,  olderr
        out[0] =  out[0].getvalue()
        out[1] =  out[1].getvalue()
                                                                                
        
class TestOptions:

    @pytest.fixture
    def module(self):
        from .build_scripts import options as module
        self.docs = {'clean': '', 'html': 'Generate HTML.',
                     'images': '''Prepare images.\n\nShould be ignored.''',
                     'android': 'Package Android app.'}
        return module
        
    def test_ignore_tasks(self, module):
        module = build(module,["android"])
        assert ['clean', 'html', 'android'] == module.tasks_run

    def test_docs(self, module):
        tasks = _pynt._get_tasks(module)
        assert 4 == len(tasks)
        
        for task_ in tasks:
            assert task_.name in self.docs
            assert self.docs[task_.name] == task_.doc

    @pytest.mark.parametrize('args', [['-l'], ['--list-tasks'], []])
    def test_list_docs(self, module, args):
        with mock_stdout() as out: 
            build(module,args)
        stdout = out[0]
        tasks = _pynt._get_tasks(module)
        for task in tasks:
            if task.ignored:
                assert re.findall('%s\s+%s\s+%s' % (task.name,"\[Ignored\]", task.doc), stdout)
            else:
                assert re.findall('%s\s+%s' % (task.name, task.doc), stdout)
            

            
class TestRuntimeError:

    def test_stop_on_exception(self):
        from .build_scripts import runtime_error as re
        with pytest.raises(IOError):
            build(re,["android"])
        mod = simulate_dynamic_module_load(re)
        assert mod.ran_images
        assert not hasattr(mod, 'ran_android')
        
    def test_exception_on_invalid_task_name(self):
        from .build_scripts import build_with_params
        with pytest.raises(Exception) as exc:
            build(build_with_params,["doesnt_exist"])
            
            assert 'task should be one of append_to_file, clean' \
                ', copy_file, echo, html, start_server, tests' in str(exc.value)


class TestPartialTaskNames:
    def setup_method(self,method):
        from .build_scripts import build_with_params
        self._mod = build_with_params

        
    def test_with_partial_name(self):
        mod = build(self._mod, ["cl"])
        assert ['clean[/tmp]'] ==  mod.tasks_run
        
    def test_with_partial_name_and_dependencies(self):
        mod = build(self._mod, ["htm"])
        assert ['clean[/tmp]','html'] ==  mod.tasks_run

    def test_exception_on_conflicting_partial_names(self):
        with pytest.raises(Exception) as exc:
            build(self._mod, ["c"])
        assert ('Conflicting matches clean, copy_file for task c' in str(exc.value) or
                'Conflicting matches copy_file, clean for task c' in str(exc.value))


class TestStrictTaskNames:

    def setup_method(self):
        from .build_scripts import build_with_strict_task_names
        self._mod = build_with_strict_task_names

    def test_task_resolver_statement(self):
        assert False == _pynt._match_task_names_heuristically(self._mod)
        
    def test_exception_on_partial_task_name(self):
        with pytest.raises(Exception) as exc:
            build(self._mod, ["c"])
        assert 'Invalid task \'c\'' in str(exc.value)

    def test_with_valid_task_name_and_dependencies(self):
        mod = build(self._mod, ["html"])
        assert ['clean[/tmp]','html'] ==  mod.tasks_run


class TestDefaultTask:
        def test_simple_default_task(self):
            from .build_scripts import simple
            assert _pynt._run_default_task(simple) #returns false if no default task

        def test_module_with_defaults_which_imports_other_files_with_defaults(self):
            from .build_scripts import default_task_and_import_dependencies
            mod = build(default_task_and_import_dependencies)
            assert 'task_with_imported_dependencies' in mod.tasks_run



class TestMultipleTasks:
    def setup_method(self,method):
        from .build_scripts import build_with_params
        self._mod = build_with_params

    def test_dependency_is_run_only_once_unless_explicitly_invoked_again(self):
        mod = build(self._mod, ["clean", "html", 'tests', "clean"])
        assert ['clean[/tmp]', "html", "tests[]", "clean[/tmp]"] == mod.tasks_run
        
    def test_multiple_partial_names(self):
        assert ['clean[/tmp]', "html"] == build(self._mod, ["cl", "htm"]).tasks_run



class TesttaskArguments:
    def setup_method(self,method):
        from .build_scripts import build_with_params
        self._mod = build_with_params
        self._mod.tasks_run = []

    def test_passing_optional_params_with_dependencies(self):
        mod = build(self._mod, ["clean[~/project/foo]",
                                     'append_to_file[/foo/bar,ABCDEF]',
                                     "copy_file[/foo/bar,/foo/blah,False]",
                                     'start_server[8080]'])
        assert ["clean[~/project/foo]",  'append_to_file[/foo/bar,ABCDEF]', 
                "copy_file[/foo/bar,/foo/blah,False]", 'start_server[8080,True]'
            ] == mod.tasks_run
        
    def test_invoking_varargs_task(self):
        mod = build(self._mod, ['tests[test1,test2,test3]'])
        assert ['tests[test1,test2,test3]'] == mod.tasks_run

    def test_partial_name_with_args(self):

        mod = build(self._mod, ['co[foo,bar]','star'])
        assert ['clean[/tmp]','copy_file[foo,bar,True]', 'start_server[80,True]'
            ] == mod.tasks_run


    def test_passing_keyword_args(self):
        mod = build(self._mod, ['co[to=bar,from_=foo]','star[80,debug=False]', 'echo[foo=bar,blah=123]'])

        assert ['clean[/tmp]','copy_file[foo,bar,True]',
                'start_server[80,False]',
                'echo[blah=123,foo=bar]'] == mod.tasks_run



    def test_passing_varargs_and_keyword_args(self):
        assert (['echo[1,2,3,some_str,111=333,bar=123.3,foo=xyz]']
                ==  
                build(self._mod,
                      ['echo[1,2,3,some_str,111=333,foo=xyz,bar=123.3]']
                  ).tasks_run)

    def test_validate_keyword_arguments_always_after_args(self):
        with pytest.raises(Exception) as exc:
            build(self._mod, ['echo[bar=123.3,foo]'])
        assert "Non keyword arg foo cannot follows" \
            " a keyword arg bar=123.3" in str(exc.value)
        
        with pytest.raises(Exception) as exc:
            build(self._mod, ['copy[from_=/foo,/foo1]'])

        assert "Non keyword arg /foo1 cannot follows" \
            " a keyword arg from_=/foo" in str(exc.value)


            
    def test_invalid_number_of_args(self):
        with pytest.raises(TypeError) as exc: 
             build(self._mod, ['append[1,2,3]'])
        print(str(exc.value))
        assert re.findall('takes .*2 .*arguments', str(exc.value))

             
    def test_invalid_names_for_kwargs(self):
        with pytest.raises(TypeError) as exc: 
            build(self._mod, ['copy[1=2,to=bar]'])
        assert "got an unexpected keyword argument '1'" in str(exc.value)
        
        with pytest.raises(TypeError) as exc: 
            build(self._mod, ['copy[bar123=2]'])
        assert "got an unexpected keyword argument 'bar123'" in str(exc.value)


class TesttaskLocalImports:
    def setup_method(self,method):
        from .build_scripts import build_with_local_import
        self._mod = build_with_local_import
        self._mod.tasks_run = []

    def test_load_build_with_local_import_does_not_fail(self):
        mod = build(self._mod, ["work"])
