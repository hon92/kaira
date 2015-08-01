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

class FunctionDefinition():
    def __init__(self, name, type_to_search, return_type = "void", parameters = [], macro_name = None, const = False, volatile = False, restrict = False):
        self.name = name
        self.return_type = return_type
        self.parameters = parameters
        self.const = const
        self.volatile = volatile
        self.restrict = restrict
        self.type_to_search = type_to_search
        self.macro_name = macro_name

    def __eq__(self, other):
        if type(other) != type(self):
            return False
        if (self.name == other.name and
             self.type_to_search == other.type_to_search and
             self.return_type == other.return_type and 
             self.parameters == other.parameters and 
             self.macro_name == other.macro_name and 
             self.const == other.const and 
             self.volatile == other.volatile and 
             self.restrict == other.restrict):
            return True
        else:
            return False 

class FunctionCheck():

    def __init__(self, tu, functions):
        self.functions = functions
        self.tu = tu
        self.types = {}
        self.type_methods = {}
        self.namespace = None

    def add(self, func_def):
        self.functions.append(func_def)

    def _find_functions(self):
        functions = []
        for c in self.tu.cursor.get_children():
            if not c.location.file or c.location.file.name != ClangTester.filename:
                continue
            if c.kind == clang.CursorKind.FUNCTION_DECL:
                functions.append(c)
        return functions

    def _find_declarations(self):
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
                self.types[c.spelling] = c

            elif not self.namespace and kind_type == clang.CursorKind.NAMESPACE and c.spelling == "ca":
                self.namespace = c

    def _get_parent_types(self, decl):
        parent_classes = []
        for d in decl.get_children():
            if d.kind == clang.CursorKind.CXX_BASE_SPECIFIER:
                for base in d.get_children():
                    parent_classes.append(base.type.spelling)
        return parent_classes

    def _find_public_methods(self, declaration):
        if declaration.spelling not in self.type_methods:
            methods = []
            is_public = False
            for field in declaration.get_children():
                kind_type = field.kind
                if kind_type == clang.CursorKind.CXX_ACCESS_SPEC_DECL:
                    c = field
                    for token in c.get_tokens():
                        if token.kind == clang.TokenKind.KEYWORD and token.cursor == c:
                            if token.spelling == "public":
                                is_public = True
                                break
                            else:
                                is_public = False

                if not is_public:
                    continue
                if kind_type != clang.CursorKind.CXX_METHOD:
                    continue
                methods.append(field)
            self.type_methods[declaration.spelling] = methods
            return methods
        else:
            return self.type_methods[declaration.spelling]

    def _find_methods(self, declaration):
        if declaration.spelling not in self.type_methods:
            methods = []

            for field in declaration.get_children():
                kind_type = field.kind
                if kind_type != clang.CursorKind.CXX_METHOD:
                    continue
                methods.append(field)

            self.type_methods[declaration.spelling] = methods
            return methods
        else:
            return self.type_methods[declaration.spelling]

    def _get_usr(self, data):
        x = data[len(data) - 1]
        if x == "#":
            return (False, False, False)#const, volatile, restrict

        is_const = int(x) & 0x1
        is_volatile = int(x) & 0x4
        is_restrict = int(x) & 0x2
        return (is_const != 0, is_volatile != 0, is_restrict != 0)

    def _check_specific_function(self, functions, func):
        def get_parameters(fn):
            parameters = []
            for c in fn.get_children():
                if c.kind == clang.CursorKind.PARM_DECL:
                        parameters.append(c)
            return parameters

        def check_parameters(parameters):
            for i in range(len(func.parameters)):
                p = parameters[i]
                n, t = func.parameters[i]
                type = p.type.spelling
                name = p.spelling
                if not (n == name and t == type):
                    return False
            return True

        for fn in functions:
            if fn.spelling != func.name:
                    continue
            is_const, is_volatile, is_restrict = self._get_usr(fn.get_usr())
            if is_const != func.const or is_volatile != func.volatile or is_restrict != func.restrict:
                continue

            result_type = fn.result_type.spelling
            if result_type != func.return_type:
                continue 

            parameters = get_parameters(fn)
            if(len(parameters) != len(func.parameters)):
                continue

            if not check_parameters(parameters):
                continue

            return True
        return False

    def check(self):
#         if self.function_type == "function":
#             functions = self._find_functions()
#             contain = self._check_specific_function(functions)
#             if not contain:
#                 self.throw_function_exception()

#         elif self.function_type == "method":
        self._find_declarations()
        for func in self.functions:
            if func.type_to_search in self.types:
                type = self.types[func.type_to_search]
                types_to_search = [type]
                for parent_type in self._get_parent_types(type):
                    if parent_type in self.types:
                        types_to_search.append(self.types[parent_type])

                founded = False
                for t in types_to_search:
                    methods = self._find_methods(t)
                    contain = self._check_specific_function(methods, func)
                    if contain:
                        founded = True
                        break

                if not founded:
                    if self.namespace and func.macro_name:
                        has_macro = self.check_macro(func)
                        if not has_macro:
                            self.set_method_exception(type, func)
                            return self
                    else:
                        self.set_method_exception(type, func)
                        return self

    def check_macro(self, func):
        for item_in_namespace in self.namespace.get_children():
            if item_in_namespace.kind == clang.CursorKind.FUNCTION_DECL and item_in_namespace.spelling == func.macro_name:
                for info in item_in_namespace.get_children():
                    if info.kind == clang.CursorKind.PARM_DECL:
                        for info_type in info.get_children():
                            if info_type.type.spelling == func.type_to_search:
                                return True
        return False

    def set_method_exception(self, decl, func):
        location = decl.location
        self.message = "In user type \"{0}\" is not defined method \"{1}\"".format(decl.displayname, func.name)
        self.line = location.line
        self.column = location.column

#     def set_function_exception(self):
#         message = "In head file did not exist function \"{0}\""
#         #raise utils.PtpException(message.format(self.name), "*head")

    def throw_exception(self, line_offset = 0):
        raise utils.PtpException(self.message, "*head:{0}:{1}".format(self.line - line_offset + 1, self.column))

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
            if check is not None:
                return check
        return None

#TODO: opravit line_offset
class ClangTester:


    filename = "/tmp/kaira-{0}.cpp".format(os.getuid())

    def __init__(self):
        self.args = ["-I/usr/include/clang/3.4/include"]
        self.checks = []
        self.functions_checks = []

    def add_arg(self, list):
        self.args.extend(list)

    def add(self, check):
        self.checks.append(check)

    def add_function_check(self, func_def):
        self.functions_checks.append(func_def)

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

    def process_diagnostics(self, diagnostic):#TOTO: raise unknown error 
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
                c.line = line - c.start_line
                c.column = location.column
                c.message = diagnostic.spelling
                return c
        return None

    def run(self):
        assert self.prepare_writer is not None
        self.writer = self.prepare_writer(self.filename)
        self.writer.raw_text("#include <cailie.h>")

        for check in self.checks:
            check.write(self.writer)

        self.writer.write_to_file(self.filename)
        tu = self._parse()
        if tu:
            function_error = self.check_functions(tu);
            if function_error:
                return function_error
            check_error = self.process_diagnostics(tu.diagnostics)
            if check_error:
                return check_error

    def check_functions(self, tu):
        function_checker = FunctionCheck(tu, self.functions_checks)
        return function_checker.check()


