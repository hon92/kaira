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
import pango
import completion
import gtksourceview2 as gtks


class HighLightRule():
    def __init__(self, name):
        self.tag = gtk.TextTag(name)

    def set_properties(self):
        pass

    def create(self):
        self.set_properties()
        return self

    def get_name(self):
        return self.tag.get_property("name")

    def get_tag(self):
        return self.tag

class ErrorHighLighRule(HighLightRule):
    def __init__(self):
        name = "Error"
        HighLightRule.__init__(self, name)

    def set_properties(self):
        self.tag.set_property("underline-set", True)
        self.tag.set_property("underline", pango.UNDERLINE_ERROR)


class WarningHighLighRule(HighLightRule):
    def __init__(self):
        name = "Warning"
        HighLightRule.__init__(self, name)

    def set_properties(self):
        self.tag.set_property("underline-set", True)
        self.tag.set_property("underline", pango.UNDERLINE_SINGLE)
        self.tag.set_property("foreground", "yellow")


class Error():
    def __init__(self, message, sl, sc, el, ec, fixes):
        self.message = message
        self.sl = sl
        self.sc = sc
        self.el = el
        self.ec = ec
        self.fixes = fixes

    def get_message(self):
        return self.message

    def get_fixes_string(self):
        if len(self.fixes) == 0:
            return
        return ", ".join([fix.value for fix in self.fixes])

    def has_fix_hits(self):
        return len(self.fixes) > 0

    def get_full_info(self):
        if len(self.fixes) > 0:
            return self.message + "\nFix hints: " + self.get_fixes_string()
        else:
            return self.message

