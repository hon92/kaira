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
from ptp import base
import os
import ptp
import code
import gobject
import timer

temp_file_path = "/tmp/"
temp_file_name = "kairaclangtemp-{0}.cpp".format(os.getuid())

if os.path.exists(temp_file_path):
    if not os.path.isfile(temp_file_path + temp_file_name):
        file(temp_file_path + temp_file_name, "w+", 1)

loaded = False
if not clang.Config.loaded:
    has_clang = ptp.get_config("Main", "LIBCLANG")
    if has_clang == "True":
        path = ptp.get_config("libclang", "path")
        clang.Config.set_library_file(path)
        loaded = True

libclang_arguments = ["-I/usr/include/clang/3.4/include"] # Need to correct this with new version of Clang
kaira_hidden_include_code = ''.join(["#include \"" +
                               os.path.join(base.paths.KAIRA_ROOT,base.paths.CAILIE_INCLUDE_DIR, "cailie.h")
                               + "\"\n"])


class SourceParser(gobject.GObject):
    def __init__(self, editor):
        gobject.GObject.__init__(self)
        self.editor = editor
        self.index = clang.Index.create()
        self.tu = None
        self.code = ""
        self.line_offset = 0
        self.parsed = False
        self.file = temp_file_path + temp_file_name
        self.static_code = code.Code()
        self.static_code.add_code(kaira_hidden_include_code)
        self.static_code.add_code(self._load_param_struct())
        interval = 1000
        self.timer = timer.Timer(interval, self.reparse)
        editor.buffer.connect_after("changed", self.code_changed)

    def _load_param_struct(self):
        generator = self.editor.app.project.get_generator(load_nets=False)
        param_struct = generator.get_param_struct()
        return param_struct

    def get_parsing_options(self):
        return 0 # default

    def get_type(self):
        pass

    def get_code(self):
        return ""

    def include_macros(self):
        return False

    def include_snippets(self):
        return False

    def include_brief_comments(self):
        return False

    def get_line_offset(self):
        return self.static_code.get_lines_count() + self.line_offset

    def reparse(self):
        self.code = self.get_code()
        unsaved_files = [(self.file, self.code)]
        if not self.tu:
            self.tu = self.index.parse(self.file, libclang_arguments, unsaved_files, self.get_parsing_options())
        else:
            self.tu.reparse(unsaved_files, self.get_parsing_options())
        self.parsed = True
        #self._debug_code(self.get_code())
        self.emit("reparsed", self.tu)

    def reparse_request(self):
        self.timer.restart()

    def get_code_complete_results(self, line, column):
        #macros,snippets,brief comments
        if not self.tu:#check if data was reparsed(now it can contain old code and return invalid results)
            self.reparse()
#         if not self.is_parsed():
#             self.reparse()
        unsaved_files = [(self.file, self.get_code())]
        return self.tu.codeComplete(self.file, line + self.get_line_offset() + 1, column + 1, unsaved_files, self.include_macros(),
                                     self.include_snippets(), self.include_brief_comments())

    def code_changed(self, buffer):
        self.parsed = False

    def is_parsed(self):
        return self.parsed

    def _debug_code(self, code):
        line = 1
        lines = code.split("\n")
        for l in lines:
            print line, l
            line += 1

    def get_cursor(self, line, column):
        if self.tu:
            file = clang.File.from_name(self.tu, self.file)
            location =  clang.SourceLocation.from_position(self.tu, file, line + self.get_line_offset() + 1, column + 1)
            cursor = clang.Cursor.from_location(self.tu, location)
            return cursor
        else:
            return None

    def get_arguments(self):
        return libclang_arguments

gobject.type_register(SourceParser)
gobject.signal_new("reparsed", SourceParser, gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,))

class HeadSourceParser(SourceParser):
    def __init__(self, editor, head_comment):
        SourceParser.__init__(self, editor)
        self.head_comment = head_comment

    def get_parsing_options(self):
        return (clang.TranslationUnit.PARSE_PRECOMPILED_PREAMBLE |
                       clang.TranslationUnit.PARSE_INCLUDE_BRIEF_COMMENTS_IN_CODE_COMPLETION |
                       clang.TranslationUnit.PARSE_CACHE_COMPLETION_RESULTS)

    def get_type(self):
        return "header"

    def get_code(self):
        code = self.editor.get_text("")
        static_code = self.static_code.get_code()
        return ''.join([static_code, self.head_comment, code])


class TransitionSourceParser(SourceParser):
    transition_pattern = "\n{0}{{\n{1}}}\n"
    def __init__(self, editor, transition_header):
        SourceParser.__init__(self, editor)
        self.transition_header = transition_header
        head_comment = self.editor.app.project.get_head_comment()
        self.static_code.add_code(head_comment)

    def get_type(self):
        return "transition"

    def get_parsing_options(self):
        return (clang.TranslationUnit.PARSE_PRECOMPILED_PREAMBLE |
                       clang.TranslationUnit.PARSE_INCLUDE_BRIEF_COMMENTS_IN_CODE_COMPLETION |
                       clang.TranslationUnit.PARSE_CACHE_COMPLETION_RESULTS)

    def get_code(self):
        head_code = self.editor.app.project.get_head_code()
        self.line_offset = head_code.count("\n") + 1
        code = self.editor.get_text("")
        static_code = self.static_code.get_code()
        return ''.join([static_code, head_code, 
                        TransitionSourceParser.transition_pattern.format(self.transition_header, code)])


class PlaceSourceParser(SourceParser):
    code_pattern = "\n{0}{{\n{1}}}\n"
    def __init__(self, editor, place_header):
        SourceParser.__init__(self, editor)
        self.place_header = place_header
        head_comment = self.editor.app.project.get_head_comment()
        self.static_code.add_code(head_comment)

    def get_type(self):
        return "place"

    def get_code(self):
        head_code = self.editor.app.project.get_head_code()
        self.line_offset = head_code.count("\n") + 1
        code = self.editor.get_text("")
        static_code = self.static_code.get_code()
        return ''.join([static_code, head_code, PlaceSourceParser.code_pattern.format(self.place_header, code)])

    def get_parsing_options(self):
        return (clang.TranslationUnit.PARSE_PRECOMPILED_PREAMBLE |
                       clang.TranslationUnit.PARSE_INCLUDE_BRIEF_COMMENTS_IN_CODE_COMPLETION |
                       clang.TranslationUnit.PARSE_CACHE_COMPLETION_RESULTS)


class LabelSourceParser(SourceParser):
    def __init__(self, editor):
        SourceParser.__init__(self, editor)
        head_comment = self.editor.app.project.get_head_comment()
        self.static_code.add_code(head_comment)

    def get_type(self):
        return "label"

    def get_code(self):
        head_code = self.editor.app.project.get_head_code()
        self.line_offset = head_code.count("\n") + 1
        code = self.editor.get_text("")
        static_code = self.static_code.get_code()
        return ''.join([static_code, head_code, "\n", code])

    def get_parsing_options(self):
        return (clang.TranslationUnit.PARSE_PRECOMPILED_PREAMBLE |
                       clang.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES)


