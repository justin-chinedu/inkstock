import enum
from base64 import b16encode
from typing import Set
from gi.repository import Gtk, Gdk

from inkex.gui import asyncme
from utils.stop_watch import StopWatch


class ChangeReceiver:
    def on_change(self, *args, **kwargs): pass


class OptionsWindow(ChangeReceiver):
    ui_file = "ui/options.ui"

    def __init__(self, change_receiver):
        self.builder = Gtk.Builder()
        self.options_values = {}
        self.options = {}
        self.__attached_options = []
        self.receiver = change_receiver
        self.builder.add_objects_from_file(self.ui_file, ["options_listbox", "options_separator"])
        self.window: Gtk.ListBox = self.builder.get_object("options_listbox")
        self.window.set_hexpand(True)
        self.window.show_all()

    def set_option(self, name, values, option_type, label=None, show_separator=True, attach=True):
        if option_type == OptionType.CHECKBOX:
            option = CheckBoxOption(name, values, self, label)
        elif option_type == OptionType.COLOR:
            option = ColorOption(name, values, self, label)
        elif option_type == OptionType.DROPDOWN:
            option = DropDownOption(name, values, self, label)
        elif option_type == OptionType.TEXTFIELD:
            option = TextFieldOption(name, values, self, label)
        elif option_type == OptionType.LINK:
            option = Link(name, values, self, label)
        elif option_type == OptionType.BUTTON:
            option = Button(name, values, self, label)
        elif option_type == OptionType.TEXTVIEW:
            option = TextView(name, values, self)
        elif option_type == OptionType.SEARCH:
            option = SearchField(name, self, label)
        elif option_type == OptionType.GROUP:
            option = Group(name, values, self, label)
            if attach:
                for value in values:
                    self.__attached_options.append(value)
        elif option_type == OptionType.SELECT:
            option = SelectOption(name, values, self, label)
        else:
            raise ValueError("Widget type not available")

        option.view.set_hexpand(False)
        if attach and not show_separator:
            self.window.add(option.view)
            self.__attached_options.append(option)
        if show_separator and attach:
            self.window.add(option.view)
            self.__attached_options.append(option)
            separator = self.get_separator()
            self.window.add(separator)

        self.options[name] = option
        self.options_values[name] = option.value
        return option
        # self.receiver.on_change(self.options)

    def get_separator(self):
        builder = Gtk.Builder()
        builder.add_objects_from_file(self.ui_file, ["options_separator"])
        separator: Gtk.Separator = builder.get_object("options_separator")
        separator.set_hexpand(False)
        return separator

    def on_change(self, option):
        self.options_values[option.name] = option.value
        for option in self.options.values():
            if option not in self.__attached_options:
                if option.name in self.options_values:
                    self.options_values.pop(option.name)
        self.receiver.on_change(self.options_values)

    def disable_option(self, name):
        if name in self.options:
            self.options[name].set_sensitive(False)

    def remove_option(self, name):
        if name in self.options:
            option = self.options[name]
            if option in self.__attached_options:
                asyncme.mainloop_only(self.window.remove)(option.view.get_parent())
                if isinstance(option, Group):
                    for value in option.values:
                        self.__attached_options.remove(value)
                self.__attached_options.remove(option)

    def attach_option(self, name):
        if name in self.options:
            option = self.options[name]
            if option not in self.__attached_options:
                asyncme.mainloop_only(self.window.add)(option.view)
                if isinstance(option, Group):
                    for value in option.values:
                        self.__attached_options.append(value)
                self.__attached_options.append(option)

    def get_options(self):
        return self.options_values


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
    def __init__(self, name, value, change_receiver, label) -> None:
        super().__init__(name, value, "options_color", change_receiver)
        self.label = self.widget("options_color_label")
        self.label.set_text(label)
        self.color_btn: Gtk.ColorButton = self.widget("options_color_btn")
        self.set_color(value)

    def set_color(self, value):
        rgba = self.color_btn.get_rgba()
        if value and rgba.parse(value):
            self.color_btn.set_rgba(rgba)

    def color_set(self, button: Gtk.ColorButton):
        rgba = button.get_rgba()
        color_rgba = tuple(map(lambda x: round(x * 255), (rgba.red, rgba.green, rgba.blue, rgba.alpha)))
        color_hex = '#{:02x}{:02x}{:02x}{:02x}'.format(*color_rgba)
        self.value = color_hex
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
        self.entry: Gtk.SearchEntry = self.widget("options_searchentry")
        self.entry.set_placeholder_text("Search")
        self.widget("options_search_label").set_text(label)
        self.value = ""

    def search_changed(self, search_entry):
        query = search_entry.get_text()
        self.value = query
        if query and (len(query) > 1):
            self.receiver.on_change(self)


class TextView(Option):
    def __init__(self, name, values, change_reciever):
        super().__init__(name, values, "options_textview", change_reciever)
        self.view.set_markup(values)
        self.value = values


class Link(Option):
    def __init__(self, name, values, change_receiver, label):
        super().__init__(name, values, "options_link", change_receiver)
        self.view.set_label(label)
        self.view.set_uri(values)
        self.value = values


class Button(Option):
    def __init__(self, name, values, change_receiver, label):
        super().__init__(name, values, "options_button", change_receiver)
        self.view.set_label(label)
        self.fn = values

    def on_click(self, btn):
        self.fn(self.name)


class Group(Option):
    def __init__(self, name, options, change_receiver, label):
        super().__init__(name, options, "options_group", change_receiver)
        self.view.set_label(label)
        self.group_list = self.widget("options_group_list")
        for option in options:
            self.add_option(option)

    def add_option(self, option):
        self.group_list.add(option.view)
        self.group_list.add(self.get_separator())

    def get_separator(self):
        builder = Gtk.Builder()
        builder.add_objects_from_file(self.ui_file, ["options_separator"])
        separator: Gtk.Separator = builder.get_object("options_separator")
        separator.set_hexpand(False)
        return separator


class SelectOption(Option):
    def __init__(self, name, options, change_receiver, label):
        super().__init__(name, options, "options_select_list", change_receiver)
        self.view.connect("row-selected", self.option_selected)
        for option in options:
            self.add_option(option)

    def add_option(self, option):
        row = SelectOptionRow(option)
        self.view.add(row)

    def option_selected(self, listbox, row):
        self.value = row.data
        print(f"row selected {row.data}")
        self.receiver.on_change(self)


class SelectOptionRow(Gtk.ListBoxRow):

    def __init__(self, view):
        super().__init__()
        self.data = view
        self.set_margin_top(10)
        self.set_size_request(50, 40)
        if isinstance(view, str):
            label = Gtk.Label(label=view)
            self.add(label)
        else:
            self.add(view)
        self.show_all()


class OptionType(enum.Enum):
    DROPDOWN, TEXTFIELD, COLOR, CHECKBOX, SEARCH, TEXTVIEW, LINK, BUTTON, GROUP, SELECT = range(10)
