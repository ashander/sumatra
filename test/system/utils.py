"""
Utility functions for writing system tests.
"""

import os.path
import re
from itertools import islice, izip
import tempfile
import shutil
import sarge

DEBUG = False
temporary_dir = None
working_dir = None
env = {}


label_pattern = re.compile("Record label for this run: '(?P<label>\d{8}-\d{6})'")
label_pattern = re.compile("Record label for this run: '(?P<label>[\w\-_]+)'")

info_pattern = r"""Project name        : (?P<project_name>\w+)
Default executable  : (?P<executable>\w+) \(version: \d.\d.\d\) at /[\w\/]+/bin/python
Default repository  : MercurialRepository at \S+/sumatra_exercise \(upstream: \S+/ircr2013\)
Default main file   : (?P<main>\w+.\w+)
Default launch mode : serial
Data store \(output\) : /[\w\/]+/sumatra_exercise/Data
.          \(input\)  : /[\w\/]+/sumatra_exercise
Record store        : Django \(/[\w\/]+/sumatra_exercise/.smt/records\)
Code change policy  : (?P<code_change>\w+)
Append label to     : None
Label generator     : timestamp
Timestamp format    : %Y%m%d-%H%M%S
Sumatra version     : 0.7dev
"""

record_pattern = re.compile(r"""Label            : (?P<label>[\w-]+)
Timestamp        : (?P<timestamp>.*)
Reason           : *(?P<reason>.*)
Outcome          : *(?P<outcome>.*)
Duration         : (?P<duration>\d+.\d*)
Repository       : (?P<vcs>\w+)Repository at .*
.*
Main_File        : (?P<main>\w+.\w.)
Version          : (?P<version>\w+)
Script_Arguments : *(?P<script_args>.*)
Executable       : (?P<executable_name>\w+) \(version: (?P<executable_version>[\w\.]+)\) at\s+(: )?(?P<executable_path>.*)
Parameters       : *(?P<parameters>.*)
""")  # TO COMPLETE.


def setup():
    """Create temporary directory for the Sumatra project."""
    global temporary_dir, working_dir, env
    temporary_dir = os.path.realpath(tempfile.mkdtemp())
    working_dir = os.path.join(temporary_dir, "sumatra_exercise")
    os.mkdir(working_dir)
    print working_dir
    env["labels"] = []


def teardown():
    """Delete all files."""
    if os.path.exists(temporary_dir):
        shutil.rmtree(temporary_dir)


def run(command):
    """Run a command in the Sumatra project directory and capture the output."""
    return sarge.run(command, cwd=working_dir, stdout=sarge.Capture(timeout=10, buffer_size=1))


def assert_file_exists(p, relative_path):
    """Assert that a file exists at the given path, relative to the working directory."""
    assert os.path.exists(os.path.join(working_dir, relative_path))


def pairs(iterable):
    """
    ABCDEF -> (A, B), (C, D), (E, F)
    """
    return izip(islice(iterable, 0, None, 2), islice(iterable, 1, None, 2))


def get_label(p):
    """Obtain the label generated by 'smt run'."""
    match = label_pattern.search(p.stdout.text)
    if match is not None:
        return match.groupdict()["label"]
    else:
        return None


def assert_in_output(p, texts):
    """Assert that the stdout from process 'p' contains all of the provided text."""
    if isinstance(texts, basestring):
        texts = [texts]
    for text in texts:
        assert text in p.stdout.text, "'{}' is not in '{}'".format(text, p.stdout.text)


def assert_config(p, expected_config):
    """Assert that the Sumatra configuration (output from 'smt info') is as expected."""
    match = re.match(info_pattern, p.stdout.text)
    assert match, "Pattern: %s\nActual: %s" % (info_pattern, p.stdout.text)
    for key, value in expected_config.items():
        assert match.groupdict()[key] == value, "expected {} = {}, actually {}".format(key, value, match.groupdict()[key])


def assert_records(p, expected_records):
    """ """
    matches = [match.groupdict() for match in record_pattern.finditer(p.stdout.text)]
    if not matches:
        raise Exception("No matches for record_pattern.\nStdout:\n%s" % p.stdout.text)
    match_dict = dict((match["label"], match) for match in matches)
    for record in expected_records:
        if record["label"] not in match_dict:
            raise KeyError("Expected record %s not found in %s" % (record["label"], str(list(match_dict.keys()))))
        matching_record = match_dict[record["label"]]
        for key in record:
            assert record[key] == matching_record[key]


def assert_label_equal(p, expected_label):
    """ """
    assert get_label(p) == expected_label


def expected_short_list(env):
    """Generate the expected output from the 'smt list' command, given the list of captured labels."""
    return "\n".join(reversed(env["labels"]))


def substitute_labels(expected_records):
    """ """
    def wrapped(env):
        for record in expected_records:
            index = record["label"]
            record["label"] = env["labels"][index]
        return expected_records
    return wrapped


def build_command(template, env_var):
    """Return a function which will return a string."""

    def wrapped(env):
        args = env[env_var]
        if hasattr(args, "__len__") and not isinstance(args, basestring):
            s = template.format(*args)
        else:
            s = template.format(args)
        return s
    return wrapped


def edit_parameters(input, output, name, new_value):
    """ """
    global working_dir

    def wrapped():
        with open(os.path.join(working_dir, input), 'rb') as fpin:
            with open(os.path.join(working_dir, output), 'wb') as fpout:
                for line in fpin:
                    if name in line:
                        fpout.write("{} = {}\n".format(name, new_value))
                    else:
                        fpout.write(line)
    return wrapped


def run_test(command, *checks):
    """Execute a command in a sub-process then check that the output matches some criterion."""
    global env, DEBUG

    if callable(command):
        command = command(env)
    p = run(command)
    if DEBUG:
        print p.stdout.text
    for check, checkarg in pairs(checks):
        if callable(checkarg):
            checkarg = checkarg(env)
        check(p, checkarg)
    label = get_label(p)
    if label is not None:
        env["labels"].append(label)
        print "label is", label
run_test.__test__ = False  # nose should not treat this as a test
