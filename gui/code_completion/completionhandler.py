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

import sourceparser
import completion
import highlightmanager
import refactor
import renamerefactor
import generaterefactor
import infobox

class CompletionHandler():
    def __init__(self, editor):
        self.editor = editor

    def load(self):
        self.set_source_view()
        self.set_code_parser()
        self.set_features()

    def set_source_view(self):
        pass

    def set_code_parser(self):
        pass

    def set_features(self):
        pass


class HeadCompletionHandler(CompletionHandler):
    def __init__(self, editor, header):
        CompletionHandler.__init__(self, editor)
        self.parser = sourceparser.HeadSourceParser(editor, header)
        self.completion = completion.Completion(editor, self.parser)

    def set_source_view(self):
        view = self.editor.view
        view.set_highlight_current_line (self.editor.app.settings.getboolean("code_completion",
                                                                            "enable_highlight_current_line"))
        view.set_show_line_numbers (self.editor.app.settings.getboolean("code_completion",
                                                                       "enable_show_line_numbers"))
        view.set_tab_width(int(self.editor.app.settings.getfloat("code_completion",
                                                                "tab_width")))

    def set_code_parser(self):
        self.parser.reparse_request()

    def set_features(self):
        highlight_manager = highlightmanager.HighLightManager(self.editor.buffer, self.parser)
        highlight_manager.add_rule(highlightmanager.ErrorHighLighRule().create())
        highlight_manager.add_rule(highlightmanager.WarningHighLighRule().create())

        refactor_container = refactor.Refactor(self.editor)
        rename_manager = renamerefactor.RenameRefactorManager(self.completion)
        generate_manager = generaterefactor.GenerateRefactorManager(self.completion)
        refactor_container.add_manager(rename_manager)
        refactor_container.add_manager(generate_manager)

        enable_info_box = self.editor.app.settings.getboolean("code_completion", "enable_info_box")
        if enable_info_box:
            info_box = infobox.BasicWithErrorInfoBox(self.completion, highlight_manager)


class TransitionCompletionHandler(CompletionHandler):
    def __init__(self, editor, transition_header):
        CompletionHandler.__init__(self, editor)
        self.parser = sourceparser.TransitionSourceParser(editor, transition_header)
        self.completion = completion.Completion(editor, self.parser)

    def set_source_view(self):
        view = self.editor.view
        view.set_highlight_current_line (self.editor.app.settings.getboolean("code_completion",
                                                                            "enable_highlight_current_line"))
        view.set_show_line_numbers (self.editor.app.settings.getboolean("code_completion",
                                                                       "enable_show_line_numbers"))
        view.set_tab_width(int(self.editor.app.settings.getfloat("code_completion",
                                                                "tab_width")))

    def set_code_parser(self):
        self.parser.reparse_request()

    def set_features(self):
        highlight_manager = highlightmanager.HighLightManager(self.editor.buffer, self.parser)
        highlight_manager.add_rule(highlightmanager.ErrorHighLighRule().create())
        highlight_manager.add_rule(highlightmanager.WarningHighLighRule().create())

        refactor_container = refactor.Refactor(self.editor)
        rename_manager = renamerefactor.RenameRefactorManager(self.completion)
        refactor_container.add_manager(rename_manager)

        enable_info_box = self.editor.app.settings.getboolean("code_completion", "enable_info_box")
        if enable_info_box:
            info_box = infobox.BasicWithErrorInfoBox(self.completion, highlight_manager)

class PlaceCompletionHandler(CompletionHandler):
    def __init__(self, editor, place_header):
        CompletionHandler.__init__(self, editor)
        self.parser = sourceparser.PlaceSourceParser(editor, place_header)
        self.completion = completion.Completion(editor, self.parser)

    def set_source_view(self):
        view = self.editor.view
        view.set_highlight_current_line (self.editor.app.settings.getboolean("code_completion",
                                                                            "enable_highlight_current_line"))
        view.set_show_line_numbers (self.editor.app.settings.getboolean("code_completion",
                                                                       "enable_show_line_numbers"))
        view.set_tab_width(int(self.editor.app.settings.getfloat("code_completion",
                                                                "tab_width")))

    def set_code_parser(self):
        self.parser.reparse_request()

    def set_features(self):
        highlight_manager = highlightmanager.HighLightManager(self.editor.buffer, self.parser)
        highlight_manager.add_rule(highlightmanager.ErrorHighLighRule().create())
        highlight_manager.add_rule(highlightmanager.WarningHighLighRule().create())

        refactor_container = refactor.Refactor(self.editor)
        rename_manager = renamerefactor.RenameRefactorManager(self.completion)
        refactor_container.add_manager(rename_manager)

        enable_info_box = self.editor.app.settings.getboolean("code_completion", "enable_info_box")
        if enable_info_box:
            info_box = infobox.BasicWithErrorInfoBox(self.completion, highlight_manager)

class LabelCompletionHandler(CompletionHandler):
    def __init__(self, editor):
        CompletionHandler.__init__(self, editor)
        self.parser = sourceparser.LabelSourceParser(editor)
        self.completion = completion.Completion(editor, self.parser)

    def set_source_view(self):
        view = self.editor.view
        view.set_highlight_current_line (self.editor.app.settings.getboolean("code_completion",
                                                                            "enable_highlight_current_line"))
        view.set_show_line_numbers (False)
        view.set_tab_width(int(self.editor.app.settings.getfloat("code_completion",
                                                                "tab_width")))

    def set_code_parser(self):
        self.parser.reparse_request()

    def set_features(self):
        highlight_manager = highlightmanager.HighLightManager(self.editor.buffer, self.parser)
        highlight_manager.add_rule(highlightmanager.ErrorHighLighRule().create())
        highlight_manager.add_rule(highlightmanager.WarningHighLighRule().create())

        def is_placeholder_visible():
            return self.completion.placeholder.is_visible()

        self.editor.view.place_holder_feature = is_placeholder_visible