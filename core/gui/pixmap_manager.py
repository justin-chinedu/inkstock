import math
import os

from gi.repository import GLib, GdkPixbuf

BILINEAR = GdkPixbuf.InterpType.BILINEAR
HYPER = GdkPixbuf.InterpType.HYPER

SIZE_ASPECT_GROW = 0
SIZE_ASPECT_CROP = 1


class PixmapManager:
    pixmap_dir = None
    # Default styling for multiview thumbnails, All styles must follow this template
    # could be overridden when providing a pixmap manager by sources
    style = """.{id}{{
            background-size: cover;
            background-origin: content-box;
            border-radius: 5%;
            background-image: url("{url}");
            background-repeat: no-repeat; 
            }}
            
            window flowbox > flowboxchild {{
            border-radius: 5%;
            }}
        """

    def __init__(self, cache_dir, scale=0.7, pref_width=200, pref_height=200,
                 padding=0, aspect_ratio=SIZE_ASPECT_CROP, grid_item_width=400, grid_item_height=300):
        self.enable_aspect = True
        self.enable_padding = True
        self.grid_item_width = grid_item_width
        self.grid_item_height = grid_item_height
        self.aspect_ratio = aspect_ratio
        self.padding = padding
        self.pref_height = pref_height
        self.pref_width = pref_width

        self.preview_item_width = 150
        self.preview_item_height = 100
        self.preview_padding = self.padding
        self.preview_scaling = 0.5
        self.preview_aspect_ratio = SIZE_ASPECT_CROP

        self.scale = scale
        self.single_preview_scale = self.scale
        self.cache_dir = cache_dir
        self.cache = {}

    @staticmethod
    async def _apply_tasks_to_item(remote_file, display_type, callback, *args):
        filepath = remote_file.get_thumbnail()
        for task in remote_file.tasks:
            if task.is_active:
                filepath = await task.do_task(filepath)
        return filepath, display_type, callback, *args

    def _get_pixbuf_for_type(self, args):
        thumbnail, display_type, callback, *args = args

        if not thumbnail:
            return

        # for thumbnails in multi view
        if display_type == "multi":
            pixbuf_path = self.get_pixbuf(thumbnail, self.pref_width, self.pref_height, self.padding, self.scale,
                                          SIZE_ASPECT_CROP)

            callback(pixbuf_path, *args)
        # for thumbnails in single view
        elif display_type == "thumb":
            pixbuf_path = self.get_pixbuf(thumbnail, self.preview_item_width, self.preview_item_height,
                                          self.preview_padding, self.preview_scaling, self.preview_aspect_ratio,
                                          thumbnail=True)

            callback(pixbuf_path, *args)
        # for preview image in single view
        elif display_type == "single":
            # TODO: Find a neater way to reset and restore values
            padding = self.enable_padding
            self.enable_padding = False
            aspect = self.enable_aspect
            self.enable_aspect = False

            pixbuf = self.get_pixbuf(thumbnail, self.pref_width, self.pref_height, self.padding,
                                     self.single_preview_scale, SIZE_ASPECT_GROW, return_pixbuf=True)
            self.enable_padding = padding
            self.enable_aspect = aspect
            del padding
            del aspect
            callback(pixbuf, *args)

        return False

    def get_pixbuf_for_type(self, remote_file, display_type, callback, *args):
        # return pixbuf immediately for source icons, no need to fetch asynchronously
        # since it doesn't take much time
        if display_type == "icon":
            pixbuf = self.get_pixbuf(remote_file, self.pref_width, self.pref_height, self.padding, self.scale,
                                     SIZE_ASPECT_GROW, return_pixbuf=True)
            return pixbuf

        def cb(result, error: Exception):
            if error:
                print(error)
            if result:
                GLib.idle_add(self._get_pixbuf_for_type, result)

        source = remote_file.source
        source.add_task_to_queue(self._apply_tasks_to_item, cb, remote_file, display_type, callback, *args),

    def get_pixbuf(self, name: str, pref_width, pref_height, padding, scale, aspect_ratio, return_pixbuf=False,
                   thumbnail=False):

        pixmap_path = self.get_pixmap_path(name)

        if self.data_is_file(name):
            img = self.load_file_from_path(pixmap_path, scale)

            if self.enable_aspect:
                img = self.set_aspect(img, pref_width, pref_height, aspect_ratio)
            if self.enable_padding:
                img = self.set_padding(img, padding)
            if thumbnail:
                pixmap_path = pixmap_path + ".thumb"
            if not return_pixbuf:
                img.savev(pixmap_path, "png")
            if return_pixbuf:
                return img
            else:
                return pixmap_path

    def set_aspect(self, img: GdkPixbuf.Pixbuf, pref_width, pref_height,
                   aspect_ratio=SIZE_ASPECT_CROP) -> GdkPixbuf.Pixbuf:
        img_w = img.get_width()
        img_h = img.get_height()
        aspect = img_w / img_h

        mod_img = None

        if aspect_ratio == SIZE_ASPECT_CROP:

            w_greater = pref_width > img_w and pref_width > pref_height
            h_greater = pref_height > img_h and pref_height > pref_width
            both_greater = pref_width > img_w and pref_height > img_h

            """If the preferred width is greater than the image width + padding and preferred height
                we scale up using the width while calculating the height based on the aspect ratio, 
                else we scale up using the height calculating
                the width based on the aspect ratio"""
            if w_greater:
                h = pref_width / aspect
                img = img.scale_simple(pref_width, h, BILINEAR)
            elif h_greater:
                w = pref_height / aspect
                img = img.scale_simple(w, pref_height, BILINEAR)
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
                img = img.scale_simple(pref_width, pref_width / aspect, HYPER)
            elif img_h > img_w:
                img = img.scale_simple(pref_height * aspect, pref_height, HYPER)
            else:
                img = img.scale_simple(pref_width, pref_width, HYPER)

            # FIXME: Make filling resized image unto new pixbuf
            filled = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, pref_width,
                                          pref_height)
            x = pref_width / 2 - min(pref_width, img.get_width()) / 2
            y = pref_height / 2 - min(img.get_height(), pref_height) / 2

            img.copy_area(0, 0, img.get_width(), img.get_height(), filled, math.floor(x), math.floor(y))
            mod_img = filled
        # if padding > 0:
        #     padded = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 24, pref_width + padding,
        #                                   pref_height + padding)
        #     x = padded.get_width() / 2 - min(padded.get_width(), mod_img.get_width()) / 2
        #     y = padded.get_height() / 2 - min(padded.get_height(), mod_img.get_height()) / 2
        #
        #     mod_img.copy_area(0, 0, mod_img.get_width(), mod_img.get_height(), padded, math.floor(x), math.floor(y))
        #     del mod_img
        #     return padded.scale_simple(pref_width, pref_height, BILINEAR)
        return mod_img

    def set_padding(self, img, padding):
        width = img.get_width()
        height = img.get_height()

        if padding > 0:
            padded = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, width + padding,
                                          height + padding)
            x = padded.get_width() / 2 - min(padded.get_width(), width) / 2
            y = padded.get_height() / 2 - min(padded.get_height(), height) / 2

            img.copy_area(0, 0, width, height, padded, math.floor(x), math.floor(y))

            return padded.scale_simple(width, height, HYPER)
        return img

    @staticmethod
    def data_is_file(data):
        """Test the file to see if it's a filename or not"""
        return isinstance(data, str) and "<svg" not in data

    def load_file_from_path(self, path: str, scale):
        img_format, width, height = GdkPixbuf.Pixbuf.get_file_info(path)
        pixbuf: GdkPixbuf.Pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, width * scale, height * scale)
        return pixbuf

    def get_pixmap_path(self, name):
        """Returns the pixmap path based on stored location"""
        for filename in (
                name,
                os.path.join(self.cache_dir, f"{name}.svg"),
                os.path.join(self.cache_dir, f"{name}.png"),
        ):
            if os.path.exists(filename) and os.path.isfile(filename):
                return name
        return os.path.join(self.cache_dir, name)
