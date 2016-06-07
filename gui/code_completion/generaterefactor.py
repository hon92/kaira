#
#    Copyright (C) 2014 Jan Homola
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

import clang.cindex as clang
import gtk
import assembly
import ptp


class CodeGenerator():
    def __init__(self):
        self.available = False

    def get_menu_item(self):
        pass

    def get_code(self):
        pass

    def check_available(self, cursor):
        pass

    def get_code_position(self): # tuple (line, col)
        pass

class PackFnGenerator(CodeGenerator):
    def __init__(self):
        CodeGenerator.__init__(self)

    def get_menu_item(self):
        if not self.available:
            return
        gen_pack_fn = gtk.MenuItem("Pack function")
        gen_pack_fn.set_tooltip_text("Create Pack function:\n{0}".format(self.get_code()))
        return gen_pack_fn

    def check_available(self, cursor):
        if cursor and cursor.kind in [clang.CursorKind.STRUCT_DECL, clang.CursorKind.CLASS_DECL, clang.CursorKind.UNION_DECL, clang.CursorKind.CLASS_TEMPLATE]:
            self.cursor = cursor
            self.available = True
            return True
        self.available = False
        return False

    def get_code(self):
        writer = ptp.gencpp.writer.CppWriter()
        declaration = "void pack(ca::Packer &packer) const"
        code = ""
        target_class = assembly.Class(self.cursor)
        public_cursor = target_class.get_access_specifier("public")
        class_attributes = [a.get_name() for a in target_class.get_fields()]

        if len(class_attributes) > 0:
            code = "\tpacker << " + " << ".join(class_attributes) + ";"

        if not public_cursor:
            writer.line("public:")

        writer.indent_push()
        writer.write_function(declaration, code)
        return writer.get_string()

    def get_code_position(self):
        range = self.cursor.extent
        line = range.end.line - 2
        col = 0
        return (line, col)


class UnPackFnGenerator(CodeGenerator):
    def __init__(self):
        CodeGenerator.__init__(self)

    def get_menu_item(self):
        if not self.available:
            return
        gen_unpack_fn = gtk.MenuItem("Unpack function")
        gen_unpack_fn.set_tooltip_text("Create Unpack function:\n{0}".format(self.get_code()))
        return gen_unpack_fn

    def check_available(self, cursor):
        if cursor and cursor.kind in [clang.CursorKind.STRUCT_DECL, clang.CursorKind.CLASS_DECL, clang.CursorKind.UNION_DECL, clang.CursorKind.CLASS_TEMPLATE]:
            self.cursor = cursor
            self.available = True
            return True
        self.available = False
        return False

    def get_code(self):
        writer = ptp.gencpp.writer.CppWriter()
        declaration = "void unpack(ca::Unpacker &unpacker)"
        target_class = assembly.Class(self.cursor)
        public_cursor = target_class.get_access_specifier("public")
        class_attributes = [a.get_name() for a in target_class.get_fields()]
        code = ""
        if len(class_attributes) > 0:
            code = "\tunpacker >> " + " >> ".join(class_attributes) + ";"

        if not public_cursor:
            writer.line("public:")

        writer.indent_push()
        writer.write_function(declaration, code)
        return writer.get_string()

    def get_code_position(self):
        range = self.cursor.extent
        line = range.end.line - 2
        col = 0
        return (line, col)

class PackUnpackMacroGenerator(CodeGenerator):
    def __init__(self):
        CodeGenerator.__init__(self)

    def get_menu_item(self):
        if not self.available:
            return
        gen_pack_unpack_macro = gtk.MenuItem("Pack and Unpack macro")
        gen_pack_unpack_macro.set_tooltip_text("Create Pack and Unpack macro:\n{0}".format(self.get_code()))
        return gen_pack_unpack_macro

    def check_available(self, cursor):
        if cursor and cursor.kind in [clang.CursorKind.STRUCT_DECL, clang.CursorKind.CLASS_DECL, clang.CursorKind.UNION_DECL, clang.CursorKind.CLASS_TEMPLATE]:
            self.cursor = cursor
            self.available = True
            return True
        self.available = False
        return False

    def get_code(self):
        class_name = self.cursor.spelling
        obj_name = class_name + "_val"
        namespace = "namespace ca"
        pack_m = "CA_PACK({0})".format(", ".join([class_name, "packer", obj_name]))
        pack_m_code = ""

        unpack_m = "CA_UNPACK({0})".format(", ".join([class_name, "unpacker", obj_name]))
        unpack_m_code = ""

        target_class = assembly.Class(self.cursor)
        class_attributes = [a.get_name() for a in target_class.get_fields()]

        if len(class_attributes) > 0:
            data = [obj_name + "." + attr for attr in class_attributes]
            pack_m_code = "\tpacker << " + " << ".join(data) + ";"
            unpack_m_code = "\tunpacker >> " + " >> ".join(data) + ";"

        writer = ptp.gencpp.writer.CppWriter()
        writer.line(namespace)
        writer.block_begin()
        writer.indent_push()
        writer.write_function(pack_m, pack_m_code)
        writer.emptyline()
        writer.write_function(unpack_m, unpack_m_code)
        writer.indent_pop()
        writer.block_end()
        return writer.get_string()

    def get_code_position(self):
        range = self.cursor.extent
        line = range.end.line
        col = 0
        return (line, col)


