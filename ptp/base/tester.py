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
import utils
from collections import OrderedDict

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

class FunctionCheck():

    #function_type = "method" or "function"
    def __init__(self, tu, name, function_type, return_type = "void", parameters = {}, const = False, volatile = False, restrict = False):
        self.tu = tu
        self.name = name
        self.return_type = return_type
        self.parameters = parameters
        self.function_type = function_type
        self.const = const
        self.volatile = volatile
        self.restrict = restrict

    def _find_functions(self):
        functions = []
        for c in self.tu.cursor.get_children():
            if not c.location.file or c.location.file.name != ClangTester.filename:
                continue
            if c.kind == clang.CursorKind.FUNCTION_DECL:
                functions.append(c)
        return functions

    def _find_class_or_struct_declarations(self):
        declarations = []
        cursor = self.tu.cursor
        for c in cursor.get_children():
            if not c.location.file or c.location.file.name != ClangTester.filename: 
                continue

            if not c.semantic_parent or c.semantic_parent != cursor: # only declarations inside head with semantic_parent root cursor
                continue

            kind_type = c.kind
            if kind_type == clang.CursorKind.STRUCT_DECL or kind_type == clang.CursorKind.UNION_DECL or kind_type == clang.CursorKind.CLASS_DECL: # struct, union or class declaration kind
                if c.spelling == "param": # skip param struct
                    continue
                declarations.append(c)
        return declarations

    def _find_functions_inside_declaration(self, declaration):
        methods = []
        for field in declaration.get_children():
            kind_type = field.kind
            if kind_type != clang.CursorKind.CXX_METHOD:
                continue
            methods.append(field)
        return methods

    def _get_usr(self, data):
        x = data[len(data) - 1]
        if x == "#":
            return (False, False, False)#const, volatile, restrict

        is_const = int(x) & 0x1
        is_volatile = int(x) & 0x4
        is_restrict = int(x) & 0x2
        return (is_const != 0, is_volatile != 0, is_restrict != 0)

    def _check_specific_function(self, functions):
        def get_parameters(fn):
            parameters = []
            for c in fn.get_children():
                if c.kind == clang.CursorKind.PARM_DECL:
                        parameters.append(c)
            return parameters

        def check_parameters(parameters):
            for i in range(len(self.parameters)):
                p = parameters[i]
                n, t = self.parameters[i]
                type = p.type.spelling
                name = p.spelling
                if not (n == name and t == type):
                    return False
            return True

        for fn in functions:
            if fn.spelling != self.name:
                    continue
            is_const, is_volatile, is_restrict = self._get_usr(fn.get_usr())
            if is_const != self.const or is_volatile != self.volatile or is_restrict != self.restrict:
                continue

            result_type = fn.result_type.spelling
            if result_type != self.return_type:
                continue 

            parameters = get_parameters(fn)
            if(len(parameters) != len(self.parameters)):
                continue

            if not check_parameters(parameters):
                continue

            return True
        return False

    def check(self, line_offset = 0):
        if self.function_type == "function":
            functions = self._find_functions()
            contain = self._check_specific_function(functions)
            if not contain:
                self.throw_function_exception()

        elif self.function_type == "method":
            user_declarations = self._find_class_or_struct_declarations()
            for decl in user_declarations:
                methods = self._find_functions_inside_declaration(decl)
                contain = self._check_specific_function(methods)
                if not contain:
                    self.throw_method_exception(decl, line_offset)
        else:
            raise Exception("Invalid function type({0})".format(self.function_type))

    def throw_method_exception(self, decl, line_offset):
        location = decl.location
        message = "In user type \"{0}\" is not defined method \"{1}\""
        print "line " , location.line, line_offset, decl.kind, decl.displayname
        raise utils.PtpException(message.format(decl.displayname, self.name), "*head:{0}:{1}".format(location.line - line_offset + 1, location.column))

    def throw_function_exception(self):
        message = "In head file did not exist function \"{0}\""
        raise utils.PtpException(message.format(self.name), "*head")

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
        with open(ClangTester.filename, 'r') as file:
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
        param_check = self.checks[0]
        self.head_check = self.checks[1]
        param_check.write(self.writer)
        self.head_check.write(self.writer)
        self.writer.raw_text(self.hidden_namespace_decl)

        for i in range(2, len(self.checks)):
            self.checks[i].write(self.writer)

        self.writer.write_to_file(self.filename)
        tu = self._parse()
        if tu:
            self.check_functions(tu);
            check_error = self.process_diagnostics(tu.diagnostics)
            if check_error:
                return check_error

    def check_functions(self, tu):
        FunctionCheck(tu, "token_name", "method", "std::string", const = True).check(self.head_check.start_line)

