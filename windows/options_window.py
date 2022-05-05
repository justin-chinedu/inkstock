import enum
from typing import Set
from gi.repository import Gtk

from utils.stop_watch import StopWatch


class ChangeReciever():
    def on_change(self, *args, **kwargs): pass


class OptionsWindow(ChangeReciever):
    ui_file = "ui/options.ui"

    def __init__(self, change_receiver):
        self.builder = Gtk.Builder()
        self.options = {}
        self.widgets = {}
        self.receiver = change_receiver
        self.builder.add_objects_from_file(self.ui_file, ["options_listbox", "options_separator"])
        self.window: Gtk.ListBox = self.builder.get_object("options_listbox")
        self.window.set_hexpand(True)
        self.separator = self.builder.get_object("options_separator")
        self.window.show_all()

    def set_option(self, name, values, type, label=None):
        if type == OptionType.CHECKBOX:
            widget = CheckBoxOption(name, values, self, label)
        elif type == OptionType.COLOR:
            widget = ColorOption(name, values, self, label)
        elif type == OptionType.DROPDOWN:
            widget = DropDownOption(name, values, self, label)
        elif type == OptionType.TEXTFIELD:
            widget = TextFieldOption(name, values, self, label)
        elif type == OptionType.SEARCH:
            widget = SearchField(name, self, label)
        else:
            raise ValueError("Widget type not available")

        builder = Gtk.Builder()
        builder.add_objects_from_file(self.ui_file, ["options_separator"])
        separator: Gtk.Separator = builder.get_object("options_separator")
        separator.set_hexpand(False)
        widget.view.set_hexpand(False)
        self.window.add(widget.view)
        self.window.add(separator)
        self.widgets[name] = widget
        self.options[name] = widget.value
        self.receiver.on_change(self.options)

    def on_change(self, widget):
        self.options[widget.name] = widget.value
        self.receiver.on_change(self.options)

    def disable_option(self, name):
        if name in self.widgets:
            self.widgets[name].set_sensitive(False)

    def get_options(self):
        return self.options


class Option:
    ui_file = "ui/options.ui"

    def __init__(self, name, values, view_id, change_reciever) -> None:
        self.view = None
        self.widget = None
        self.builder = None
        self.name = name
        self.values = values
        self.init(view_id)
        self.receiver = change_reciever
        self.value = None

    def init(self, view_id):
        self.builder: Gtk.Builder = Gtk.Builder()
        self.builder.add_objects_from_file(self.ui_file, [view_id])
        self.builder.connect_signals(self)
        self.widget = self.builder.get_object
        self.view = self.widget(view_id)
        self.view.show_all()


class TextFieldOption(Option):
    def __init__(self, name, values, change_receiver, label) -> None:
        super().__init__(name, values, "options_textfield", change_receiver)
        self.label = self.widget("options_textfield_label")
        self.label.set_text(label)

    def changed(self, editable: Gtk.Entry):
        self.value = editable.get_text()
        self.receiver.on_change(self)


class ColorOption(Option):
    def __init__(self, name, values, change_receiver, label) -> None:
        super().__init__(name, values, "options_color", change_receiver)
        self.label = self.widget("options_color_label")
        self.label.set_text(label)

    def color_set(self, button: Gtk.ColorButton):
        self.value = button.get_color().to_string()
        self.receiver.on_change(self)


class DropDownOption(Option):
    def __init__(self, name, values, change_receiver, label) -> None:
        super().__init__(name, values, "options_dropdown", change_receiver)
        self.label = self.widget("options_dropdown_label")
        self.label.set_text(label)
        self.combo: Gtk.ComboBox = self.widget("options_dropdown_combobox")
        for value in values:
            self.combo.append_text(value)
        self.value = values[0]
        self.combo.set_active(0)
        self.receiver.on_change(self)

    def changed(self, combo):
        selected_text = combo.get_active_text()
        self.value = selected_text
        self.receiver.on_change(self)


class CheckBoxOption(Option):
    def __init__(self, name, values, change_reciever) -> None:
        super().__init__(name, values, "options_checkbox_flow", change_reciever)
        self.value = Set[str]
        for value in values:
            checkbox = Gtk.CheckButton(value)
            checkbox.connect("toggled", self.toggled)
            self.view.add(checkbox)

    def toggled(self, button: Gtk.CheckButton):
        value = button.get_label()
        if button.get_active():
            self.value.add(value)
        elif value in self.value:
            self.value.remove(value)
        self.receiver.on_change(self)


class SearchField(Option):

    def __init__(self, name, change_reciever, label):
        super().__init__(name, None, "options_search", change_reciever)
        self.widget("options_searchentry").set_placeholder_text("Search")
        self.widget("options_search_label").set_text(label)
        self.value = ""

    def search_changed(self, search_entry):
        query = search_entry.get_text()
        self.value = query
        if query and (len(query) > 1):
            self.receiver.on_change(self)


class OptionType(enum.Enum):
    DROPDOWN, TEXTFIELD, COLOR, CHECKBOX, SEARCH = range(5)