class TokenNameGenerator(CodeGenerator):
    def __init__(self):
        CodeGenerator.__init__(self)

    def get_menu_item(self):
        if not self.available:
            return
        gen_tn_fn = gtk.MenuItem("TokenName function")
        gen_tn_fn.set_tooltip_text("Create token_name function:\n{0}".format(self.get_code()))
        return gen_tn_fn

    def check_available(self, cursor):
        if cursor and cursor.kind in [clang.CursorKind.STRUCT_DECL, clang.CursorKind.CLASS_DECL, clang.CursorKind.UNION_DECL, clang.CursorKind.CLASS_TEMPLATE]:
            self.cursor = cursor
            self.available = True
            return True
        self.available = False
        return False

    def get_code(self):
        writer = ptp.gencpp.writer.CppWriter()
        declaration = "std::string token_name() const"
        target_class = assembly.Class(self.cursor)
        code = "return \"{0}\";"
        code = code.format(target_class.class_cursor.spelling)
        writer.indent_push()
        writer.write_function(declaration, code)
        return writer.get_string()

    def get_code_position(self):
        range = self.cursor.extent
        line = range.end.line - 2
        col = 0
        return (line, col)


class TokenNameMacroGenerator(CodeGenerator):
    def __init__(self):
        CodeGenerator.__init__(self)

    def get_menu_item(self):
        if not self.available:
            return
        gen_tn_macro = gtk.MenuItem("TokenName macro")
        gen_tn_macro.set_tooltip_text("Create token_name macro:\n{0}".format(self.get_code()))
        return gen_tn_macro

    def check_available(self, cursor):
        if cursor and cursor.kind in [clang.CursorKind.STRUCT_DECL, clang.CursorKind.CLASS_DECL, clang.CursorKind.UNION_DECL, clang.CursorKind.CLASS_TEMPLATE]:
            self.cursor = cursor
            self.available = True
            return True
        self.available = False
        return False

    def get_code(self):
        class_name = self.cursor.spelling
        obj_name = class_name + "_val"
        namespace = "namespace ca"
        tn_m = "CA_TOKEN_NAME({0}, {1})".format(class_name, obj_name)
        code = "return \"{0}\";".format(class_name)
        writer = ptp.gencpp.writer.CppWriter()
        writer.line(namespace)
        writer.block_begin()
        writer.indent_push()
        writer.write_function(tn_m, code)
        writer.indent_pop()
        writer.block_end()
        return writer.get_string()

    def get_code_position(self):
        range = self.cursor.extent
        line = range.end.line
        col = 0
        return (line, col)


class GenerateRefactorManager():
    def __init__(self, completion):
        self.completion = completion
        self.cursor = None
        self.code_generators = []

    def add_code_generator(self, code_generator):
        self.code_generators.append(code_generator)

    def _insert_generated_code_to_buffer(self, generated_code, line, col = 0):
        buffer = self.completion.editor.buffer
        line -= self.completion.parser.get_line_offset()
        iter = buffer.get_iter_at_line(line)
        iter.set_line_offset(col)
        chars_count = iter.get_chars_in_line()
        iter.forward_chars(chars_count)
        buffer.insert(iter, generated_code)

    def run_generator(self, menu_item, generator):
        code = generator.get_code()
        line, col = generator.get_code_position()
        self._insert_generated_code_to_buffer(code, line, col)

    def get_menu_item(self):
        selected_cursor = self.completion.get_cursor_under_mouse()

        menu_item = gtk.MenuItem("Generate")
        gen_menu = gtk.Menu()
        for generator in self.code_generators:
            if generator.check_available(selected_cursor):
                gen_item = generator.get_menu_item()
                if gen_item:
                    gen_menu.add(gen_item)
                    gen_item.connect("activate", self.run_generator, generator)

        if len(gen_menu) == 0:
            return
        menu_item.set_submenu(gen_menu)
        return menu_item
