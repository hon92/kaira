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

import gtk
import clang.cindex as clang

class RenameDialog(gtk.Dialog):
    def __init__(self, old_name):
        gtk.Dialog.__init__(self, "Rename", None, gtk.DIALOG_MODAL,
                            (gtk.STOCK_OK, gtk.RESPONSE_ACCEPT, gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))
        self.set_size_request(300, 120)
        self.set_default_response(gtk.RESPONSE_ACCEPT)
        self.entry = gtk.Entry()
        self.entry.set_text(old_name)
        self.entry.set_property("activates-default", True)
        self.info_label = gtk.Label()
        self.vbox.pack_start(self.entry)
        self.vbox.pack_start(self.info_label)
        self.old_name = old_name

    def get_old_name(self):
        return self.old_name

    def get_new_name(self):
        return self.entry.get_text()

    def set_info(self, info_text):
        self.info_label.set_text(info_text)

# class RefactorManager():
#     def __init__(self):
#         self.dialog = None
#  
#     def _create_dialog(self):
#         pass
#  
#     def show_dialog(self):
#         assert self.dialog == None
#         self.dialog.show()
#         pass
#  
#     def check_refactor(self):
#         pass


class Refactor():
    def __init__(self, editor):
        self.managers = []
        editor.view.connect("populate-popup", self.on_populate_context_menu)

    def on_populate_context_menu(self, view, menu):
        menu_item = gtk.MenuItem("Refactor")
        refactoring_menu = gtk.Menu()
        for manager in self.managers:
            item = manager.get_menu_item()
            refactoring_menu.add(item)
        menu_item.set_submenu(refactoring_menu)
        menu.append(menu_item)
        menu.show_all()

    def add_manager(self, refactor_manager):
        self.managers.append(refactor_manager)


