#!/usr/local/bin/python

#
# Copyright 2017 Marco Helmich
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from subprocess import Popen, PIPE, STDOUT
import os

# CONSTANTS
TEST_NAME = 'GalaxyBTreeTest'
SERVICE_NAME = 'carbon-copy'
MASTER_BRANCH_NAME = 'master'
GIT_REPO_ROOT = '.'
CURRENT_WD = os.path.dirname(os.path.realpath(__file__))
DELIMITER='|'

"""
    This is a thin wrapper around commandline git
    It allows you to call methods like git.status() or git.checkout('develop~HEAD')

    Internally all it does is intercepting calls to unknown methods (the class has no method).
    Then is tokenizes all strings passed into it and forwards all this to git (which runs in a subprocess).
"""
class Git(object):
    def __init__(self, repo_dir = '.'):
        self.repo_dir = repo_dir
        pass

    def __getattr__(self, name):
        def wrapper(*args, **kwargs):
            gitified_name = name.replace('_', '-')
            command_line = ['git', gitified_name] + list(args)
            #print "command that's called '%s'" % ' '.join(command_line)
            proc = Popen(command_line, stdout=PIPE, stderr=STDOUT, cwd=self.repo_dir, universal_newlines=False)
            (stdoutdata, stderrdata) = proc.communicate()
            return_code = proc.wait()
            if return_code > 0:
                raise Exception('something went wrong in your git command')
            return (return_code, stdoutdata)
        return wrapper

def get_run_test_command(test_name_pattern):
    # statically compose the command to run
    #return ['mvn', '-q', '-Dtest=' + test_name_pattern, 'test']
    return [CURRENT_WD + '/run_test.sh', test_name_pattern]

def run_test(test_name_pattern, working_dir):
    command_line = get_run_test_command(test_name_pattern)
    print "executing %s" % ' '.join(command_line)
    # hard wired the maven command to run a test
    proc = Popen(command_line, cwd=working_dir)
    # return the return code of the process
    return proc.wait()

def clean_up_repo(git):
    # this can be as simple or fancy as you want it to be
    # right now I do the bare minimum of checking out HEAD again
    git.checkout(MASTER_BRANCH_NAME)
    pass

def get_last_good_revision(git):
    # find last good revision by fibonacci'ing
    # your way to the last good revision
    fib1 = 1
    fib2 = 1
    fib = 0
    is_test_failing = True
    relative_revision = ''

    while is_test_failing:
        # first of all, iterate the fibonacci counters
        fib = fib1 + fib2
        fib1 = fib2
        fib2 = fib
        relative_revision = MASTER_BRANCH_NAME + "~%d" % fib
        print "\n============================================"
        print "revision under test is %s" % relative_revision
        print "============================================\n"
        git.checkout(relative_revision)
        # check out the respective revision relative to HEAD
        # run the test
        return_code = run_test(TEST_NAME, '.')
        if return_code > 0:
            print "\n============================================"
            print "test in revision %s failed" % relative_revision
            print "============================================\n"
        else:
            print "\n============================================"
            print "test in revision %s passed" % relative_revision
            print "============================================\n"
        # iterate the loop variable
        is_test_failing = return_code > 0
        # there might be a build failure or something
        # that is an independent failure
        # hence at some point we want to interrupt the process
        if fib > 987:
            raise Exception('potential infinite loop detected')
        pass

    return "HEAD~%d" % fib

def find_between(s, first, last):
    try:
        start = s.index(first) + len(first)
        end = s.index(last, start)
        return s[start:end]
    except ValueError:
        return ""

def bisect(git, last_good_revision_hash):
    # this is pretty important
    # you need to make sure your git repo is in a consistent state
    # it seems like git bisect takes the good and bad revision
    # relative to which revision is currently in the repo
    print "======> last_good_revision_hash %s" % last_good_revision_hash
    clean_up_repo(git)
    print "=====> cleaned up"
    # start the bisect with the BAD and the GOOD
    (return_code, output) = git.bisect('start', 'HEAD', last_good_revision_hash)
    print "=====> started bisect"
    line = ''
    for token in output:
        line = line + token
        if token.endswith('\n'):
            print line
    run_test_command_line = get_run_test_command(TEST_NAME)
    print "=====> %s" % run_test_command_line
    # pass in the array as single string arguments
    git.bisect('run', *run_test_command_line)

    # log the bisect trace
    (return_code, output) = git.bisect('log')
    # print output to stdout
    first_bad_revision=''

    # putting the line back together
    line = ''
    for token in output:
        line = line + token
        if token.endswith('\n'):
            print line
            # MAGIC TOKEN ALERT
            if '# first bad commit' in line:
                first_bad_revision = find_between(line, '[', ']')
            else:
                line = ''

    print "\n============================================"
    print "found first bad revision : %s" % first_bad_revision
    print "============================================\n"
    # get detailed into about the commit
    # this monster will contain
    # author | email | date | subject
    # an example looks like this
    # mhelmich|mhelmich@lendingclub.com|2016-06-24 18:38:30 -0700|nananana failing test
    (return_code, output) = git.log('-1', '--pretty=%aN' + DELIMITER + '%ae' + DELIMITER + '%ai' + DELIMITER + '%s', first_bad_revision)
    detailed_revision_info = ''
    # print output to stdout
    # stdout has to have only one line!
    line = ''
    for token in output:
        line = line + token
        if token.endswith('\n'):
            print line
            detailed_revision_info = line


    detailed_revision_info_array = detailed_revision_info.split(DELIMITER)
    #print "info about the checkin : %s" % ' '.join(detailed_revision_info_array)
    git.bisect('reset')
    return (first_bad_revision, detailed_revision_info_array[0], detailed_revision_info_array[1], detailed_revision_info_array[2], detailed_revision_info_array[3])

if __name__ == "__main__":
    git = Git(GIT_REPO_ROOT)
    # establish the last good revision
    last_good_revision_hash = get_last_good_revision(git)
    print "\n============================================"
    print "last good revision is : %s" % last_good_revision_hash
    print "============================================\n"
    # bisect all revision between the last good one and HEAD
    (bad_commit_hash, user_name, email, date, commit_subject) = bisect(git, last_good_revision_hash)
    print "info about the checkin : %s %s %s %s %s" % (bad_commit_hash, user_name, email, date, commit_subject)
    # grab all this info and send an email/create a ticket/etc.

    print """
        send to: %s

        Dear %s,
        you seem have broken tests in the project %s with your commit
        "%s"
        on %s.
        Btw the commit hash was %s.
        Would you mind taking a look and fixing it?
        Cheers,
           Marco
    """ % (email, user_name, SERVICE_NAME, commit_subject, date, bad_commit_hash)
    pass
