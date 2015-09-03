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
import gtksourceview2 as gtksource
import paths
import completionprovider
import completer
import highlightmanager
import placeholder
import clang.cindex as clang
import os
import sys
sys.path.append("..")


def load_proposals_icons():
    theme = gtk.IconTheme()
    theme.set_search_path([paths.ICONS_COMPLETION_DIR])
    data = theme.list_icons()
    icons = {}

    for icon in data:
        icons[icon] = theme.load_icon(icon, 16, 0)
    return icons

icons = load_proposals_icons()



class Completion():
    def __init__(self, editor, parser):
        self.editor = editor
        self.parser = parser
        self.view = editor.view
        self.completion = self.view.get_completion()
        self.provider = completionprovider.CompletionProvider(self)
        self.completion.add_provider(self.provider)
        self._load_completion_settings()
        self.completer = completer.Completer(self, icons)
        self.placeholder = placeholder.PlaceHolder(editor)
        self._init_signals()

        self.window_showed = False
        self.new_results_requested = False

    def _load_completion_settings(self):
        self.completion.set_property("remember-info-visibility", True)
        self.completion.set_property("auto-complete-delay", 250)
        self.completion.set_property("accelerators", 0)
        self.completion.set_property("select-on-show", True)

    def _init_signals(self):
        #view signals
        self.view.connect("key_press_event", self.on_key_pressed)
        self.view.connect("key_release_event", self.on_key_released)
        self.view.connect_after("key_release_event", self.on_key_released_after)
        self.view.connect("button_press_event", self.on_mouse_press)
        self.view.connect("paste-clipboard", self.on_paste_from_clipboard)
        self.view.connect_after("move-cursor", self.on_move_cursor_after)
        self.view.connect_after("backspace", self.on_backspace_after)
        self.view.connect("button_release_event", self.on_mouse_release)
        self.view.connect("populate-popup", self.on_populate_context_menu)

        #completion signals
        self.completion.connect("show", self.on_completion_window_show)
        self.completion.connect("hide", self.on_completion_window_hide)

        #buffer signals
        self.view.buffer.connect_after("changed", self.on_buffer_changed_after)
        self.view.buffer.connect_after("insert-text", self.on_buffer_insert_text_after)
        self.view.buffer.connect("notify::cursor-position", self.on_cursor_position_changed)

    def on_populate(self, context):
        iter = context.get_iter()
        import time
        t = time.time()
        proposals = self.completer.get_proposals(iter)
        print time.time() - t
        self.provider.set_proposals_count(len(proposals))
        context.props.completion.move_window(iter)
        context.add_proposals(self.provider, proposals, True)

    def on_activate_proposal(self, proposal, iter):
        if self.editor.buffer.get_has_selection():
            start,end = self.view.buffer.get_selection_bounds()
            self.view.buffer.delete(start,end)

        if proposal.get_placeholders():
            self.placeholder.process_proposal(proposal, iter)

    '''singals method implementations'''

    def on_key_pressed(self, view, key):
        if key.keyval == gtk.keysyms.Tab:
            if self.placeholder.is_visible():
                self.placeholder.next()
                return True

        if key.keyval == gtk.keysyms.Escape:
            if self.placeholder.is_visible():
                self.placeholder.hide()
                return True
        if key.keyval == gtk.keysyms.semicolon:
            if self.placeholder.is_visible() and self.placeholder.is_on_end():
                self.placeholder.hide()

    def on_key_released(self, view, key):
        pass

    def on_key_released_after(self, view, key):
        pass

    def on_mouse_press(self, view, event):
        pass

    def on_paste_from_clipboard(self, view):
        pass

    def on_move_cursor_after(self, view, step, count, extend):
        pass

    def on_backspace_after(self, view):
        pass

    def on_mouse_release(self, view, event):
        pass

    def on_populate_context_menu(self, view, menu):
        goto_declaration = gtk.MenuItem("Go to declaration")
        goto_declaration.connect("activate", lambda w: self.goto_declaration())
        menu.append(goto_declaration)
        menu.show_all()

    def on_completion_window_show(self, completion):
        self.window_showed = True

    def on_completion_window_hide(self, completion):
        self.window_showed = False

    def on_buffer_changed_after(self, buffer):
        self.parser.reparse_request()

    def on_buffer_insert_text_after(self, buffer, iter, text, length):
        if self.placeholder.is_active():
            self.placeholder.show()

    def on_cursor_position_changed(self, buffer, position):
        if self.placeholder.is_visible():
            if self.placeholder.is_cursor_outside(buffer.get_cursor_position()):
                self.placeholder.hide()

    def goto_declaration(self):
        is_code_parsed = self.parser.is_parsed()
        if not is_code_parsed:
            self.parser.reparse()

        cursor = self.get_cursor_under_mouse()

        if not cursor:
            return

        referenced = cursor.referenced
        if not referenced:
            return

        location = referenced.location
        file = location.file.name

        if file == self.parser.file:
            s, e = self.editor.get_section_iters("")
            cursor_position = self.editor.buffer.get_property("cursor-position")
            cursor_iter = self.editor.buffer.get_iter_at_offset(cursor_position)
            if cursor_iter.get_offset() <= s.get_offset():
                return

            line = location.line - self.parser.get_line_offset() - s.get_line()
            column = location.column - 1

            if line > 0 and self.parser.get_type() == "header":
                self.editor.jump_to_position(("", line, column))
            elif line > 0 and (self.parser.get_type() == "place" or self.parser.get_type() == "transition"):
                self.editor.jump_to_position(("", line, column))
            else:
                line_in_head = location.line - self.parser.static_code.get_lines_count()
                if line_in_head >= 0:
                    self.editor.app.edit_head(lineno = line_in_head, colno = column)
        else:
            from mainwindow import Tab
            from codeedit import CodeFileEditor
            code_editor = CodeFileEditor(self.editor.app, self.editor.app.project.get_syntax_highlight_key(), file)
            code_editor.view.set_highlight_current_line(True)
            code_editor.jump_to_position(("", location.line, location.column - 1))
            window = self.editor.app.window
            tab_name = os.path.basename(file)
            tab = Tab(tab_name, code_editor)
            window.add_tab(tab, True)

    def get_cursor_under_mouse(self):
        position = self.view.buffer.get_cursor_position()
        iter = self.view.buffer.get_iter_at_offset(position)
        line = iter.get_line()
        col = iter.get_line_offset()
        cursor_left = self.parser.get_cursor(line, col)
        cursor_right = self.parser.get_cursor(line, col + 1)

        if not cursor_left and not cursor_right:
            return None
        #if cursor on the left side of mouse cursor is valid -> return him first
        if not (cursor_left.kind.is_invalid() or cursor_left.kind.is_unexposed()):
            return cursor_left
        elif not (cursor_right.kind.is_invalid() or cursor_right.kind.is_unexposed()):
            return cursor_right
        else:
            return None
