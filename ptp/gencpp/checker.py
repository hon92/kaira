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

        check = CheckStatement("return ({0});".format(expr), decls, return_type, source=source)
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

    def run(self):
        builder = build.Builder(self.project,
            os.path.join("/tmp", self.project.get_name() + ".h"))

        build.write_header_file(builder)
        builder.write_to_file()

        tester = base.tester.Tester()
        tester.prepare_writer = self.prepare_writer
        tester.args = [ "-I", os.path.join(paths.KAIRA_ROOT, paths.CAILIE_INCLUDE_DIR),
                        "-I", self.project.root_directory ]

        if self.project.get_build_with_octave():
            import ptp # To avoid cyclic import
            tester.args += [ "-I", os.path.join(paths.KAIRA_ROOT, paths.CAOCTAVE_INCLUDE_DIR) ]
            tester.args += ptp.get_config("Octave", "INCFLAGS").split()

        if self.project.build_target == "simrun":
            tester.args += [ "-I", os.path.join(paths.KAIRA_ROOT, paths.CASIMRUN_INCLUDE_DIR) ]

        tester.args += self.project.get_build_option("CFLAGS").split()
        tester.run()

        generator = self.project.get_generator()
        if generator:
            import ptp
            import clang.cindex as clang

            net_data = []
            head_line_count = 0
            head_code = self.project.get_head_code()
            invisible_code = "#include \"" + os.path.join(base.paths.KAIRA_ROOT,base.paths.CAILIE_INCLUDE_DIR, "cailie.h") + "\"\n"
            net_data.append(invisible_code)
            net_data.append(head_code)
            
            for data in net_data:
                for line in data:
                    head_line_count += line.count("\n")


            nets = self.project.nets
            for net in nets:
                places = net.places
                transitions = net.transitions

                for place in places:
                    code = place.code
                    if not code:
                        code = ""
                    place_header = generator.get_place_user_fn_header(place.id, True) + "{\n" + code + "}\n"
                    net_data.append(place_header)

                for transition in transitions:
                    code = transition.code
                    if not code:
                        code = ""
                    transition_header = generator.get_transition_user_fn_header(transition.id, True) + "{\n" + code + "}\n"
                    net_data.append(transition_header)

            #args = tester.args
            data = ''.join(net_data)
            cont = True

            if not clang.Config.loaded:
                has_clang = ptp.get_config("Main", "LIBCLANG")
                if has_clang == "True":
                    path = ptp.get_config("libclang", "path")
                    clang.Config.set_library_file(path)
                else:
                    cont = False

            if cont:

                index = clang.Index.create()
                temp_file = "temp.cpp"
                unsaved_files = [(temp_file, data)]
                tu = index.parse(temp_file, ["-I/usr/include/clang/3.4/include"], unsaved_files)
                if tu:
                    diagnostics = tu.diagnostics
                    for d in diagnostics:
                        if d.severity > 2:
                            loc = d.location
                            cursor = clang.Cursor.from_location(tu, loc)
                            if cursor:
                                sem_par = cursor.semantic_parent
                                line = sem_par.location.line
                                
                                fce_name = sem_par.spelling
                                if fce_name and fce_name.startswith("place_fn"):
                                    f = []
                                    for c in fce_name:
                                        if c.isdigit():
                                            f.append(c)
                                    id = ''.join(f)
                                    f = "*{0}/type".format(id)
                                    error_line = d.location.line - head_line_count 
                                    if error_line > 1:
                                        raise utils.PtpException(d.spelling, "*" + id + "/init_function:{0}:{1}".format(str(error_line), str(d.location.column)))
                                    else:
                                        raise utils.PtpException(d.spelling, f)

        if tester.stderr:
            raise utils.PtpException(tester.stderr)

        for t in self.types.values():
            t.add_checks(tester)

        for check in self.checks:
            tester.add(check)

        check = tester.run()
        if check is not None:
            check.throw_exception()
