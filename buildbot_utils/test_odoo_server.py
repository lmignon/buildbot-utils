#!/usr/bin/env python
from __future__ import print_function
import ast
import os
import re
import sys
import subprocess
import argparse
import ConfigParser

MANIFEST_FILES = ['__odoo__.py', '__openerp__.py', '__terp__.py']


def has_test_errors(fname, dbname, check_loaded=True):
    """
    Check a list of log lines for test errors.
    Extension point to detect false positives.
    """
    # Rules defining checks to perform
    # this can be
    # - a string which will be checked in a simple substring match
    # - a regex object that will be matched against the whole message
    # - a callable that receives a dictionary of the form
    #     {
    #         'loglevel': ...,
    #         'message': ....,
    #     }
    errors_ignore = [
        'Mail delivery failed',
        'failed sending mail',
    ]
    errors_report = [
        lambda x: x['loglevel'] == 'CRITICAL',
        'At least one test failed',
        'no access rules, consider adding one',
        'invalid module names, ignored',
    ]

    def make_pattern_list_callable(pattern_list):
        for i in range(len(pattern_list)):
            if isinstance(pattern_list[i], basestring):
                regex = re.compile(pattern_list[i])
                pattern_list[i] = lambda x: regex.match(x['message'])
            elif hasattr(pattern_list[i], 'match'):
                regex = pattern_list[i]
                pattern_list[i] = lambda x: regex.match(x['message'])

    make_pattern_list_callable(errors_ignore)
    make_pattern_list_callable(errors_report)

    print("-" * 10)
    # Read log file removing ASCII color escapes:
    # http://serverfault.com/questions/71285
    color_regex = re.compile(r'\x1B\[([0-9]{1,2}(;[0-9]{1,2})?)?[m|K]')
    log_start_regex = re.compile(
        r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \d+ (?P<loglevel>\w+) '
        '(?P<db>(%s)|([?])) (?P<logger>\S+): (?P<message>.*)$' % dbname)
    log_records = []
    last_log_record = dict.fromkeys(log_start_regex.groupindex.keys())
    with open(fname) as log:
        for line in log:
            line = color_regex.sub('', line)
            match = log_start_regex.match(line)
            if match:
                last_log_record = match.groupdict()
                log_records.append(last_log_record)
            else:
                last_log_record['message'] = '%s\n%s' % (
                    last_log_record['message'], line.rstrip('\n')
                )
    errors = []
    for log_record in log_records:
        ignore = False
        for ignore_pattern in errors_ignore:
            if ignore_pattern(log_record):
                ignore = True
                break
        if ignore:
            break
        for report_pattern in errors_report:
            if report_pattern(log_record):
                errors.append(log_record)
                break

    if check_loaded:
        if not [r for r in log_records if 'Modules loaded.' == r['message']]:
            errors.append({'message': "Modules loaded message not found."})

    if errors:
        for e in errors:
            print(e['message'])
        print("-" * 10)
    return len(errors)


def is_module(path):
    """return False if the path doesn't contain an odoo module, and the full
    path to the module manifest otherwise"""

    if not os.path.isdir(path):
        return False
    files = os.listdir(path)
    filtered = [x for x in files if x in (MANIFEST_FILES + ['__init__.py'])]
    if len(filtered) == 2 and '__init__.py' in filtered:
        return os.path.join(
            path, next(x for x in filtered if x != '__init__.py'))
    else:
        return False


def is_installable_module(path):
    """return False if the path doesn't contain an installable odoo module,
    and the full path to the module manifest otherwise"""
    manifest_path = is_module(path)
    if manifest_path:
        manifest = ast.literal_eval(open(manifest_path).read())
        if manifest.get('installable', True):
            return manifest_path
    return False


def get_modules(path):

    # Avoid empty basename when path ends with slash
    if not os.path.basename(path):
        path = os.path.dirname(path)

    res = []
    if os.path.isdir(path):
        res = [x for x in os.listdir(path)
               if is_installable_module(os.path.join(path, x))]
    return res


def is_addons(path):
    res = get_modules(path) != []
    return res


def get_addons(path):
    if not os.path.exists(path):
        return []
    if is_addons(path):
        res = [path]
    else:
        res = [os.path.join(path, x)
               for x in os.listdir(path)
               if is_addons(os.path.join(path, x))]
    return res


