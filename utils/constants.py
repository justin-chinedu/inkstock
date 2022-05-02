import os
from appdirs import user_cache_dir

SOURCES = os.path.join(os.path.dirname(__file__), 'sources')
WINDOWS = os.path.join(os.path.dirname(__file__), 'windows')
LICENSES = os.path.join(os.path.dirname(__file__), 'licenses')
CACHE_DIR = user_cache_dir('inkscape-import-web-image', 'Inkscape')
