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

class PlaceHolder(gtk.EventBox):
    delimiters = ['(', ')', '{', '}', '<', '>', '[', ']', ', ', ' ', '\n','::', ';', '=', '']

    def __init__(self, editor):
        gtk.EventBox.__init__(self)
        self.buffer = editor.buffer
        self.view = editor.view
        self.history = PlaceHolderHistory()
        self.add(self._create_box())
        self.view.add_child_in_window(self, gtk.TEXT_WINDOW_TEXT, 0, 0)
        self.active = False

    def _create_box(self):
        self.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color("black"))
        self.label = gtk.Label("")
        return self.label

    def is_active(self):
        return self.active

    def is_visible(self):
        return self.get_visible()

    def show(self):
        self.active = False
        last_proposal_info = self.history.get_last()
        if not last_proposal_info:
            return

        last_proposal_info.init()
        last_proposal_info.set_index(0)
        self.show_all()

    def next(self):
        last = self.history.get_last()
        if last:
            last.next()

    def hide(self):
        self.active = False
        self.history.remove_last()
        last = self.history.get_last()
        if last:
            last.set_index(last.get_index())
        else:
            self.hide_all()

    def process_proposal(self, proposal, iter):
        self.active = True
        first_mark = self.view.buffer.create_mark(None, iter, True)
        self.history.add(PlaceHolderInfo(self, proposal, first_mark))

    def is_on_end(self):
        last = self.history.get_last()
        return last.is_on_end()

    def is_cursor_inside(self, position):
        last = self.history.get_last()
        if not last:
            return False
        start_iter = self.buffer.get_iter_at_mark(last.mark)
        if not last._marks:
            return True

        end_iter = self.buffer.get_iter_at_mark(last._marks[-1][0])
        s_offset = start_iter.get_offset()
        e_offset = end_iter.get_offset()
        return position >= s_offset and position <= e_offset

    def is_cursor_outside(self, position):
        return not self.is_cursor_inside(position)


class PlaceHolderInfo():
    def __init__(self, placeholder, proposal, mark):
        self.placeholder = placeholder
        self.buffer = placeholder.buffer
        self.proposal = proposal
        self.mark = mark
        self._marks = None
        self.index = 0
        self.max_index = 0

    def init(self):
        marks = []
        first = self.buffer.get_iter_at_mark(self.mark)
        places = self.proposal.get_placeholders()
        place_holder_count = places[-1]
        self.max_index = place_holder_count
        typed_text_len = len(places[0])
        first.forward_chars(typed_text_len)

        for index in range(1, len(places) - 1):
            w = places[index]
            l = len(w)
            if w in PlaceHolder.delimiters:
                first.forward_chars(l)
            else:
                w = w.replace("&","&amp;").replace(">","&gt;").replace("<","&lt;")
                place_holder_count -= 1
                first.backward_char()
                start_mark = self.buffer.create_mark(None, first)
                first.forward_chars(l + 1)
                end_mark = self.buffer.create_mark(None, first)
                marks.append((start_mark, end_mark, w))

        if place_holder_count < 0:
            while place_holder_count != 0:
                del marks[0]
                place_holder_count += 1

        last_mark = self.buffer.create_mark(None, first)
        marks.append((last_mark, last_mark, "End"))
        self._marks = marks

    def set_index(self, index):
        if index >= 0 and index <= self.max_index:
            start_mark, end_mark, word = self._marks[index]
            start_iter = self.buffer.get_iter_at_mark(start_mark)
            start_iter.forward_char()
            end_iter = self.buffer.get_iter_at_mark(end_mark)
            rect = self.placeholder.view.get_iter_location(start_iter)
            if index == len(self._marks) - 1:
                self.buffer.place_cursor(end_iter)
                rect = self.placeholder.view.get_iter_location(end_iter)
            else:
                self.buffer.select_range(start_iter, end_iter)
            rect.x, rect.y = self.placeholder.view.buffer_to_window_coords(gtk.TEXT_WINDOW_TEXT, rect.x, rect.y)

            if end_iter.get_line() == 0:
                rect.y += 20
            else:
                rect.y -= 20

            text = '<span color="white" size="medium">' + word +  '</span>'
            self.placeholder.label.set_markup(text)
            self.placeholder.view.move_child(self.placeholder, rect.x, rect.y)

    def get_index(self):
        return self.index

    def is_on_end(self):
        return self.index == self.max_index

    def next(self):
        if self.index + 1 <= self.max_index:
            self.index += 1
        else:
            self.index = 0
        print self.index
        self.set_index(self.index)

    def dispose(self):
        buffer = self.buffer
        buffer.delete_mark(self.mark)

        for index in range(len(self._marks) - 1):
            sm, em , w = self._marks[index]
            buffer.delete_mark(sm)
            buffer.delete_mark(em)

        buffer.delete_mark(self._marks[-1][0])


class PlaceHolderHistory():
    def __init__(self):
        self.placeholders = []

    def add(self, placeholder_info):
        self.placeholders.append(placeholder_info)

    def get(self, index):
        if index >= 0 and index < len(self.placeholders):
            return self.placeholders[index]
        else:
            return None

    def get_last(self):
        if len(self.placeholders) > 0:
            return self.placeholders[-1]
        else:
            return None

    def remove_last(self):
        last = self.get_last()
        if last:
            last.dispose()
            self.placeholders.remove(last)

    def get_index(self):
        return self.index