def get_addons_path(cfg_file):
    if os.path.exists(cfg_file):
        config = ConfigParser.ConfigParser()
        config.readfp(open(cfg_file))
        return config.get('options', 'addons_path')
    try:
        import openerp
        openerp.modules.module.initialize_sys_path()
        ad_paths = openerp.modules.module.ad_paths
        for ad in __import__('odoo_addons').__path__:
            ad = os.path.abspath(ad)
            if ad not in ad_paths:
                ad_paths.append(ad)
        print (ad_paths)
        return ",".join(ad_paths)
    except ImportError:
        # odoo_addons is not provided by any distribution
        pass


def get_addons_to_check(src_dirs, odoo_include, odoo_exclude):
    """
    Get the list of modules that need to be installed
    :param src_dirs: list of src_dir directory
    :param odoo_include: addons to include
    :param odoo_exclude: addons to exclude
    :return: List of addons to test
    """
    addons_list = []
    if odoo_include:
        addons_list = odoo_include
    else:
        addons_list = []
        for src_dir in src_dirs:
            addons_list.extend(get_modules(src_dir))

    if odoo_exclude:
        exclude_list = odoo_exclude
        addons_list = [
            x for x in addons_list
            if x not in exclude_list]
    return addons_list


def get_test_dependencies(addons_path, addons_list):
    """
    Get the list of core and external modules dependencies
    for the modules to test.
    :param addons_path: string with a comma separated list of addons paths
    :param addons_list: list of the modules to test
    """
    if not addons_list:
        return ['base']
    else:
        for path in addons_path.split(','):
            manif_path = is_installable_module(
                os.path.join(path, addons_list[0]))
            if not manif_path:
                continue
            manif = eval(open(manif_path).read())
            return list(
                set(manif.get('depends', []))
                | set(get_test_dependencies(addons_path, addons_list[1:]))
                - set(addons_list))


def setup_server(db, server_cmd, preinstall_modules, install_options=None):
    """
    Setup the base module before running the tests
    if the database template exists then will be used.
    :param db: Template database name
    :param server_cmd: Server command
    :param preinstall_modules: list of modules to preinstall
    :param install_options: Install options (travis parameter)
    """
    if preinstall_modules is None:
        preinstall_modules = ['base']
    print("\nCreating instance:")
    try:
        subprocess.check_call(["createdb", db])
    except subprocess.CalledProcessError:
        print("Using previous openerp_template database.")
    else:
        try:
            cmd_odoo = ["%s" % server_cmd,
                        "-d", db,
                        "--log-level=info",
                        "--stop-after-init",
                        "--init", ','.join(preinstall_modules),
                        ] + (install_options or [])
            print(" ".join(cmd_odoo))
            command_call = ['unbuffer'] + cmd_odoo
            p = subprocess.Popen(command_call,
                                 stderr=subprocess.STDOUT,
                                 stdout=subprocess.PIPE)
            for line in iter(p.stdout.readline, ""):
                print(line.replace('\n', ''))
            p.stdout.close()
            return_code = p.wait()
            return return_code
        except Exception as e:
            return 1
    return 0


RED = "\033[1;31m"
GREEN = "\033[1;32m"
CLEAR = "\033[0;m"


def colorized(text, color):
    return '\n'.join(
        map(lambda line: color + line + CLEAR, text.split('\n')))


def green(text):
    return colorized(text, GREEN)


def red(text):
    return colorized(text, RED)


fail_msg = red("FAIL")
success_msg = green("Success")