class RenameRefactorManager():
    def __init__(self, completion):
        self.completion = completion
        self.editor = completion.editor
        self.parser = completion.parser

    def get_menu_item(self):
        menu_item = gtk.MenuItem("Rename")
        menu_item.connect("activate", lambda w: self.refactor_code())
        return menu_item

    def refactor_code(self):
        cursor = self.completion.get_cursor_under_mouse()

        if cursor:
            referenced = cursor.referenced
            if not referenced:
                return

        old_text = referenced.spelling
        dialog = RenameDialog(old_text)

        def get_response(dialog, response):
            if response == gtk.RESPONSE_ACCEPT:
                valid = self._check(dialog, referenced)
                if valid:
                    self._run(referenced, old_text, dialog.get_new_name())
                    dialog.destroy()
            else:
                dialog.destroy()

        dialog.connect("response", get_response)
        dialog.show_all()

    def _run(self, referenced_cursor, old_name, new_name):
        location = referenced_cursor.location
        if self.parser.get_type() == "header" or (location.line < self.parser.get_line_offset() and self.parser.get_type() in ["transition", "place"]):
            self.rename_code_in_nodes(referenced_cursor, old_name, new_name)
        else: 
            self.rename_code_in_node(self.editor, referenced_cursor, old_name, new_name)

    def _check(self, dialog, referenced_cursor):
        new_name = dialog.get_new_name()
        old_name = dialog.get_old_name()

        if not new_name:
            dialog.set_info("Invalid variable name")
            return False
        if new_name == old_name:
            dialog.set_info("Name are same")
            return False
        if not self.parser.is_parsed():
            self.parser.reparse()
        if referenced_cursor.location.file.name != self.parser.tu.spelling:
            dialog.set_info("Cant refactor code outside Kaira tool")
            return False
        if not self.check_fixed_code(referenced_cursor):
            dialog.set_info("Can't refactor code in fixed code parts")
            return False
        if not self._check_scope(referenced_cursor, new_name):
            dialog.set_info("Name in scope already exists")
            return False

        dialog.set_info("Refactoring in progress...")
        return True

    def check_fixed_code(self, referenced_cursor):
        line = referenced_cursor.location.line - self.parser.get_line_offset() - 1
        s, e = self.editor.get_section_iters("")
        if line >= 0 and line < s.get_line():
            return False
        else:
            return True

    def _check_scope(self, referenced_cursor, new_name):
        def get_compound_cursor(cursor, ref_cursor):
            source_range = ref_cursor.extent
            line_start = source_range.start.line
            column_start = source_range.start.column
            line_end = source_range.end.line
            column_end = source_range.end.column

            def _find_closest_compound_cursor(cursor, found_compounds):
                if cursor.displayname == self.parser.tu.spelling:
                    found_compounds.append(cursor)
                    return

                for c in cursor.get_children():
                    kind_value = c.kind.from_param()
                    if (kind_value >= 201 and kind_value <= 209):# or kind_value in [2, 3, 4]:
                        source_range = c.extent
                        curr_start_line = source_range.start.line
                        curr_start_column = source_range.start.column
                        curr_end_line = source_range.end.line
                        curr_end_column = source_range.end.column

                        contain = True
                        if line_start >= curr_start_line and line_end <= curr_end_line:
                            if line_start == curr_start_line and column_start <= curr_start_column:
                                contain = False
                            if line_end == curr_end_line and column_end >= curr_end_column:
                                contain = False
                        else:
                            contain = False
                        if contain:
                            found_compounds.append(c)
                            _find_closest_compound_cursor(c, found_compounds)

            found_compounds = []
            _find_closest_compound_cursor(cursor, found_compounds)
            if len(found_compounds) > 0:
                return found_compounds[-1]
            else:
                return None

        def is_same_token_inside(cursor, token_name):
            for c in cursor.get_children():
                if c.kind.is_statement():
                    for decl in c.get_children():
                        if decl.displayname == token_name or decl.spelling == token_name:
                            return True
            return False

        semantic_parent = referenced_cursor.semantic_parent
        compound_cursor = get_compound_cursor(semantic_parent, referenced_cursor)
        if compound_cursor:
            contain = is_same_token_inside(compound_cursor, new_name)
            if contain:
                return False
            else:
                return True
        else:
            return False

    def rename_code_by_location(self, buffer, where, new_text, old_text, line_offset):
        for location in where[:: - 1]:
            line = location.line - 1 - line_offset
            column = location.column - 1
            iter = buffer.get_iter_at_line(line)
            iter.set_line_offset(column)
            mark = buffer.create_mark(None, iter)
            start_iter = buffer.get_iter_at_mark(mark)
            end_iter = start_iter.copy()
            end_iter.forward_chars(len(old_text))
            buffer.delete(start_iter, end_iter)
            buffer.insert(start_iter, new_text)
            buffer.delete_mark(mark)

    def rename_code_in_node(self, editor, referenced_cursor, old_name, new_name):
        places = []
        self.find_cursor_uses(self.parser.tu, self.parser.tu.cursor, referenced_cursor, places)
        editor_buffer = editor.buffer
        temp_buffer = gtk.TextBuffer()
        temp_buffer.set_text(editor_buffer.get_text(editor_buffer.get_start_iter(), editor_buffer.get_end_iter()))
        start_iter, end_iter = editor.get_section_iters("")
        start_line = start_iter.get_line()
        end_line = end_iter.get_line()
        self.rename_code_by_location(temp_buffer, places, new_name, old_name, self.parser.get_line_offset());
        new_code = temp_buffer.get_text(temp_buffer.get_iter_at_line(start_line), temp_buffer.get_iter_at_line(end_line))
        self.editor.set_text(new_code)

    def rename_code_in_nodes(self, referenced_cursor, old_name, new_name):
        head_parser = self.parser.get_type() == "header"
        project = self.editor.app.project
        parser_code = self.parser.get_code()
        temp_buffer = gtk.TextBuffer()
        temp_buffer.set_text(parser_code)
        head_code_start = temp_buffer.get_start_iter()
        if head_parser:
            head_code_end = temp_buffer.get_end_iter()
        else:
            head_code_end = temp_buffer.get_iter_at_line(self.parser.get_line_offset() - 1)
            head_code_end.forward_to_line_end()

        head_code = temp_buffer.get_text(head_code_start, head_code_end)
        line_offset = head_code_end.get_line()
        temp_index = clang.Index.create()
        temp_tu = temp_index.parse("c.cpp", self.parser.get_arguments(), [("c.cpp", head_code)])

        place_pattern = "{0}{{\n{1}}}"
        transition_pattern = "{0}{{\n{1}}}"

        generator = project.get_generator()

        for net in project.nets:
            location = referenced_cursor.location
            places = net.places()
            transitions = net.transitions()

            items = [] #contain code from all places and transitions
            items.append(head_code)
            node_info = [] #contain start_line, end_line, and place or transition where new_code should be written
            index_line = line_offset

            for place in places:
                code = place.code
                if not code:
                    continue
                place_code = place_pattern.format(generator.get_place_user_fn_header(place.get_id(), True), code)
                end_lines = place_code.count("\n")
                items.append(place_code)
                node_info.append((index_line + 3, index_line + end_lines + 1, place))
                index_line += end_lines + 1
 
            for transition in transitions:
                code = transition.code
                if not code:
                    continue
                transition_headcode = generator.get_transition_user_fn_header(transition.get_id(), True)
                transition_code = transition_pattern.format(transition_headcode, code)
                header_lines_count = transition_headcode.count("\n")
                end_lines = transition_code.count("\n")
                items.append(transition_code)
                node_info.append((index_line + header_lines_count + 2, index_line + end_lines + 1, transition))
                index_line += end_lines + 1

            all_code = "\n".join(items) #contain all code for parse and find all places where code should be rewritten
            temp_buffer.set_text(all_code)
            temp_tu.reparse([("c.cpp", all_code)])
            ref = clang.Cursor.from_location(temp_tu, location)

            where = [] #SourceLocation where is place for new code
            self.find_cursor_uses(temp_tu, temp_tu.cursor, ref, where)

            def location_sort(a, b):
                line_cmp = cmp(a.line, b.line)
                if line_cmp != 0:
                    return line_cmp
                else:
                    return cmp(a.column, b.column)

            where.sort(location_sort)
            self.rename_code_by_location(temp_buffer, where, new_name, old_name, 0)

            for info in node_info:
                start_line = info[0]
                end_line = info[1]
                place = info[2]
                start_iter_line = temp_buffer.get_iter_at_line(start_line)
                end_iter_line = temp_buffer.get_iter_at_line(end_line)
                new_code = temp_buffer.get_text(start_iter_line, end_iter_line)
                place.set_code(new_code)

        head_start = self.parser.static_code.get_lines_count()
        if head_parser:
            head_start += project.get_head_comment().count("\n")
        head_start_iter = temp_buffer.get_iter_at_line(head_start)
        head_end_iter = temp_buffer.get_iter_at_line(line_offset)
        if head_end_iter.get_char() != "\n":
            head_end_iter.forward_to_line_end()
        new_head_code = temp_buffer.get_text(head_start_iter, head_end_iter)

        window = self.editor.app.window
        reload_head = True

        if head_parser:
            self.editor.set_text(new_head_code)
            reload_head = False
        else:
            project.set_head_code(new_head_code)

        def reload_tab(tab):
            from codeedit import CodeEditor

            if(issubclass(tab.widget.__class__, CodeEditor)):
                if(isinstance(tab.key, str)):
                    if reload_head:
                        tab.widget.set_text(project.get_head_code())
                else:
                    new_code = tab.key.get_code()
                    tab.widget.set_text(new_code)

        window.foreach_tab(reload_tab)

    def find_cursor_uses(self, tu, root_cursor, cursor, places):
        referenced_cursor = cursor.referenced
        if not referenced_cursor:
            return
        current_file = tu.spelling
        if cursor.semantic_parent and cursor.lexical_parent and cursor.semantic_parent != cursor.lexical_parent:
            referenced_cursor = cursor.canonical

        name = referenced_cursor.spelling

        def _find_cursors_locations(root_cursor, referenced_cursor, places):
            for c in root_cursor.get_children():
                if not c.location.file:
                    continue
                if c.location.file.name == current_file:
                    ref = c.referenced
                    valid = False
                    sem_par = c.semantic_parent

                    if (ref and ref == referenced_cursor) or (sem_par and sem_par == referenced_cursor):
                        valid = True
                    elif ref and not referenced_cursor.is_definition():
                        defin = referenced_cursor.get_definition()
                        if defin and defin == ref:
                            valid = True

                    if (c.spelling == name or (ref and ref.spelling == name)) and c.kind.from_param() != 103:
                        if valid:
                            loc = c.location
                            if loc not in places:
                                places.append(c.location)

                    _find_cursors_locations(c, referenced_cursor, places)

        _find_cursors_locations(root_cursor, referenced_cursor, places)