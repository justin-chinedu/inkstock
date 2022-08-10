import json
import os

import appdirs
from gi.repository import Gtk, Gdk

from core.constants import CACHE_DIR, SOURCES
from core.gui.pixmap_manager import PixmapManager, SIZE_ASPECT_GROW
from core.gui.window import Window
from core.import_manager import ImportManager
from sources.source import RemoteSource, SourceType
from windows.options_window import OptionsWindow, OptionType, OptionsChangeListener


class InkStockWindow(Window):
    name = "inkstocks_window"
    primary = True

    def __init__(self, gapp):
        super().__init__(gapp)
        # settings = Gtk.Settings.get_default()
        # settings.connect("notify::gtk-theme-name", self._on_theme_name_changed)
        self.app_css_dark = """
         @import url("theme/Matcha/gtk/gtk-3.0/gtk-dark-pueril.css");
         @import url("theme/inkstock_dark.css");
        """
        self.app_css_light = """
         @import url("theme/Matcha/gtk/gtk-3.0/gtk-light-pueril.css");
         @import url("theme/inkstock.css");
        """
        # self._on_theme_name_changed(settings, None)

        self.import_files_btn: Gtk.Button = self.widget('import_files_btn')
        self.import_files_btn.set_sensitive(False)
        self.source_title = self.widget('source_title')
        self.source_desc = self.widget('source_desc')
        self.source_icon = self.widget('source_icon')
        self.progress: Gtk.ProgressBar = self.widget('download_progress')
        self.progress.hide()
        self.no_of_selected = self.widget('no_of_selected')
        self.page_stack: Gtk.Stack = self.widget('page_stack')
        self.import_files_btn.connect('clicked', self.import_files)
        self.sources_options: Gtk.Stack = self.widget('sources_options')
        self.setting_popover: Gtk.Popover = self.widget("settings_popover")
        self.setting_btn: Gtk.ToggleButton = self.widget("settings_button")
        self.setting_btn.connect("toggled", self.show_settings)
        self.setting_popover.set_modal(False)

        if not os.path.exists(CACHE_DIR):
            os.mkdir(CACHE_DIR)

        self.sources_pixmanager = PixmapManager(CACHE_DIR, scale=3, pref_width=150,
                                                pref_height=150, padding=40, aspect_ratio=SIZE_ASPECT_GROW, )
        self.import_manager = ImportManager(self)
        self.sources_windows = []
        self.sources_handler = SourcesHandler(self)
        self.settings_handler = SettingsHandler(self)
        self.change_theme(self.settings_handler.settings["theme"])

    def show_settings(self, btn: Gtk.ToggleButton):
        toggled = btn.get_active()
        if toggled:
            self.setting_popover.popup()
        else:
            self.setting_popover.popdown()

    def _on_theme_name_changed(self, settings, _):
        name = settings.get_property("gtk-theme-name").lower()
        self.change_theme(name)

    def change_theme(self, name):
        if "dark" in name:
            self.load_css(self.app_css_dark)
        else:
            self.load_css(self.app_css_light)

    @staticmethod
    def load_css(data: str):
        css_prov = Gtk.CssProvider()
        css_prov.load_from_data(data.encode('utf8'))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_prov,
            Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def import_files(self, *args):
        self.add_and_show_import_window()

    def add_window(self, window_cls, source):
        """if window has not been attached to source, load window"""
        if not source.window and window_cls not in self.sources_windows:
            w = self.gapp.load_window(window_cls.name, source=source, main_window=self)
            self.sources_windows.append(window_cls)

    def show_options_window(self, window):
        if not self.sources_options.get_child_by_name("sources_options"):
            self.sources_options.add_named(window, "sources_options")
        child = self.sources_options.get_child_by_name("sources_options")
        self.sources_options.set_visible_child(child)

    def show_window(self, window, source):
        """Adds window to the page stack"""
        if not self.page_stack.get_child_by_name(source.name):
            self.page_stack.add_named(window.window, source.name)
        child = self.page_stack.get_child_by_name(source.name)
        self.page_stack.set_visible_child(child)

    def add_and_show_import_window(self):
        self.source_title.set_text("InkStock")
        self.source_desc.set_markup("Save files as zip or import into Inkscape")
        self.source_icon.clear()
        icon = self.sources_pixmanager.get_pixbuf_for_type("icons/inkstock_logo.svg", "icon", None)
        self.source_icon.set_from_pixbuf(icon)
        self.sources_options.set_sensitive(False)
        self.import_files_btn.set_sensitive(False)
        if not self.import_manager.window:
            self.gapp.load_window(self.import_manager.window_cls.name, manager=self.import_manager)
        self.show_window(self.import_manager.window, self.import_manager)
        self.import_manager.show_window()

    def show_sources_window(self):
        self.sources_options.set_sensitive(True)
        self.import_files_btn.set_sensitive(True)
        self.sources_handler.source_selected(self.sources_handler.last_selected_source)