def test_server(db, server_cmd, tested_addons, expected_errors, odoo_version):
    """
    Setup the base module before running the tests
    if the database template exists then will be used.
    :param db: Template database name
    :param server_cmd: Server command
    :param tested_addons: List of addons to test
    """
    all_errors = []
    counted_errors = 0
    print("\nTesting %s:" % tested_addons)
    test_loghandler = None
    if odoo_version == '7.0':
        test_loglevel = 'test'
    else:
        test_loglevel = 'info'
        test_loghandler = 'openerp.tools.yaml_import:DEBUG'
    cmd_odoo = ["%s" % server_cmd,
                "-d", db,
                "--log-level=%s" % test_loglevel,
                "--stop-after-init",
                "--init", ','.join(tested_addons),
                "--test-enable",
                ]
    if test_loghandler:
        cmd_odoo +=  ['--log-handler', test_loghandler]
    print(" ".join(cmd_odoo))
    command_call = ['unbuffer'] + cmd_odoo
    pipe = subprocess.Popen(command_call,
                            stderr=subprocess.STDOUT,
                            stdout=subprocess.PIPE)
    with open('stdout.log', 'w') as stdout:
        for line in iter(pipe.stdout.readline, ""):
            stdout.write(line)
            print(line.strip())
    returncode = pipe.wait()
    # Find errors, except from failed mails
    errors = has_test_errors(
        "stdout.log", db)
    if returncode != 0:
        all_errors.append(tested_addons)
        print(fail_msg, "Command exited with code %s" % returncode)
        # If not exists errors then
        # add an error when returcode!=0
        # because is really a error.
        if not errors:
            errors += 1
    if errors:
        counted_errors += errors
        all_errors.append(tested_addons)
        print(fail_msg, "Found %d lines with errors" % errors)
    print('Module test summary')
    if all_errors:
        print(fail_msg, tested_addons)
    else:
        print(success_msg, tested_addons)
    if expected_errors and counted_errors != expected_errors:
        print("Expected %d errors, found %d!"
              % (expected_errors, counted_errors))
        return 1
    elif counted_errors != expected_errors:
        return 1
    # if we get here, all is OK
    return 0


def get_parser():
    """Return :py:class:`argparse.ArgumentParser` instance for CLI."""

    main_parser = argparse.ArgumentParser()

    main_parser.add_argument(
        '-t', '--test',
        dest='do_run_tests',
        action="store_true",
        default=False,
        help='Run tests'
    )

    main_parser.add_argument(
        '-v', '--version',
        dest='version',
        action="store",
        default="8.0",
        choices=["7.0", "8.0", "9.0"],
        help='Specify odoo version'
    )

    main_parser.add_argument(
        '-i', '--init',
        dest='do_run_tests',
        action="store_false",
        help='Init server'
    )

    main_parser.add_argument(
        '-s', '--src_dir',
        dest='src_dirs',
        action="append",
        default=[],
        help='Src dir'
    )

    main_parser.add_argument(
        '-d', '--db',
        dest='db',
        action='store', default=None,
        help='DB name',
    )

    main_parser.add_argument(
        '-cmd', '--server-cmd',
        dest='server_cmd',
        action='store', default=None,
        help='Odoo server command (by default ./bin/start_odoo (7.0, 8.0) '
             'or odoo-autodiscover (9.0))'
    )

    main_parser.add_argument(
        '-c', '--cfg',
        dest='cfg_file',
        action='store', default='./etc/odoo.cfg',
        help='Odoo server config'
    )

    main_parser.add_argument(
        '-e', '--expected-errors',
        type=int,
        dest='expected_errors',
        action='store', default=0,
        help='Odoo server config'
    )

    main_parser.add_argument(
        '--exclude',
        dest='exclude',
        action='store', default='',
        help='Comma separated list of addons to exclude from tests'
    )

    main_parser.add_argument(
        '--include',
        dest='include',
        action='store', default='',
        help='Comma separated list of addons to include from tests'
             '(if not specified all addons is src_dirs are tested)'
    )
    return main_parser


def main():
    """Main CLI application."""

    parser = get_parser()
    args = parser.parse_args()
    tested_addons_list = get_addons_to_check(
        args.src_dirs, args.include, args.exclude)
    addons_path = get_addons_path(args.cfg_file)
    preinstall_modules = get_test_dependencies(addons_path, tested_addons_list)
    server_cmd = args.server_cmd
    if not server_cmd:
        if args.version in ['7.0', '8.0']:
            server_cmd = './bin/start_odoo'
        else:
            server_cmd = 'odoo-autodiscover.py'
    if not args.do_run_tests:
        return setup_server(args.db, server_cmd, preinstall_modules)
    else:
        return test_server(args.db, server_cmd, tested_addons_list,
                           args.expected_errors, args.version)

if __name__ == '__main__':
    exit(main())