class HighLightManager():
    def __init__(self, buffer, parser):
        self.buffer = buffer
        self.rules = []
        self.tag_table = buffer.get_property("tag_table")
        parser.connect("reparsed", self.update)
        self.error_map = {}
        gutter = parser.editor.view.get_gutter(gtk.TEXT_WINDOW_LEFT)
        gutter.connect("query-tooltip", self.on_gutter_tooltip_query)
        view = parser.editor.view
        view.set_property("show-line-marks", True)
        view.set_mark_category_icon_from_pixbuf("error", completion.icons["error"])
        view.set_mark_category_icon_from_pixbuf("warning", completion.icons["warning"])
        view.set_mark_category_priority("warning", 1)
        view.set_mark_category_priority("error", 2)
        view.set_mark_category_background("error", gtk.gdk.Color(257 * 179, 257 * 147, 257 * 144))
        view.set_mark_category_background("warning", gtk.gdk.Color(257 * 235, 257 * 214, 257 * 163))

        def empty_fn():
            return True

        view.set_mark_category_tooltip_markup_func("__empty", empty_fn)

    def on_gutter_tooltip_query(self, gutter, renderer, iter, tooltip):
        line = iter.get_line()
        if self.error_map.has_key(line):
            errors = self.error_map[line]
            showed_message = []
            for error in errors:
                showed_message.append(error.get_full_info())
            tooltip.set_text("\n\n".join(showed_message))
            return True

    def add_rule(self, high_light_rule):
        if high_light_rule not in self.rules:
            self.rules.append(high_light_rule)
            self.tag_table.add(high_light_rule.get_tag())

    def highlight_code(self, rule_name, line_start, col_start, line_end, col_end):
        pass

    def clear(self):
        self.error_map.clear()
        for rule in self.rules:
            self.buffer.remove_tag_by_name(rule.get_name(), self.buffer.get_start_iter(), self.buffer.get_end_iter())
        self.buffer.remove_source_marks(self.buffer.get_start_iter(), self.buffer.get_end_iter())

    def process_diagnostic(self, parser, diagnostic):
        location = diagnostic.location
        ranges = diagnostic.ranges
        fixs = diagnostic.fixits
        line = location.line - parser.get_line_offset() - 1
        column = location.column - 1

        buffer_start_iter = self.buffer.get_start_iter()
        buffer_end_iter = self.buffer.get_end_iter()

        buffer_start_line = buffer_start_iter.get_line()
        buffer_start_col = buffer_start_iter.get_line_offset()
        buffer_end_line = buffer_end_iter.get_line()
        buffer_end_col = buffer_end_iter.get_line_offset()

        def check_border(l, c):
            if l >= buffer_start_line and l <= buffer_end_line:
                char_line_count = self.buffer.get_iter_at_line(l).get_chars_in_line()
                if c >= 0 and c <= char_line_count:
                    return True
            return False

        def get_iters(sl, sc, el = None, ec = None):
            start_iter = self.buffer.get_iter_at_line(sl)
            start_iter.set_line_offset(sc)
            if not (el and ec):
                end_iter = start_iter.copy()
                if end_iter.get_char().isspace():
                    end_iter.backward_char()
                else:
                    while not end_iter.get_char().isspace():
                        moved = end_iter.forward_char()
                        if not moved:
                            break
                        
                    #end_iter.forward_visible_word_end()
            else:
                end_iter = self.buffer.get_iter_at_line(el)
                end_iter.set_line_offset(ec)
            return start_iter, end_iter

        #check can be showed in editor
        if not check_border(line, column):
            print "line or column offset error"
            return None

        iter = self.buffer.get_iter_at_line(line)
        iter.set_line_offset(column)

        start_line = line
        start_column = column
        end_line = line
        end_column = column

        fix_hints = []
        for fix in fixs:
            fix_hints.append(fix)

        range_fail = False
        for range in ranges:
            print "---------", range.start, range.end
            start_location = range.start
            end_location = range.end
            if start_location.line == 0 and start_location.column == 0 and end_location.line == 0 and end_location.column == 0:
                range_fail = True
                continue
            start_line = start_location.line - 1 - parser.get_line_offset()
            start_column = start_location.column - 1
            end_line = end_location.line - 1 - parser.get_line_offset()
            end_column = end_location.column - 1

            if (not check_border(start_line, start_column)) or (not check_border(end_line, end_column)):
                print "clang error"
                return None
            else:
                print "clang valid position"
                start_iter, end_iter = get_iters(start_line, start_column, end_line, end_column)
                return (start_iter, end_iter, fix_hints)

        if len(ranges) == 0 or range_fail:
            start_iter, end_iter = get_iters(start_line, start_column)
            return (start_iter, end_iter, fix_hints)
        return None

    def update(self, parser, tu):
        #print "updated"
        self.clear()
        for diagnostic in tu.diagnostics:
            print diagnostic
            severity = diagnostic.severity
            range = self.process_diagnostic(parser, diagnostic)
            if not range:
                continue

            message = diagnostic.spelling
            start_iter = range[0]
            end_iter = range[1]
            fix_hits = range[2]
            sl = start_iter.get_line()
            sc = start_iter.get_line_offset()
            el = end_iter.get_line()
            ec = end_iter.get_line_offset()
            if self.error_map.has_key(sl):
                self.error_map[sl].append(Error(message, sl, sc, el, ec, fix_hits))
            else:
                self.error_map[sl] = [Error(message, sl, sc, el, ec, fix_hits)]

            print "HIGHLIGHT:sl {0}, sc {1}, el {2}, ec {3}, ranges({4}), location [{5},{6}], fixes [{7}]".format(sl, sc, el, ec, [str(r.start.line) + " " + str(r.start.column) + " " + str(r.end.line) + " " + str(r.end.column) for r in diagnostic.ranges], diagnostic.location.line, diagnostic.location.column, [f.value for f in fix_hits])

            if severity == 4:
                self.buffer.apply_tag_by_name("Error", start_iter, end_iter)
                self.buffer.create_source_mark(None, "error", start_iter)
            elif severity == 3:
                self.buffer.apply_tag_by_name("Error", start_iter, end_iter)
                self.buffer.create_source_mark(None, "error", start_iter)
            elif severity == 2:
                self.buffer.apply_tag_by_name("Warning", start_iter, end_iter)
                self.buffer.create_source_mark(None, "warning", start_iter)

    def get_error(self, line, col):
        if self.error_map.has_key(line):
            founded_error = []
            errors = self.error_map[line]
            for error in errors:
                if col >= error.sc:
                    if error.el == error.sl and col <= error.ec:
                        founded_error.append(error)
                    else:
                        end_iter = self.buffer.get_iter_at_line(error.el)
                        end_iter.set_line_offset(error.ec)
                        if col <= end_iter.get_chars_in_line():
                            founded_error.append(error)
            return founded_error
        return None
