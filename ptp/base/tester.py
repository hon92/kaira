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
import assembly

# types which are native supported by Kaira tool
NATIVE_TYPES = ["int", "bool", "char", "unsigned char", "unsigned int", "long", "void *",\
                            "unsigned long", "long long", "unsigned long long", "double", "float", "std::string", "std::vector", "std::pair"]

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
    def __init__(self, name, return_datatype = "void", parameters = [], const = False, volatile = False, restrict = False):
        self.name = name
        self.return_datatype = return_datatype
        self.parameters = parameters # list of tuples (datatype, var_name)
        self.const = const
        self.volatile = volatile
        self.restrict = restrict

    def _get_fns(self, function_checker):
        global_functions = function_checker.assembly.get_global_functions()
        match_fns = [f for f in global_functions if f.get_name() == self.name]
        return match_fns

    def _function_checks(self, fns):
        found_match = False

        for f in fns:
            if f.get_return_type() != self.return_datatype:
                continue
            if f.is_const() != self.const:
                continue
            if f.is_volatile() != self.volatile:
                continue
            if f.is_restrict() != self.restrict:
                continue
            parameters = f.get_parameters()
            if len(parameters) != len(self.parameters):
                continue

            valid_parameters = True
            for i in range(len(self.parameters)):
                parameter = parameters[i]
                data_type, var_name = self.parameters[i]
                if parameter.get_name() != var_name or parameter.get_datatype() != data_type:
                    valid_parameters = False
                    break

            if not valid_parameters:
                continue

            found_match = True
        return found_match

    def check(self, function_checker):
        fns = self._get_fns(function_checker)
        found = self._function_checks(fns)
        if not found:
            function_checker.set_throw_exception_data("Function \"{0}\" not defined in head code".format(self.name))
            return False
        return True


class MethodDefinition(FunctionDefinition):
    def __init__(self,  name, class_name, return_datatype = "void", parameters = [], const = False, volatile = False, restrict = False):
        FunctionDefinition.__init__(self, name, return_datatype, parameters, const, volatile, restrict)
        self.class_name = class_name

    def check(self, function_checker):
        self.target_class = function_checker.assembly.get_class(self.class_name)
        methods = []
        for m in self.target_class.get_methods():
            if m.get_name() == self.name:
                methods.append(m)

        found = self._function_checks(methods)
        if not found:
            function_checker.set_throw_exception_data("Method \"{0}\" not defined in type \"{1}\"".format(self.name, self.target_class.get_name()), self.target_class.class_cursor)
            return False
        else:
            return True

    def copy(self):
        return MethodDefinition(self.name, self.class_name, self.return_datatype, self.parameters, self.const, self.volatile, self.restrict)


class TraceFunctionDefinition(FunctionDefinition):
    def __init__(self, name, place_type):
        FunctionDefinition.__init__(self, name, "int", [], False, False, False)
        self.valid_data_type = ["int", "double", "std::string"]
        self.place_type = place_type

    def check(self, function_checker):
        fns = self._get_fns(function_checker)
        not_found_error_message = "Trace function \"{0}\" not defined in head code".format(self.name)
        if len(fns) == 0:
            function_checker.set_throw_exception_data(not_found_error_message)
            return False

        specific_error = ""
        found_match = False
        for f in fns:
            return_type = f.get_return_type()
            if return_type not in self.valid_data_type:
                specific_error = "Trace function \"{0}\" can return only [{1}]".format(self.name, "' or '".join(self.valid_data_type))
                continue
            parameters = f.get_parameters()
            if len(parameters) != 1:
                specific_error = "Trace function \"{0}\" has {1} parameters (1 given)".format(self.name, len(parameters))
                continue
            datatype = parameters[0].get_datatype()
            if datatype != self.place_type:
                specific_error = "Trace function \"{0}\" has wrong parameter(parameter must have \"{1}\" type)".format(self.name, self.place_type)
                continue

            found_match = True
            specific_error = ""

        if not found_match:
            if specific_error:
                function_checker.set_throw_exception_data(specific_error)
            else:
                function_checker.set_throw_exception_data(not_found_error_message)
            return False
        else:
            return True


class MacroDefinition():
    def __init__(self, name, parameters = []):
        self.name = name
        self.parameters = parameters

    def check(self, function_checker):
        namespaces = function_checker.assembly.get_namespace("ca")
        error_message = "Macro \"{0}\" not defined for type \"{1}\""

        if len(namespaces) == 0:
            function_checker.set_throw_exception_data(error_message.format(self.name, self.parameters[0]))
            return False
        found_match = False
        functions_to_check = []
        for namespace in namespaces:
            functions = namespace.get_functions()
            functions_to_check.extend([f for f in functions if f.get_name() == self.name])

        for fn in functions_to_check:
            parameters = fn.get_parameters()
            if len(parameters) != len(self.parameters):
                continue
            valid_parameters = True
            for i in range(len(self.parameters)):
                p = parameters[i]
                param_name = self.parameters[i]
                valid = False
                if self.parameters[0] in p.get_datatype():
                    valid = True
                    break
#                 for pp in p.var_cursor.get_children():
#                     print "type:", p.var_cursor.displayname, param_name, "PARAM:", self.parameters[0]
#                     if pp.type.spelling == param_name:
#                         valid = True
#                         break
                if not valid:
                    valid_parameters = False
                    break
                else:
                    break

            if valid_parameters:
                found_match = True
                break
            else:
                function_checker.set_throw_exception_data(error_message.format(self.name, self.parameters[0]))
        return found_match

    def copy(self):
        return MacroDefinition(self.name, self.parameters)


