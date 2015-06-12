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


import base.tester
import base.utils as utils
import base.paths as paths
from base.net import Declarations
import os.path
import build
from copy import copy

class CheckStatement(base.tester.Check):

    def __init__(self, expression, decls=None, return_type="void", source=None):
        self.expression = expression
        self.decls = decls
        self.return_type = return_type
        self.source = source

    def write_prologue(self, writer):
        if self.decls is not None:
            decls = self.decls.get_list()
        else:
            decls = []

        writer.line("{0} {1} ({2}) {{",
                    self.return_type,
                    self.new_id(),
                    ",".join("{0} {1}".format(t, name) for name, t in decls))

    def write_epilogue(self, writer):
        writer.line("}}")

    def write_content(self, writer):
        writer.raw_line(self.expression)

    def throw_exception(self):
        raise utils.PtpException(self.message, self.source)

class TypeChecker:

    def __init__(self, name, source, functions):
        self.name = name
        self.sources = set([ source ])
        self.functions = set(functions)

    def update(self, type_checker):
        assert type_checker.name == self.name
        self.sources.update(type_checker.sources)
        self.functions.update(type_checker.functions)

    def add_checks(self, tester):
        var = base.tester.new_id()

        source = min(self.sources)
        check = CheckStatement("{0} *{1};".format(self.name, base.tester.new_id()), source=source)
        check.own_message = "Invalid type '{0}'".format(self.name)
        tester.add(check)

        message = "Function '{0}' not defined for type '{1}'"
        if "token_name" in self.functions:
            decls = Declarations()
            decls.set(var, self.name + " &")
            check = CheckStatement("ca::token_name({0});".format(var),
                                   decls, source=source)
            check.own_message = message.format("token_name", self.name)
            tester.add(check)

        if "pack" in self.functions:
            decls = Declarations()
            decls.set(var, self.name + "&")
            decls.set("packer", "ca::Packer &")
            check = CheckStatement("ca::pack(packer, {0});".format(var),
                                   decls,
                                   source=source)
            check.own_message = message.format("ca::pack", self.name)
            tester.add(check)

        if "unpack" in self.functions:
            decls = Declarations()
            decls.set(var, self.name + "&")
            decls.set("unpacker", "ca::Unpacker &")
            check = CheckStatement("ca::unpack(unpacker, {0});".format(var),
                                   decls,
                                   source=source)
            check.own_message = message.format("ca::unpack", self.name)
            tester.add(check)

        if "from_octave_value" in self.functions:
            decls = Declarations()
            decls.set(var, self.name + "&")
            ovalue = base.tester.new_id()
            decls.set(ovalue, "octave_value&")
            check = CheckStatement("caoctave::from_octave_value({0},{1});".format(var, ovalue),
                                   decls,
                                   source=source)
            check.own_message = message.format("caoctave::from_octave_value", self.name)
            tester.add(check)

        if "to_octave_value" in self.functions:
            decls = Declarations()
            decls.set(var, self.name + "&")
            check = CheckStatement("return caoctave::to_octave_value({0});".format(var),
                                   decls,
                                   "octave_value",
                                   source=source)
            check.own_message = message.format("caoctave::to_octave_value", self.name)
            tester.add(check)


class PlaceChecker(base.tester.Check):

    def __init__(self, place, header):
        self.place = place
        self.header = header
        self.source = "*{0}/init_function:{1}:{2}"
        self.type_source = "*{0}/type"

    def write_prologue(self, writer):
        writer.raw_text(self.header)
        writer.raw_text("{\n")

    def write_epilogue(self, writer):
        writer.raw_text("}\n")

    def write_content(self, writer):
        code = self.place.code
        if not code:
            code = ""
        writer.raw_text(code)

    def throw_exception(self):
        if self.line == 0:
            raise utils.PtpException(self.message, self.type_source.format(self.place.id))
        raise utils.PtpException(self.message, self.source.format(self.place.id, self.line + 1, self.column))

class TransitionChecker(base.tester.Check):

    def __init__(self, transition, header):
        self.transition = transition
        self.source = "*{0}/function:{1}:{2}"
        self.header = header

    def write_prologue(self, writer):
        writer.raw_text(self.header)
        writer.raw_text("{\n")

    def write_epilogue(self, writer):
        writer.raw_text("}\n")

    def write_content(self, writer):
        code = self.transition.code
        if not code:
            code = ""
        writer.raw_text(code)

    def throw_exception(self):
        line = self.line - (len(self.transition.get_decls().get_list()) + 1)
        raise utils.PtpException(self.message, self.source.format(self.transition.id, line, self.column))

class HeadChecker(base.tester.Check):

    def __init__(self, head_code, params = "struct param\n{\n};\n"):
        self.source = "*head:{0}:{1}"
        self.head_code = head_code
        self.params = params
        self.line_offset = self.params.count("\n") - 1

    def write_prologue(self, writer):
        writer.raw_text(self.params)

    def write_epilogue(self, writer):
        pass

    def write_content(self, writer):
        writer.raw_text(self.head_code)

    def throw_exception(self):
        raise utils.PtpException(self.message, self.source.format(self.line - self.line_offset, self.column))

