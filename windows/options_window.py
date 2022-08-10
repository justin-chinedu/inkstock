import enum
from typing import Set
from gi.repository import Gtk

from core.utils import asyncme


class OptionsChangeListener:
    def on_change(self, *args, **kwargs): raise NotImplementedError()


class OptionsWindow(OptionsChangeListener):
    ui_file = "ui/options_window.ui"

    def __init__(self, change_receiver):
        self.builder = Gtk.Builder()
        self.options_values = {}
        self.options = {}
        self.__attached_options = []
        self.receiver = change_receiver

        self.builder.add_from_file(self.ui_file)
        self.window: Gtk.ScrolledWindow = self.builder.get_object("options_scroll")
        self.window.show_all()
        self.box: Gtk.Box = self.window.get_child().get_child()

        self.__enabled = True

    def __add__widget(self, widget):
        self.box.pack_start(widget, False, False, 0)

    def set_option(self, name, values, option_type, label=None, show_separator=True, attach=True, allow_multiple=True,
                   **kwargs):
        self.__enabled = False
        if not allow_multiple:
            # remove any other duplicate if Widget is attached
            self.remove_option(name)

        if option_type == OptionType.CHECKBOX:
            option = CheckBoxOption(name, values, self)
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
            option = SelectOption(name, values, self, **kwargs)
        else:
            raise ValueError("Widget display_type not available")

        option.view.set_hexpand(False)
        if attach and not show_separator:
            self.__add__widget(option.view)
            self.__attached_options.append(option)
        if show_separator and attach:
            self.__add__widget(option.view)
            self.__attached_options.append(option)
            option.view.set_margin_bottom(30)

        self.options[name] = option
        self.options_values[name] = option.value
        self.__enabled = True
        if option_type == OptionType.BUTTON:
            print(option.view.get_toplevel())

        return option

    def on_change(self, option):
        self.options_values[option.name] = option.value
        for option in self.options.values():
            if option not in self.__attached_options:
                if option.name in self.options_values:
                    self.options_values.pop(option.name)
        if self.__enabled:
            self.receiver.on_change(self.options_values)

    def disable_option(self, name):
        if name in self.options:
            self.options[name].set_sensitive(False)

    def remove_option(self, name):
        if name in self.options:
            option = self.options[name]
            if option in self.__attached_options:
                asyncme.mainloop_only(self.box.remove)(option.view)
                if isinstance(option, Group):
                    for value in option.values:
                        self.__attached_options.remove(value)
                self.__attached_options.remove(option)

    def attach_option(self, name):
        if name in self.options:
            option = self.options[name]
            if option not in self.__attached_options:
                asyncme.mainloop_only(self.__add__widget)(option.view)
                if isinstance(option, Group):
                    for value in option.values:
                        self.__attached_options.append(value)
                self.__attached_options.append(option)

    def get_options(self):
        return self.options_values

    def reorder_option(self, option_name, position: int):
        option = self.options.get(option_name)
        if option and option in self.__attached_options:
            self.box.reorder_child(option.view, position)

    def make_scrollable(self, max_height: int, option_name: str):
        scroll = Gtk.ScrolledWindow()
        self.remove_option(option_name)
        option = self.options[option_name]
        scroll.set_max_content_height(max_height)
        scroll.add_with_viewport(option)
        self.options[option_name] = scroll
        self.attach_option(option_name)


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
        color_hex = '#{:02x}{:02x}{:02x}'.format(*color_rgba)
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

    def set_active(self, value: str):
        if value in self.values:
            self.combo.set_active(self.values.index(value))
        else:
            raise ValueError("value not in drop down values")

    def changed(self, combo):
        selected_text = combo.get_active_text()
        self.value = selected_text
        self.receiver.on_change(self)


class CheckBoxOption(Option):
    def __init__(self, name, values, change_reciever) -> None:
        super().__init__(name, values, "options_checkbox_flow", change_reciever)
        self.value = set()
        self.checkboxes = []
        for value in values:
            checkbox = Gtk.CheckButton.new_with_label(value)
            checkbox.connect("toggled", self.toggled)
            self.checkboxes.append(checkbox)
            self.view.add(checkbox)

    def toggle_all(self, active: bool):
        for c in self.checkboxes:
            c.set_active(active)

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
        self.notify_on_change = False

    def search_changed(self, search_entry):
        if self.notify_on_change:
            query = search_entry.get_text()
            self.value = query
            self.receiver.on_change(self)

    def search_submitted(self, search_entry):
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
        self.group_list.show_all()
        for option in options:
            self.add_option(option)

    def add_option(self, option):
        self.group_list.pack_start(option.view, False, False, 0)
        option.view.set_margin_bottom(30)
        option.view.show_all()


class SelectOption(Option):
    def __init__(self, name, options, change_receiver, **kwargs):
        super().__init__(name, options, "options_select_list_box", change_receiver)
        self.list = self.widget("options_select_list")
        self.list_title = self.widget("options_select_list_title")
        self.list_more = self.widget("options_select_list_more")
        self.list.connect("row-selected", self.option_selected)
        self.options = options
        if "title" in kwargs:
            self.list_title.set_text(kwargs["title"])
        else:
            self.list_title.hide()

        self.rows = []
        for option in self.options:
            self.add_option(option)

        if not self.options:
            self.list_title.hide()
            self.list_more.hide()
        elif len(self.options) > 5:
            self.show_max_rows(5)
        else:
            self.list_more.hide()

    def add_option(self, option):
        row = SelectOptionRow(option)
        self.list.add(row)
        self.rows.append(row)

    def on_show_more(self, toggle_btn):
        if toggle_btn.get_active():
            self.show_all_rows()
            self.list_more.set_label("Show less")
        else:
            self.show_max_rows(5)
            self.list_more.set_label("Show more")

    def show_max_rows(self, no_of_rows: int):
        for index, row in enumerate(self.rows):
            if index >= no_of_rows:
                row.hide()

    def show_all_rows(self):
        for row in self.rows:
            row.show()

    def select_option(self, option):
        if isinstance(self.options, tuple):
            options = list(map(lambda x: x[1], self.options))
            index = options.index(option)
            self.list.select_row(self.list.get_row_at_index(index))
        elif option in self.options:
            index = self.options.index(option)
            self.list.select_row(self.list.get_row_at_index(index))

    def unselect_all(self):
        self.list.unselect_all()

    def option_selected(self, listbox, row):
        if not row:
            self.value = None
        else:
            self.value = row.data
        self.receiver.on_change(self)


class SelectOptionRow(Gtk.ListBoxRow):

    def __init__(self, view):
        super().__init__()
        self.data = view
        self.set_margin_top(5)
        self.set_margin_bottom(5)
        self.set_size_request(50, 40)
        if isinstance(view, str):
            label = Gtk.Label(label=view)
            self.add(label)
        elif isinstance(view, tuple):
            self.add(view[0])
            self.data = view[1]
        else:
            self.add(view)
        self.show_all()


class OptionType(enum.Enum):
    DROPDOWN, TEXTFIELD, COLOR, CHECKBOX, SEARCH, TEXTVIEW, LINK, BUTTON, GROUP, SELECT = range(10)
