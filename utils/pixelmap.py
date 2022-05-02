import math
import os
from concurrent.futures import Future

import gi

from inkex.gui import asyncme

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, GdkPixbuf, Gdk

BILINEAR = GdkPixbuf.InterpType.BILINEAR
HYPER = GdkPixbuf.InterpType.HYPER

SIZE_ASPECT_GROW = 0
SIZE_ASPECT_CROP = 2


class PixmapManager:
    pixmap_dir = None

    def __init__(self, cache_dir, scale=0.7, pref_width=200, pref_height=200,
                 padding=0, aspect_ratio=SIZE_ASPECT_CROP, grid_item_width=400, grid_item_height=300):
        self.grid_item_width = grid_item_width
        self.grid_item_height = grid_item_height
        self.aspect_ratio = aspect_ratio
        self.padding = padding
        self.pref_height = pref_height
        self.pref_width = pref_width

        self.scale = scale
        self.cache_dir = cache_dir
        self.cache = {}

    def get_pixbuf_from_file(self, file, callback):
        def run(*args):
            thumbnail = file.thumbnail
            pixbuf_path = self.get_pixbuf(thumbnail)
            callback(pixbuf_path, *args)

        asyncme.run_or_wait(run)(file)

    def get_pixbuf(self, name: str):
        key = name[-30:]  # bytes or string
        if key not in self.cache:
            if self.data_is_file(name):
                pixmap_path = self.pixmap_path(name)
                img = self.load_file_from_path(pixmap_path, self.scale)
                aspect = self.set_aspect(img, self.pref_width, self.pref_height, self.padding)
                aspect.savev(pixmap_path, "png")
                self.cache[key] = pixmap_path
                return pixmap_path
        else:
            return self.cache[key]

    def set_aspect(self, img: GdkPixbuf.Pixbuf, pref_width, pref_height, padding=0) -> GdkPixbuf.Pixbuf:
        img_w = img.get_width()
        img_h = img.get_height()
        aspect = img_w / img_h

        mod_img = None

        if self.aspect_ratio == SIZE_ASPECT_CROP:

            w_greater = pref_width > img_w and pref_width > pref_height
            h_greater = pref_height > img_h and pref_height > pref_width
            both_greater = pref_width > img_w and pref_height > img_h

            """If the preferred width is greater than the image width + padding and preferred height
                we scale up using the width while calculating the height based on the aspect ratio, 
                else we scale up using the height calculating
                the width based on the aspect ratio"""
            if w_greater:
                h = pref_width / aspect
                img = img.scale_simple(pref_width - padding, h - padding, BILINEAR)
            elif h_greater:
                w = pref_height / aspect
                img = img.scale_simple(w - padding, pref_height - padding, BILINEAR)
            elif not both_greater:
                """if both are lesser we scale down the image by scaling down the shortest side and calculating
                the longer side based on the aspect ratio"""
                pref_aspect = pref_width / pref_height
                if pref_aspect > aspect:
                    """
                    this means we need to scale down the width of img
                    and calculate height based on aspect ratio to prevent
                    the width from being shorter than the final image width
                    and vice versa for the height, taking padding into consideration
                    """
                    h = pref_width / aspect
                    img = img.scale_simple(pref_width, h, BILINEAR)
                else:  # height of img is greater
                    w = pref_height * aspect
                    img = img.scale_simple(w, pref_height, BILINEAR)

            cropped = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, pref_width,
                                           pref_height)
            # cropped.fill(0xffffffff)
            """we minus the left coord of pref from the img to get the 
            coord of the final image"""

            x = img.get_width() / 2 - min(pref_width, img.get_width()) / 2
            y = img.get_height() / 2 - min(img.get_height(), pref_height) / 2

            cropped = img.new_subpixbuf(math.floor(x), math.floor(y), min(pref_width, img.get_width()),
                                        min(pref_height, img.get_height()))

            mod_img = cropped
        else:
            if img_w > img_h:
                img = img.scale_simple(pref_width, pref_width / aspect, BILINEAR)
            elif img_h > img_w:
                img = img.scale_simple(pref_height * aspect, pref_height, BILINEAR)
            else:
                img = img.scale_simple(pref_width, pref_width, BILINEAR)

            filled = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, pref_width,
                                          pref_height)
            x = pref_width / 2 - min(pref_width, img.get_width()) / 2
            y = pref_height / 2 - min(img.get_height(), pref_height) / 2

            img.copy_area(0, 0, img.get_width(), img.get_height(), filled, math.floor(x), math.floor(y))
            mod_img = filled
        if padding > 0:
            padded = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, pref_width + padding,
                                          pref_height + padding)
            x = padded.get_width() / 2 - min(padded.get_width(), mod_img.get_width()) / 2
            y = padded.get_height() / 2 - min(padded.get_height(), mod_img.get_height()) / 2

            mod_img.copy_area(0, 0, mod_img.get_width(), mod_img.get_height(), padded, math.floor(x), math.floor(y))
            del mod_img
            return padded.scale_simple(pref_width, pref_height, BILINEAR)
        return mod_img

    @staticmethod
    def data_is_file(data):
        """Test the file to see if it's a filename or not"""
        return isinstance(data, str) and "<svg" not in data

    def load_file_from_path(self, path: str, scale):
        img_format, width, height = GdkPixbuf.Pixbuf.get_file_info(path)
        pixbuf: GdkPixbuf.Pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, width * scale, height * scale, True)
        return pixbuf

    def pixmap_path(self, name):
        """Returns the pixmap path based on stored location"""
        for filename in (
                name,
                os.path.join(self.cache_dir, f"{name}.svg"),
                os.path.join(self.cache_dir, f"{name}.png"),
        ):
            if os.path.exists(filename) and os.path.isfile(filename):
                return name
        return os.path.join(self.cache_dir, name)


def load_css(data: str):
    css_prov = Gtk.CssProvider()
    css_prov.load_from_data(data.encode('utf8'))
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        css_prov,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def main():
    pixel = PixmapManager("")
    pic = "/storage/emulated/0/Download/IMG_8417.jpeg"
    pixel.get_pixbuf(pic, 0.5, 400,
                     300, padding=10)
    exit(0)
    builder = Gtk.Builder()
    builder.add_from_file("../ui/results_window.ui")
    flowbox = builder.get_object("results_flow")
    results = builder.get_object("results_window")
    css = '''
        .image_fill{
            background-size: cover;
            border-radius: 10%;
            background-origin: content-box;
            background: url(''' + " " + '''") no-repeat;
        }
    '''
    load_css(css)

    pixbuf = pixel.get_pixbuf("/storage/emulated/0/Download/IMG_8425.jpeg")
    window = Gtk.Window()
    result_item = builder.get_object("result_item")
    image: Gtk.Image = builder.get_object("result_image")
    # image.set_from_pixbuf(pixbuf)
    frame = Gtk.Frame()
    frame.set_size_request(400, 400)
    text = builder.get_object("result_text")
    layout = Gtk.Layout()
    text.set_text("Test")
    flowbox.add(frame)

    window.add(results)
    frame.get_style_context().add_class("image_fill")
    window.show_all()
    window.connect("destroy", Gtk.main_quit)
    Gtk.main()
