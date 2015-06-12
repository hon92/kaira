#
#    Copyright (C) 2013 Stanislav Bohm
#
#    This file is part of Kaira.
#
#    Kaira is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, version 3 of the License, or
#    (at your option) any later version.
#
#    Kaira is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Kaira.  If not, see <http://www.gnu.org/licenses/>.
#

import subprocess
import re
import os
import clang.cindex as clang

check_id_counter = 30000

def new_id():
    global check_id_counter
    check_id_counter += 1
    return "____cpptest____{0}".format(check_id_counter)


class Check:

    content = ""
    own_message = None
    key = None
    message = None

    def write_prologue(self, writer):
        pass

    def write_epilogue(self, writer):
        pass

    def write_content(self, writer):
        pass

    def write(self, writer):
        self.start_line = writer.get_next_line_number()
        self.write_prologue(writer)
        self.write_content(writer)
        self.write_epilogue(writer)
        self.end_line = writer.get_current_line_number()

    def process_match(self, line_no, message):
        if self.start_line <= line_no and self.end_line >= line_no:
            if self.own_message is not None:
                self.message = self.own_message
            else:
                self.message = message
            return True
        return False

    def new_id(self):
        return new_id()


class Tester:


    compiler = "gcc"
    filename = "/tmp/kaira-{0}.cpp".format(os.getuid())

    def __init__(self):
        self.args = ()
        self.message_parser = re.compile(
            "(?P<filename>[^:]*):(?P<line>\d+):(?P<message>.*)")
        self.checks = []
        self.prepare_writer = None
        self.stdout = None
        self.stderr = None

    def add(self, check):
        self.checks.append(check)

    def process_message(self, line):
        match = self.message_parser.match(line)
        if match is None:
            return
        if match.group("filename") != self.filename:
            return
        line_no = int(match.group("line"))
        message = match.group("message")
        for check in self.checks:
            if check.process_match(line_no, message):
                return check

    def run(self):
        assert self.prepare_writer is not None
        writer = self.prepare_writer(self.filename)

        for check in self.checks:
            check.write(writer)

        writer.write_to_file(self.filename)
        p = subprocess.Popen(("g++",) + tuple(self.args) +
                             ("-O0", "-c", "-o", "/tmp/kaira.o", self.filename),
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE)
        self.stdout, self.stderr = p.communicate()
        for line in self.stderr.split("\n"):
            check = self.process_message(line)
            print line
            if check is not None:
                return check
        return None


class ClangTester:


    filename = "/tmp/kaira-{0}.cpp".format(os.getuid())

    def __init__(self):
        self.args = ["-I/usr/include/clang/3.4/include"]
        self.checks = []
        self.hidden_namespace_decl = ""

    def add_arg(self, list):
        self.args.extend(list)

    def add(self, check):
        self.checks.append(check)

    def add_hidden_namespace_decl(self, hidden_namespace):
        self.hidden_namespace_decl = hidden_namespace.get_code()

    def clang_available(self):
        import ptp
        available = True
        if not clang.Config.loaded:
                has_clang = ptp.get_config("Main", "LIBCLANG")
                if has_clang == "True":
                    path = ptp.get_config("libclang", "path")
                    clang.Config.set_library_file(path)
                else:
                    available = False
        return available

    def _parse(self):
        assert self.clang_available() is not None
        index = clang.Index.create()
        file = open(ClangTester.filename, 'r')
        unsaved_files = [(ClangTester.filename, file)]
        tu = index.parse(ClangTester.filename, self.args, unsaved_files)
        return tu

    def process_diagnostics(self, diagnostic):
        for diagnostic in diagnostic:
            if diagnostic.severity > 2:
                check_error = self.process_error(diagnostic)
                if check_error:
                    return check_error

    def process_error(self, diagnostic):
        print diagnostic.location, diagnostic.spelling
        location = diagnostic.location
        line = location.line
        for c in self.checks:
            if c.start_line <= line and c.end_line >= line:
                #print "ON LINE {0} ERROR:{1}".format(line, diagnostic.spelling),c, c.start_line
                c.line = line - c.start_line
                c.column = location.column
                c.message = diagnostic.spelling
                return c

    def run(self):
        assert self.prepare_writer is not None
        self.writer = self.prepare_writer(self.filename)
        self.writer.raw_text("#include <cailie.h>")
        head_check = self.checks[0]
        head_check.write(self.writer)
        self.writer.raw_text(self.hidden_namespace_decl)

        for i in range(1, len(self.checks)):
            self.checks[i].write(self.writer)

        self.writer.write_to_file(self.filename)
        tu = self._parse()
        if tu:
            check_error = self.process_diagnostics(tu.diagnostics)
            if check_error:
                return check_error