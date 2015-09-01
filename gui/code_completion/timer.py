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

import gobject

class Timer():
    def __init__(self, interval, function, *args, **kwargs):
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.running = False
        self.source_set = set()
        self.source = None

    def _run(self):
        self.running = True
        self.function(*self.args, **self.kwargs)
        self.source_set.remove(self.source)

    def start(self):
        if not self.running:
            self.source = gobject.timeout_add(self.interval, self._run)
            #print "timer created " , self.source
            self.running = True
            self.source_set.add(self.source)

    def stop(self):
        if self.running:
            if self.source in self.source_set:
                removed = gobject.source_remove(self.source)
                if removed:
                    #print "removed", self.source
                    self.source_set.remove(self.source)
                else:
                    pass#print self.source ,"already finnished"
            else:
                pass
                #print "eeeeeee"
            self.running = False
            #assert len(self.source_set) == 0

    def restart(self):
        self.stop()
        self.start()