class SourcesHandler(OptionsChangeListener):
    def __init__(self, window):
        self.window = window
        self.sources = [source(CACHE_DIR, self.window.import_manager) for source in RemoteSource.sources.values() if
                        source.is_enabled]
        self.displayed_sources = self.sources
        self.disabled = True  # when disabled this doesn't react to change in options window
        self.last_selected_source = None
        self.last_selected_option = None
        self.query = ""

        self.options_window = OptionsWindow(self)
        search = self.options_window.set_option("source_query", None, OptionType.SEARCH, "Search Sources")
        search.notify_on_change = True
        self.source_type_values = sorted(map(lambda x: x.value, SourceType))
        checkboxes = self.options_window.set_option(f"source_types", self.source_type_values, OptionType.CHECKBOX,
                                                    "Source types", attach=False)
        self.options_window.set_option("source_type_group", [checkboxes], OptionType.GROUP, "Filter Source types",
                                       show_separator=True)

        self.show_displayed_sources()
        self.disabled = False

        self.window.show_options_window(self.options_window.window)
        self.window.sources_options.show()

    def show_displayed_sources(self):
        for value in self.source_type_values:
            sources = [source for source in self.displayed_sources if source.source_type.value == value]
            select_option = self.options_window.set_option(f"sources_select_{value}",
                                                           list(map(lambda x: x.name, sources)),
                                                           OptionType.SELECT,
                                                           show_separator=True, title=value.upper(), is_scrollable=True)
            if self.last_selected_source \
                    and self.last_selected_source in self.displayed_sources \
                    and self.last_selected_source.source_type.value == value:
                self.disabled = True
                select_option.select_option(self.last_selected_source.name)
                self.disabled = False

    def on_change(self, options):
        if self.disabled:
            return

        if "source_query" in options and self.query != options["source_query"]:
            self.query = options["source_query"]
            if self.query == "":
                for value in self.source_type_values:
                    self.options_window.remove_option(f"sources_select_{value}")
                self.displayed_sources = self.sources
                self.show_displayed_sources()
            else:
                self.displayed_sources = [source for source in self.sources if self.query.lower() in
                                          source.name.lower()]
                for value in self.source_type_values:
                    self.options_window.remove_option(f"sources_select_{value}")
                self.show_displayed_sources()

        if "source_types" in options:
            source_types = options["source_types"]
            unchecked_types = set(self.source_type_values).difference(source_types)
            checked_types = set(self.source_type_values).intersection(source_types)
            if checked_types:
                for t in unchecked_types:
                    self.options_window.options[f"sources_select_{t}"].view.hide()
                for t in checked_types:
                    self.options_window.options[f"sources_select_{t}"].view.show()
            else:
                for t in unchecked_types:
                    self.options_window.options[f"sources_select_{t}"].view.show()

        for value in self.source_type_values:
            source_name = options[f"sources_select_{value}"]
            if source_name is not None:  # Selected
                source = [source for source in self.displayed_sources if source.name == source_name][0]
                option = self.options_window.options[f"sources_select_{value}"]
                if self.last_selected_source and source.source_type != self.last_selected_source.source_type:
                    self.disabled = True
                    self.last_selected_option.unselect_all()
                    self.disabled = False
                self.source_selected(source)
                self.last_selected_source = source
                self.last_selected_option = option

    def source_selected(self, source):
        # if source == self.last_selected_source:
        #     return
        self.window.source_title.set_text(source.name)
        self.window.source_desc.set_markup(source.desc)

        self.window.source_icon.clear()
        icon = self.window.sources_pixmanager.get_pixbuf_for_type(source.icon, "icon", None)
        self.window.source_icon.set_from_pixbuf(icon)

        self.window.add_window(source.window_cls, source)
        self.window.show_window(source.window, source)


class SettingsHandler(OptionsChangeListener):
    def __init__(self, window: InkStockWindow):
        self.window = window
        self.options_window = OptionsWindow(self)
        self.options_window.window.set_propagate_natural_height(True)
        self.options_window.window.set_propagate_natural_width(True)
        self.options_window.box.set_hexpand(True)
        self.options_window.box.set_halign(Gtk.Align.FILL)
        self.settings = self.retrieve_settings()
        self.options_window.set_option("settings_text", "Appearance", OptionType.TEXTVIEW)
        theme_option = self.options_window.set_option("theme", ["dark", "light"], OptionType.DROPDOWN, "Change Theme")
        theme_option.set_active(self.settings["theme"])
        self.options_window.set_option("about_text",
                                       "\nInkstock ©2022\n\nJustin Chinedu "
                                       "<a href='https://github.com/justin-chinedu/inkstock'>Github</a>",
                                       OptionType.TEXTVIEW)

        self.window.setting_popover.add(self.options_window.window)

    def on_change(self, settings: dict):
        if settings["theme"] != self.settings.get("theme", None):
            self.window.change_theme(settings["theme"])

        self.save_settings(settings)
        
    def save_settings(self, settings):
        self.settings.update(settings)
        pref_dir = appdirs.user_config_dir(appname="InkStock", appauthor="jaycodex")
        if not os.path.exists(pref_dir):
            os.mkdir(pref_dir)
        pref_file = os.path.join(pref_dir, "preferences.json")
        json.dump(self.settings, open(pref_file, mode="w"))

    @staticmethod
    def retrieve_settings() -> dict:
        pref_dir = appdirs.user_config_dir(appname="InkStock", appauthor="jaycodex")
        pref_file = os.path.join(pref_dir, "preferences.json")
        if os.path.exists(pref_file):
            return json.load(open(pref_file, mode="r"))
        else:
            # defaults
            return {"theme": "dark"}
