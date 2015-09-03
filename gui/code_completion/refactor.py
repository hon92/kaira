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