class MethodOrMacroDefinition():
    def __init__(self, method_def, macro_def):
        self.macro_def = macro_def
        self.method_def = method_def

    def check(self, function_checker):
        if not (self.method_def.check(function_checker) or self.macro_def.check(function_checker)):
            class_cursor = self.method_def.target_class.class_cursor
            message = "Method or macro \"{0}\" not defined for type \"{1}\""
            function_checker.set_throw_exception_data(message.format(self.macro_def.name, self.method_def.class_name), class_cursor)
            return False
        return True


class FunctionCheck():
    def __init__(self, tu, functions):
        self.tu = tu
        self.functions = functions
        self.assembly = assembly.Assembly(tu)
        self.line = 0
        self.column = 0
        self.message = ""

    def check(self):
        for func in self.functions:
            found = func.check(self)
            if not found:
                return self

    def set_throw_exception_data(self, message, class_cursor = None):
        if class_cursor:
            location = class_cursor.location
            self.line = location.line
            self.column = location.column
        self.message = message

    def throw_exception(self, head_line_offset):
        line = self.line - head_line_offset + 1
        if line < 0:
            line = 0
        raise utils.PtpException(self.message, "*head:{0}:{1}".format(line, self.column))


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


class ClangTester:


    filename = "/tmp/kaira-{0}.cpp".format(os.getuid())

    def __init__(self):
        self.args = ["-I/usr/include/clang/3.4/include"]
        self.checks = []
        self.functions_checks = []
        self.place_type_checks = []

    def add_arg(self, list):
        self.args.extend(list)

    def add(self, check):
        self.checks.append(check)

    def add_function_check(self, func_def):
        self.functions_checks.append(func_def)

    def add_place_type_check(self, place_check):
        self.place_type_checks.append(place_check)

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

    def process_diagnostics(self, diagnostics):
        for diagnostic in diagnostics:
            if diagnostic.severity > 2:
                print diagnostic.location, diagnostic.spelling, [r for r in diagnostic.ranges]
                if diagnostic.location.file.name == ClangTester.filename:
                    check_error = self.process_error(diagnostic)
                    if check_error:
                        return check_error
                else:
                    #check error in different file
                    message = "Code error at:{0}:{1} in file {2}: {3}"
                    line = diagnostic.location.line
                    column = diagnostic.location.column
                    info = diagnostic.spelling
                    file = diagnostic.location.file.name
                    raise utils.PtpException(message.format(line, column, file, info))

    def process_error(self, diagnostic):
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

        for place_check in self.place_type_checks:
            place_check.write(self.writer)

        self.writer.write_to_file(self.filename)
        tu = self._parse()
        if tu:
            self.check_types(tu)
            function_error = self.check_functions(tu)
            if function_error:
                return function_error
            check_error = self.process_diagnostics(tu.diagnostics)
            if check_error:
                return check_error

    def check_functions(self, tu):
        function_checker = FunctionCheck(tu, self.functions_checks)
        return function_checker.check()

    def check_types(self, tu):

        def get_types_to_check(type_parameter):
            all_tokens = [t.spelling for t in type_parameter.var_cursor.get_tokens()]
            tokens = []
            i = 1
            temp = []

            while i != len(all_tokens) - 1:
                t = all_tokens[i]
                if t == "&":
                    break
                elif t == "::":
                    tokens.append(" ".join(temp))
                    temp = []
                    prev = tokens[-1]
                    tokens[-1] = prev + t + all_tokens[i + 1]
                    i += 1
                elif t == "<" or t == ">":
                    if temp:
                        tokens.append(" ".join(temp))
                        temp = []
                    tokens.append(t)
                elif t == ",":
                    if temp:
                        tokens.append(" ".join(temp))
                        temp = []
                    tokens.append(t)
                else:
                    temp.append(t)
#                 elif t == "::":
#                     nt = all_tokens[i - 1]
#                     st = t
#                     tt = all_tokens[i + 1]
#                     #del tokens[-1]
#                     tokens.append(temp + st + tt)
#                     temp = ""
#                     i += 1
#                 elif t != "<" and t != ">":
#                     temp += t
#                     
#                 elif t == "<" or t == ">":
#                     temp = ""
#                     tokens.append(t)
#                 if temp:
#                     tokens.append(temp)
#                     temp = ""
                #else:
                 #   tokens.append(temp)
                  #  temp = ""
                i += 1

            if temp:
                tokens.append(" ".join(temp))
            #print "TYPE:", type_parameter.get_datatype(), "TOKENS:", tokens, "TEMP:", temp

            types = []
            off = -1
            for t in tokens:
                if t == "<":
                    off = -1
                elif t == ">":
                    off -= 1
                elif t != ",":
                    if len(types) == 0:
                        types.append((t, None))
                    else:
                        types.append((t, types[off][0]))
                        off -= 1
            if len(tokens) == 1 and len(types) == 0:
                types.append((tokens[0], None))

            types_to_check = []
            for i in range(len(types)):
                name, parent = types[i]
                if not parent:
                    if name not in NATIVE_TYPES:
                        types_to_check.append(name)
                else:
                    if parent in NATIVE_TYPES:
                        if name not in NATIVE_TYPES:
                            types_to_check.append(name)
            return types_to_check

        tu_assembly = assembly.Assembly(tu)
        functions = tu_assembly.get_global_functions()

        for place_check in self.place_type_checks:
            place_fn = [f for f in functions if f.get_name().startswith(place_check.fn_prefix) and f.get_name().endswith(place_check.id)]
            parameter = place_fn[0].get_parameters()[0]
            types = get_types_to_check(parameter)
            types = [t for t in types if t not in NATIVE_TYPES]
            #print "types not in natives:", types
            place_check.set_checks(types, self)

