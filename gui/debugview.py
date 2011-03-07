
import gtk
from canvas import NetCanvas, MultiCanvas
from drawing import VisualConfig
import utils

class DebugView(gtk.VBox):
	def __init__(self, app, debuglog):
		gtk.VBox.__init__(self)
		self.debuglog = debuglog
		self.frame = debuglog.get_frame(0)

		self.pack_start(self._buttons(), False, False)
		self.canvas_sc = gtk.ScrolledWindow()
		self.canvas = self._create_canvas()
		self.canvas.set_size_and_viewport_by_net()
		self.canvas_sc.add_with_viewport(self.canvas)

		self.instance_canvas_sc = gtk.ScrolledWindow()
		self.instance_canvas = self._create_instances_canvas()
		self.instance_canvas_sc.add_with_viewport(self.instance_canvas)
		self.instance_canvas.show_all()

		self.pack_start(self.canvas_sc)
		self.show_all()
		self.pack_start(self.instance_canvas_sc)

	def get_frame_pos(self):
		return int(self.scale.get_value())

	def _buttons(self):
		self.scale = gtk.HScale(gtk.Adjustment(value=0, lower=0, upper=self.debuglog.frames_count(), step_incr=1, page_incr=1, page_size=1))
		toolbar = gtk.HBox(False)

		button = gtk.ToggleButton("Instances")
		button.connect("toggled", self._view_change)
		toolbar.pack_start(button, False, False)

		button = gtk.Button("<<")
		button.connect("clicked", lambda w: self.scale.set_value(max(0, self.get_frame_pos() - 1)))
		toolbar.pack_start(button, False, False)

		self.counter_label = gtk.Label()
		toolbar.pack_start(self.counter_label, False, False)

		button = gtk.Button(">>")
		button.connect("clicked", lambda w: self.scale.set_value(min(self.debuglog.frames_count() - 1, self.get_frame_pos() + 1)))
		toolbar.pack_start(button, False, False)

		self.scale.set_draw_value(False)
		self.scale.connect("value-changed", lambda w: self.goto_frame(int(w.get_value())))
		toolbar.pack_start(self.scale)

		self.info_label = gtk.Label()
		toolbar.pack_start(self.info_label, False, False)

		self.update_labels()
		toolbar.show_all()
		return toolbar

	def goto_frame(self, frame_pos):
		self.frame = self.debuglog.get_frame(frame_pos)
		self.update_labels()
		self.redraw()

	def update_labels(self):
		max = str(self.debuglog.frames_count() - 1)
		self.counter_label.set_text("{0:0>{2}}/{1}".format(self.get_frame_pos(), max, len(max)))
		time = self.debuglog.get_time_string(self.frame)
		colors = { "I": "gray", "S" : "green", "E" : "#cc4c4c" }
		name = self.frame.name
		self.info_label.set_markup("<span font_family='monospace' background='{2}'>{0}</span>{1}".format(name, time, colors[name]))

	def redraw(self):
		self.instance_canvas.redraw()
		self.canvas.redraw()

	def _create_canvas(self):
		c = NetCanvas(self.debuglog.project.get_net(), None, OverviewVisualConfig(self))
		c.show()
		return c

	def _instance_draw(self, cr, width, height, vx, vy, vconfig, area, i):
		self.debuglog.project.get_net().draw(cr, vconfig)
		cr.set_source_rgba(0.3,0.3,0.3,0.5)
		cr.rectangle(vx,vy,width, 15)
		cr.fill()
		cr.move_to(vx + 10, vy + 11)
		cr.set_source_rgb(1.0,1.0,1.0)
		cr.show_text("node=%s   iid=%s" % (self.debuglog.get_instance_node(area, i), i))
		cr.stroke()

	def _view_for_area(self, area):
		sz = utils.vector_add(area.get_size(), (80, 95))
		pos = utils.vector_diff(area.get_position(), (40, 55))
		return (sz, pos)

	def _create_instances_canvas(self):
		def area_callbacks(area, i):
			vconfig = InstanceVisualConfig(self, area, i)
			draw_fn = lambda cr,w,h,vx,vy: self._instance_draw(cr, w, h, vx, vy, vconfig, area, i)
			click_fn = lambda position: self._on_instance_click(position, area, i)
			return (draw_fn, click_fn)
		c = MultiCanvas()
		for area in self.debuglog.project.get_net().areas():
			callbacks = [ area_callbacks(area, i) for i in xrange(self.debuglog.get_area_instances_number(area)) ]
			sz, pos = self._view_for_area(area)
			c.register_line(sz, pos, callbacks)
		c.end_of_registration()
		return c

	def _view_change(self, button):
		if button.get_active():
			self.instance_canvas_sc.show()
			self.canvas_sc.hide()
		else:
			self.instance_canvas_sc.hide()
			self.canvas_sc.show()

def filter_by_id(items, id):
	return [ x[1] for x in items if x[0] == id ]

color_running = ((0.7,0.7,0.1,0.5))
color_started = ((0.1,0.9,0.1,0.5))
color_ended = ((0.8,0.3,0.3,0.5))

class OverviewVisualConfig(VisualConfig):

	def __init__(self, debugview):
		self.debugview = debugview

	def place_drawing(self, item):
		d = VisualConfig.place_drawing(self, item)
		tokens = self.debugview.frame.get_tokens(item)
		r = []
		for iid in tokens:
			r += [ t + "@" + str(iid) for t in tokens[iid] ]
		d.set_tokens(r)
		return d

	def transition_drawing(self, item):
		frame = self.debugview.frame
		d = VisualConfig.transition_drawing(self, item)
		if filter_by_id(frame.running, item.get_id()):
				d.set_highlight(color_running)
		if filter_by_id(frame.started, item.get_id()):
				d.set_highlight(color_started)
		if filter_by_id(frame.ended, item.get_id()):
				d.set_highlight(color_ended)
		return d


class InstanceVisualConfig(VisualConfig):

	def __init__(self, debugview, area, iid):
		self.debugview = debugview
		self.area = area
		self.iid = iid

	def place_drawing(self, item):
		d = VisualConfig.place_drawing(self, item)
		if self.area.is_inside(item):
			d.set_tokens(self.debugview.frame.get_tokens(item, self.iid))
		return d

	def transition_drawing(self, item):
		frame = self.debugview.frame
		d = VisualConfig.transition_drawing(self, item)
		if self.iid in filter_by_id(frame.running, item.get_id()):
				d.set_highlight(color_running)
		if self.iid in filter_by_id(frame.started, item.get_id()):
				d.set_highlight(color_started)
		if self.iid in filter_by_id(frame.ended, item.get_id()):
				d.set_highlight(color_ended)
		return d