class Checker:

    def __init__(self, project):
        self.project = project
        self.types = {}
        self.checks = []

    def check_type(self, typename, source, functions=()):
        t = self.types.get(typename)
        if t is None:
            self.types[typename] = TypeChecker(typename, source, functions)
        else:
            self.types[typename].update(TypeChecker(typename, source, functions))

    def check_expression(self, expr, decls, return_type, source, message=None):
        self._check_expression(expr, decls, source, message)

        check = CheckStatement("return (static_cast<{0} >({1}));".format(return_type, expr), decls, return_type, source=source)
        if message:
            check.own_message = message
        else:
            check.own_message = "Invalid type of expression"
        self.checks.append(check)

    def check_may_form_vector(self, expr, decls, return_type, source, message=None):
        self._check_expression(expr, decls, source, message)

        decls = copy(decls)
        v = base.tester.new_id()
        decls.set(v, return_type)

        check = CheckStatement("{0}.push_back({1});".format(v, expr), decls, source=source)
        if message:
            check.own_message = message
        else:
            check.own_message = "Invalid type of expression"
        self.checks.append(check)

    def _check_expression(self, expr, decls, source, message):
        check = CheckStatement(expr + ";", decls, source=source)
        if message:
            check.own_message = message
        self.checks.append(check)

    def prepare_writer(self, filename):
        builder = build.Builder(self.project, filename)
        build.write_header(builder)

        if self.project.get_build_with_octave():
            builder.line("#include <caoctave.h>")

        return builder

    def check_nodes_in_nets(self):
        generator = self.project.get_generator()
        class HiddenNamespace():
            def __init__(self, name):
                self.name = name
                self.forward_decls = []
                self.checks = []

            def add_place(self, place):
                id = place.id
                code = place.code
                if not code:
                    code = ""
                place_header = generator.get_place_user_fn_header(place.id, True)
                self.forward_decls.append(place_header[:-1] + ";\n")
                place_header = self.insert_string_at_index(place_header, self.name + "::", 5)
                self.checks.append(PlaceChecker(place, place_header))

            def add_transition(self, transition):
                transition_header = generator.get_transition_user_fn_header(transition.id, True)
                vars_struct_decl_name = "struct Vars{0};\n".format(transition.id)
                self.forward_decls.append(vars_struct_decl_name)
                transition_func_decl = "void transition_fn{0}(ca::Context &ctx, Vars{0} &var);\n".format(transition.id)
                self.forward_decls.append(transition_func_decl)
                vars_index_pos = transition_header.index("Vars{0}".format(transition.id))
                vars2_index_pos = transition_header.index("Vars{0}".format(transition.id), vars_index_pos + 1)
                func_index_pos = transition_header.index("transition_fn{0}".format(transition.id))
                hnn = self.name + "::"
                transition_header = self.insert_string_at_index(transition_header, hnn, vars2_index_pos)
                transition_header = self.insert_string_at_index(transition_header, hnn, func_index_pos)
                transition_header = self.insert_string_at_index(transition_header, hnn, vars_index_pos)
                self.checks.append(TransitionChecker(transition, transition_header))

            def get_code(self):
                return "namespace {0}\n{{\n".format(self.name) + ''.join(self.forward_decls) + "\n}\n"

            def __getitem__(self, i):
                return self.checks[i]

            def __len__(self):
                return len(self.checks)

            def insert_string_at_index(self, string, substring, index):
                return string[:index] + substring + string[index:]

        hidden_namespace = HiddenNamespace("__test__")

        for net in self.project.nets:
            for place in net.places:
                hidden_namespace.add_place(place)

            for transition in net.transitions:
                hidden_namespace.add_transition(transition)

        return hidden_namespace

    def run(self):
        builder = build.Builder(self.project,
            os.path.join("/tmp", self.project.get_name() + ".h"))
        builder.write_to_file()

        clang_tester = base.tester.ClangTester()
        clang_tester.prepare_writer = self.prepare_writer
        clang_tester.add_arg([ "-I", os.path.join(paths.KAIRA_ROOT, paths.CAILIE_INCLUDE_DIR),
                         "-I", self.project.root_directory ])

        if self.project.get_build_with_octave():
            import ptp # To avoid cyclic import
            clang_tester.add_arg([ "-I", os.path.join(paths.KAIRA_ROOT, paths.CAOCTAVE_INCLUDE_DIR) ])
            clang_tester.add_arg(ptp.get_config("Octave", "INCFLAGS").split())

        if self.project.build_target == "simrun":
            clang_tester.add_arg([ "-I", os.path.join(paths.KAIRA_ROOT, paths.CASIMRUN_INCLUDE_DIR) ])

        clang_tester.add_arg(self.project.get_build_option("CFLAGS").split())
        generator = self.project.get_generator()
        clang_tester.add(HeadChecker(self.project.get_head_code(), generator.get_param_struct()))

        hidden_namespace = self.check_nodes_in_nets()
        clang_tester.add_hidden_namespace_decl(hidden_namespace)

        for check in hidden_namespace:
            clang_tester.add(check)

        for t in self.types.values():
            t.add_checks(clang_tester)

        for check in self.checks:
            clang_tester.add(check)

        check = clang_tester.run()
        if check is not None:
            check.throw_exception()
