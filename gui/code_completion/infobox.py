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
import timer
import completer
import completion
from mpl_toolkits.gtktools import error_message

class InfoBox(gtk.EventBox):
    def __init__(self, completion):
        gtk.EventBox.__init__(self)
        self.completion = completion
        self.editor = self.completion.editor
        self.view = self.editor.view
        self.buffer = self.editor.buffer
        show_delay = int(self.editor.app.settings.getfloat("code_completion","delay_info_box"))
        self.box = self.create_box()
        self.add(self.box)
        self.view.add_child_in_window(self, gtk.TEXT_WINDOW_TEXT, 0, 0)
        self.timer = timer.Timer(show_delay, self.show)
        self.editor.app.window.connect("leave_notify_event", lambda w, e : self.hide())
        self.view.connect("motion_notify_event", self.on_mouse_move)
        self.cursor = None

    def create_box(self):
        pass

    def set_data(self):
        pass

    def get_size(self):
        pass

    def show_request(self):
        self.hide()
        self.timer.restart()

    def show(self):
        self.show_all()

    def hide(self):
        self.hide_all()

    def set_box_position(self, mouse_x, mouse_y):
        mx = int(mouse_x)
        my = int(mouse_y)

        box_w, box_h = self.get_size()
        view_w, view_h = self.view.size_request()
        iter = self.view.get_iter_at_location(mx, my)

        if iter.get_line() > 0:
            iter.backward_line()
            my -= box_h / 2
        else:
            iter.forward_line()
            my += box_h / 2

        rec = self.view.get_iter_location(iter)
        my += rec.y - my

        if mx < 0:
            mx = 0
        if mx + box_w > view_w:
            mx = view_w - box_w
        if my < 0:
            my = 0
        if my + box_h > view_h:
            my = view_h - box_h
        self.view.move_child(self, mx, my)

    def show_box(self, x, y):
        set = self.set_data()
        if set:
            self.set_box_position(x, y)
            self.show_request()

    def on_mouse_move(self, view, event):
        bx, by = self.view.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, int(event.x), int(event.y))
        iter = self.view.get_iter_at_location(int(bx), int(by))
        line = iter.get_line()
        col = iter.get_line_offset()
        self.cursor = self.completion.parser.get_cursor(line, col)
        self.show_box(event.x, event.y)


class BasicInfoBox(InfoBox):
    def __init__(self, completion):
        InfoBox.__init__(self, completion)

    def create_box(self):
        container = gtk.VBox()
        self.label = gtk.Label("")
        self.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("black"))
        self.label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse("white"))
        container.add(self.label)
        return container

    def set_data(self):
        if not self.cursor:
            return

        text = self.cursor.spelling or self.cursor.displayname
        self.label.set_text(text)
        return True

    def get_size(self):
        size = self.label.size_request()
        return (size[0], size[1])


class IconInfoBox(InfoBox):
    def __init__(self, compl):
        InfoBox.__init__(self, compl)
        self.kind_map = completer.result_kind_map
        self.icons = completion.icons

    def set_data(self):
        if not self.cursor:
            return

        result_kind = self.cursor.kind.value
        if self.kind_map.has_key(result_kind):
            p, icon_name = self.kind_map[result_kind]
            self.icon.set_from_pixbuf(self.icons[icon_name])
        else:
            self.icon.clear()

        data_display_name = self.cursor.displayname
        
        if not data_display_name:
            data_display_name = self.cursor.spelling

        if not data_display_name:
            data_display_name = ""

        data_type = self.cursor.type.get_result().spelling
        if not data_type:
            data_type = self.cursor.type.spelling

        self.type_label.set_text(data_type)
        self.info_label.set_text(data_display_name + " (" + self.cursor.kind.name + ")")
        return True

    def create_box(self):
        self.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("black"))
        container = gtk.HBox()
        self.icon = gtk.Image()
        self.type_label = gtk.Label("")
        self.type_label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse("yellow"))
        self.info_label = gtk.Label("")
        self.info_label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse("white"))
        self.separator_label = gtk.Label(" -> ")
        self.separator_label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse("red"))
        container.add(self.icon)
        container.add(self.type_label)
        container.add(self.separator_label)
        container.add(self.info_label)
        return container

    def get_size(self):
        ics = self.icon.size_request()
        tls = self.type_label.size_request()
        ils = self.info_label.size_request()
        sls = self.separator_label.size_request()

        return (ics[0] + tls[0] + ils[0] + sls[0], ics[1] + tls[1] + ils[1] + sls[1])

class BasicWithErrorInfoBox(BasicInfoBox):
    def __init__(self, completion, highlight_manager):
        BasicInfoBox.__init__(self, completion)
        self.highlight_manager = highlight_manager
        self.error = None

    def create_box(self):
        return BasicInfoBox.create_box(self)

    def on_mouse_move(self, view, event):
        bx, by = self.view.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, int(event.x), int(event.y))
        iter = self.view.get_iter_at_location(int(bx), int(by))
        gutter = self.view.get_gutter(gtk.TEXT_WINDOW_LEFT)
        widget_w = event.window.get_geometry()[2]
        view_width = self.view.get_visible_rect().width
        if view_width != widget_w:
            self.timer.stop()
            self.hide()
            return

        line = iter.get_line()
        col = iter.get_line_offset()
        self.cursor = self.completion.parser.get_cursor(line, col)
        self.error = self.highlight_manager.get_error(line, col)
        self.show_box(event.x, event.y)

    def set_data(self):
        if self.error:
            message_pattern = "Code error: {0}{1}"
            show_message = []
            for error in self.error:
                error_message = error.get_message()
                if error.has_fix_hits():
                    fm = "\nFix hits: " + error.get_fixes_string()
                    message = message_pattern.format(error_message, fm)
                else:
                    message = message_pattern.format(error_message, "")
                show_message.append(message)

            self.label.set_text("\n\n".join(show_message))
            return True
        else:
            return BasicInfoBox.set_data(self)

