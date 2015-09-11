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


class TokenNameChecker(base.tester.Check):
    def __init__(self, class_name, source, method_def, macro_def):
        self.source = source
        self.class_name = class_name
        self.obj_name = "__val"
        self.fn_prefix = "__token_name_test"
        self.id = self.new_id()
        self.method_def = method_def
        self.macro_def = macro_def

    def set_checks(self, types_to_check, tester):
        for type in types_to_check:
            method_def = self.method_def.copy()
            method_def.class_name = type
            macro_def = self.macro_def.copy()
            macro_def.parameters = [type]
            tester.add_function_check(base.tester.MethodOrMacroDefinition(method_def, macro_def))

    def write_prologue(self, writer):
        writer.raw_text("void {0}{1}(const {2} &{3})\n{{\n".format(self.fn_prefix, self.id, self.class_name, self.obj_name))

    def write_epilogue(self, writer):
        writer.raw_text("}")

    def write_content(self, writer):
        writer.raw_text("\tca::token_name({0});\n".format(self.obj_name))

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
            macro = base.tester.MacroDefinition("token_name", [self.name])
            method = base.tester.MethodDefinition("token_name", self.name, "std::string", const = True)
            tester.add_place_type_check(TokenNameChecker(self.name, source, method, macro))

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

class ParamChecker(base.tester.Check):

    def __init__(self, param = "struct param\n{\n};\n"):
        self.source = "param"
        self.param = param
        self.message = "Invalid argument in project parameters"

    def write_prologue(self, writer):
        pass

    def write_epilogue(self, writer):
        pass

    def write_content(self, writer):
        writer.raw_text(self.param)

    def throw_exception(self):
        raise utils.PtpException(self.message, self.source)

class HeadChecker(base.tester.Check):

    def __init__(self, head_code):
        self.source = "*head:{0}:{1}"
        self.head_code = head_code

    def write_prologue(self, writer):
        pass

    def write_epilogue(self, writer):
        pass

    def write_content(self, writer):
        writer.raw_text(self.head_code)

    def throw_exception(self):
        raise utils.PtpException(self.message, self.source.format(self.line + 1, self.column))

class SimRunChecker(base.tester.Check):

    def __init__(self, code):
        self.source = "*communication-model:{0}:{1}"
        self.code = code

    def write_prologue(self, writer):
        writer.raw_text("ca::IntTime packet_time(" \
                 "casr::Context &ctx, int source_id, int target_id, size_t size)\n{\n")

    def write_epilogue(self, writer):
        writer.raw_text("}")

    def write_content(self, writer):
        writer.raw_text(self.code)

    def throw_exception(self):
        raise utils.PtpException(self.message, self.source.format(self.line + 1, self.column))

class HiddenNamespaceChecker(base.tester.Check):
 
    def __init__(self, name, project, tester):
        self.source = ""
        self.name = name
        self.project = project
        self.tester = tester
        self.namespace = "namespace {0}\n{{\n{1}\n}}\n"
        self.forward_declarations = []
        self.generator = project.get_generator()
        self.node_checks = []
        self.load_nodes()

    def get_node_checks(self, tester):
        for check in self.node_checks:
            tester.add(check)

    def load_nodes(self):
        for net in self.project.nets:
            for place in net.places:
                self._load_place(place)
            for transition in net.transitions:
                self._load_transition(transition)

    def _load_place(self, place):
        place_header = self.generator.get_place_user_fn_header(place.id, True)
        self.forward_declarations.append(place_header[:-1] + ";\n")
        place_header = self.insert_string_at_index(place_header, self.name + "::", 5)
        self.node_checks.append(PlaceChecker(place, place_header))

    def _load_transition(self, transition):
        transition_header = self.generator.get_transition_user_fn_header(transition.id, True)
        vars_struct_decl_name = "struct Vars{0};\n".format(transition.id)
        self.forward_declarations.append(vars_struct_decl_name)
        args = [ "ca::Context &ctx, Vars{0} &var".format(str(transition.id)) ]
        if transition.clock:
            args.append("ca::Clock &clock")
        transition_func_decl = "void transition_fn{0}({1});\n".format(transition.id, ', '.join(args))
        self.forward_declarations.append(transition_func_decl)
        vars_index_pos = transition_header.index("Vars{0}".format(transition.id))
        vars2_index_pos = transition_header.index("Vars{0}".format(transition.id), vars_index_pos + 1)
        func_index_pos = transition_header.index("transition_fn{0}".format(transition.id))
        hnn = self.name + "::"
        transition_header = self.insert_string_at_index(transition_header, hnn, vars2_index_pos)
        transition_header = self.insert_string_at_index(transition_header, hnn, func_index_pos)
        transition_header = self.insert_string_at_index(transition_header, hnn, vars_index_pos)
        self.node_checks.append(TransitionChecker(transition, transition_header))

    def insert_string_at_index(self, string, substring, index):
        return string[:index] + substring + string[index:]

    def write_prologue(self, writer):
        pass
 
    def write_epilogue(self, writer):
        pass
 
    def write_content(self, writer):
        writer.raw_text(self.namespace.format(self.name, ''.join(self.forward_declarations)))
 
    def throw_exception(self):
        index = self.line - 2
        node_check = self.node_checks[index]

        if isinstance(node_check, PlaceChecker):
            source = node_check.type_source.format(node_check.place.id)
            raise utils.PtpException(self.message, source)
        else:
            raise utils.PtpException(self.message, "") 


class Checker:

    def __init__(self, project):
        self.project = project
        self.types = {}
        self.checks = []
        self.functions_checks = []

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
        if self.project.build_target == "simrun":
            builder.line("#include <simrun.h>")
        return builder

    def check_trace_fn(self, fn_name, type):
        trace_fn_def = base.tester.TraceFunctionDefinition(fn_name, type)
        self.functions_checks.append(trace_fn_def)

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
        if self.project.build_target == "simrun":
            clang_tester.add(SimRunChecker(self.project.communication_model_code))

        clang_tester.add(ParamChecker(generator.get_param_struct()))
        head_checker = HeadChecker(self.project.get_head_code())
        clang_tester.add(head_checker)
        hidden_namespace = HiddenNamespaceChecker("__test__", self.project, clang_tester)
        clang_tester.add(hidden_namespace)
        hidden_namespace.get_node_checks(clang_tester)

        for fn in self.functions_checks:
            clang_tester.add_function_check(fn)
 
        for t in self.types.values():
            t.add_checks(clang_tester)

        for check in self.checks:
            clang_tester.add(check)

        check = clang_tester.run()
        if check is not None:
            if isinstance(check, base.tester.FunctionCheck):
                check.throw_exception(head_checker.start_line)
            else:
                check.throw_exception()
