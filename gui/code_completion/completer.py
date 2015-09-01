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
import proposal


def init_kind_map(result_kind_map):
    maps = {
         0 : ([6,9,10,20,23,27,28,29],-100,"var"),
         1 : ([2,3,4,31,32],-85,"class"),
         2 : ([8,26,30],-90,"func"),
         3 : ([21],-92,"func"),
         4 : ([22,33],-80,"namespace"),
         5 : ([5],-78,"enum"),
         6 : ([7],-75,"enumerator"),
         #7 : ([500,501,502,503],-70,"macro"),
         #8 : ([72],-40,"snippet")
    }

    for v in maps.values():
        icon_name = v[2]
        priority = v[1]
        for value in v[0]:
            result_kind_map[value] = (priority, icon_name)

result_kind_map = dict()
init_kind_map(result_kind_map)

class Completer():
    prefix_chars = [";", " ", "(", ".", ">", ":", "<", "[", "]", ")", "#", "-", "{", "}", "=", "\n", "\t"]

    def __init__(self, completion, icons):
        self.completion = completion
        self.parser = completion.parser
        self.icons = icons
        self.buffer = completion.view.buffer
        self.cached_results = []
        self.last_iter = (-1, -1)
        self.prefix = ""

    def set_prefix(self):
        end_pos = self.buffer.get_cursor_position()
        end_iter = self.buffer.get_iter_at_offset(end_pos)
        start_iter = end_iter.copy()

        while True:
            moved = start_iter.backward_char()
            if not moved:
                break
            if start_iter.get_char() in Completer.prefix_chars:
                start_iter.forward_char()
                break
        self.prefix = self.buffer.get_text(start_iter, end_iter)

    def _filter_proposals(self, proposal):
        return proposal.get_label().startswith(self.prefix)

    def get_new_proposals(self, line, column):
        results = self.parser.get_code_complete_results(line, column)
        if not results:
            self.cached_results = []
            return []
        else:
            proposals = self.format_results(results)
            self.cached_results = proposals
            return proposals

    def get_proposals(self, iter):
        self.set_prefix()
        line = iter.get_line()
        column = iter.get_line_offset() - len(self.prefix)
        same_line = self.last_iter[0] == line
        same_column = self.last_iter[1] == column
        new_position = not (same_line and same_column)
        proposals = []

        if (not self.completion.window_showed and (new_position or self.completion.code_changed)) or self.completion.new_results_requested:
            proposals = self.get_new_proposals(line, column)
        else:
            proposals = self.get_cached_proposals()

        if self.prefix:
            proposals = filter(self._filter_proposals, proposals)

        self.last_iter = (line, column)
        self.completion.code_changed = False
        self.completion.new_results_requested = False
        return proposals

    def get_cached_proposals(self):
        return self.cached_results

    def format_results(self, results):
        proposals = []
        result_type_chunk = None
        icon_name = ""
        info = ""
        typed_text = ""
        label_text = ""
        place_holder = None
        brief_comment = None
        availability_string = None

        for result in results.results:
            result_kind = result.cursorKind

            if result_kind_map.has_key(result_kind):
                priority, icon_name = result_kind_map[result_kind]
            else:
                continue

            completion_string = result.string
            availability_string = completion_string.availability

            if availability_string.name != "Available":
                continue

            brief_comment = completion_string.briefComment
            chunks_list = []
            place_holder = 0
            result_type_chunk = None

            for chunk in completion_string:
                if chunk.isKindInformative():
                    continue
                if chunk.isKindResultType():
                    result_type_chunk = chunk
                    continue

                chunk_info = chunk.spelling
                chunks_list.append(chunk_info)

                
                if chunk.isKindPlaceHolder():
                    place_holder += 1
                    #place_holder.append(chunks_list[-1])

                if chunk.isKindTypedText():
                    typed_text = label_text = chunks_list[-1]
                else:
                    typed_text = ''.join(chunks_list)

            info = ''.join(chunks_list)

            if result_kind == 72 and not place_holder:
                icon_name = "keyword"
                #priority = -35

            if result_type_chunk:
                label_text = ''.join((label_text, "  -->  ", result_type_chunk.spelling))

            icon = self.icons[icon_name]
            item = proposal.ProposalItem(label_text, typed_text, info, icon)

            b_comment = brief_comment.spelling
            if b_comment:
                info += "\nInformation: " + b_comment

            if place_holder > 0:
                chunks_list.append(place_holder)
                item.set_placeholders(chunks_list)

            proposals.append(item)
        return proposals
