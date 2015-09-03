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


class Variable():
    def __init__(self, var_decl_cursor):
        self.var_cursor = var_decl_cursor

    def get_name(self):
        return self.var_cursor.spelling

    def get_datatype(self):
        return self.var_cursor.type.spelling

class Function():
    def __init__(self, fn_cursor):
        pass

    def get_name(self):
        pass

    def get_return_type(self):
        pass

    def get_parameters(self):
        pass


class Class():
    def __init__(self, class_cursor):
        self.class_cursor = class_cursor

    def _get_specifier_string(self, specifier_cursor):
        for token in specifier_cursor.get_tokens():
            if token.kind == clang.TokenKind.KEYWORD and token.cursor == specifier_cursor:
                if token.spelling == "public":
                    return "public"
                elif token.spelling == "protected":
                    return "protected"
                elif token.spelling == "private":
                    return "private"
                else:
                    return "invalid"

    def get_type(self):
        kind = self.class_cursor.kind
        if kind == clang.CursorKind.STRUCT_DECL:
            return "struct"
        elif kind == clang.CursorKind.CLASS_DECL:
            return "class"
        elif kind == clang.CursorKind.UNION_DECL:
            return "union"
        else:
            return ""

    def get_access_specifier(self, type):
        for cursor in self.class_cursor.get_children():
            if cursor.kind == clang.CursorKind.CXX_ACCESS_SPEC_DECL:
                specifier = self._get_specifier_string(cursor)
                if specifier == type:
                    return cursor
        return None

    def get_methods(self):
        pass

    def get_method(self, name):
        pass

    def get_field(self, name):
        pass

    def get_fields(self, type = "public"):
        fields = []
        specifier = "private"
        for cursor in self.class_cursor.get_children():
            if cursor.kind == clang.CursorKind.CXX_ACCESS_SPEC_DECL:
                specifier = self._get_specifier_string(cursor)
            elif cursor.kind == clang.CursorKind.FIELD_DECL and specifier == type:
                fields.append(Variable(cursor))
        return fields

class Assembly():
    def __init__(self, tu):
        assert tu != None
        self.tu = tu
        self.tu_cursor = tu.cursor

    def get_class(self, name):
        for cursor in self.tu_cursor.get_children():
            if not cursor.location.file:
                continue
            if cursor.location.file.name != self.tu.spelling:
                continue
            if cursor.kind in [clang.CursorKind.STRUCT_DECL, clang.CursorKind.CLASS_DECL, clang.CursorKind.UNION_DECL]:
                if cursor.spelling == name:
                    return Class(cursor)
        return None

    def get_classes(self):
        classes = []
        for cursor in self.tu_cursor.get_children():
            if not cursor.location.file:
                continue
            if cursor.location.file.name != self.tu.spelling:
                continue
            if cursor.kind in [clang.CursorKind.STRUCT_DECL, clang.CursorKind.CLASS_DECL, clang.CursorKind.UNION_DECL]:
                classes.append(Class(cursor))
        return classes

    def global_variables(self):
        pass

    def global_functions(self):
        pass






