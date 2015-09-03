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

class GenerateRefactorManager():
    def __init__(self, completion):
        self.completion = completion
        self.cursor = None

    def _check_selected_cursor(self):#maybe confirm cursor inside class and then select cursor referencend to that class
        cursor = self.completion.get_cursor_under_mouse()
        if cursor and cursor.kind in [clang.CursorKind.STRUCT_DECL, clang.CursorKind.CLASS_DECL, clang.CursorKind.UNION_DECL]:
            self.cursor = cursor
            return True
        else:
            return False

    def _insert_generated_code_to_buffer(self, code, insert_into_class):
        buffer = self.completion.editor.buffer
        end_location = self.cursor.extent.end
        line = end_location.line - self.completion.parser.get_line_offset()

        if insert_into_class:
            line -= 2
            iter = buffer.get_iter_at_line(line)
            chars = iter.get_chars_in_line()
            iter.forward_chars(chars)

            selected_class = assembly.Class(self.cursor)
            type = selected_class.get_type()
            if type == "class":
                specifier_cursor = selected_class.get_access_specifier("public")
                if specifier_cursor:
                    end_location = specifier_cursor.extent.end
                    line = end_location.line - self.completion.parser.get_line_offset() + 1
                    iter = buffer.get_iter_at_line(line)
                    buffer.insert(iter, code)
                else:
                    buffer.insert(iter, "public:\n" + code)

        else:
            iter = buffer.get_iter_at_line(line)
            buffer.insert(iter, code)

    def _get_fields_names(self):
        selected_class = assembly.Class(self.cursor)
        fields = selected_class.get_fields()
        names = []
        for f in fields:
            names.append(f.get_name())
        return names

    def get_menu_item(self):
        if not self._check_selected_cursor():
            return

        menu_item = gtk.MenuItem("Generate Pack & Unpack")
        gen_menu = gtk.Menu()
        gen_pack_fn = gtk.MenuItem("Generate Pack function")
        gen_unpack_fn = gtk.MenuItem("Generate Unpack function")
        gen_pack_unpack_macro = gtk.MenuItem("Generate Pack and Unpack macro")

        gen_pack_fn.connect("activate", lambda w: self.generate_pack_function())
        gen_unpack_fn.connect("activate", lambda w: self.generate_unpack_function())
        gen_pack_unpack_macro.connect("activate", lambda w: self.generate_pack_unpack_macro())

        gen_menu.add(gen_pack_fn)
        gen_menu.add(gen_unpack_fn)
        gen_menu.add(gen_pack_unpack_macro)
        menu_item.set_submenu(gen_menu)
        return menu_item

    def generate_pack_function(self):
        pack_fn_pattern = "\nvoid pack(ca::Packer &packer) const\n{{\n\t{0}\n}}\n\n"
        names = self._get_fields_names()
        if len(names) > 0:
            generated_code = pack_fn_pattern.format("packer << " + " << ".join(names) + ";")
        else:
            generated_code = pack_fn_pattern.format("")
        print generated_code
        self._insert_generated_code_to_buffer(generated_code, True)

    def generate_unpack_function(self):
        unpack_fn_pattern = "\nvoid unpack(ca::Unpacker &unpacker)\n{{\n\t{0}\n}}\n\n"
        names = self._get_fields_names()
        if len(names) > 0:
            generated_code = unpack_fn_pattern.format("unpacker >> " + " >> ".join(names) + ";")
        else:
            generated_code = unpack_fn_pattern.format("")
        print generated_code
        self._insert_generated_code_to_buffer(generated_code, True)

    def generate_pack_unpack_macro(self):
        pack_macro_pattern = "\nnamespace ca\n{{\n\tCA_PACK({0})\n\t{{\n\t\t{1}\n\t}}\n\n\tCA_UNPACK({2})\n\t{{\n\t\t{3}\n\t}}\n}}\n\n"
        names = self._get_fields_names()
        class_name = self.cursor.spelling
        obj_name = class_name + "_obj"

        if len(names) > 0:
            data = []
            for n in names:
                data.append(obj_name + "." + n)
            generated_code = pack_macro_pattern.format(", ".join([class_name, "packer", obj_name]), "packer << " + " << ".join(data) + ";", \
                                                        ", ".join([class_name, "unpacker", obj_name]), "unpacker >> " + " >> ".join(data) + ";")
        else:
            generated_code = pack_macro_pattern.format(", ".join([class_name, "packer", obj_name]), "", ", ".join([class_name, "unpacker", obj_name]), "")

        print generated_code
        self._insert_generated_code_to_buffer(generated_code, False)

