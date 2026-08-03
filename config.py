"""
config.py
---------
Loads user configuration from ~/.config/i3x11wpl/config.ini.
Creates a default config file on first run if none exists.
Keeping config separate from UI/logic makes it easy to tweak
appearance/behavior without touching code.
"""
import configparser
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "i3x11wpl"
CONFIG_FILE = CONFIG_DIR / "config.ini"
CACHE_DIR = Path.home() / ".cache" / "i3x11wpl"
THUMB_DIR = CACHE_DIR / "thumbnails"

# Default values written to config.ini the first time the app runs.
DEFAULTS = {
    "general": {
        "wallpaper_dir": str(Path.home() / "Pictures" / "wallpapers"),
        # Command used to set the wallpaper. The image path is appended.
        "feh_command": "feh --bg-fill",
    },
    "window": {
        "width": "600",
        "height": "480",
        "opacity": "0.97",       # 0.0 (fully transparent) - 1.0 (opaque)
        "border_radius": "0",    # square corners, dmenu/rofi style
        "font_family": "Ubuntu Mono",
        "font_size": "11",
    },
    "thumbnail": {
        # Small row icon, not a grid thumbnail - keeps rows compact.
        "size": "48",
    },
    # Alacritty color scheme, used as-is so the picker matches the terminal.
    "colors": {
        "background": "#1e1e2e",
        "foreground": "#cdd6f4",
        "black": "#45475a",
        "blue": "#89b4fa",
        "green": "#a6e3a1",
        "red": "#f38ba8",
        "yellow": "#f9e2af",
        "magenta": "#f5c2e7",
        "cyan": "#94e2d5",
        "white": "#bac2de",
    },
}


def _ensure_config_exists():
    """Write a default config file if the user doesn't have one yet."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        cp = configparser.ConfigParser()
        cp.read_dict(DEFAULTS)
        with open(CONFIG_FILE, "w") as f:
            cp.write(f)


class Config:
    """Typed, convenient access to config.ini values."""

    def __init__(self):
        _ensure_config_exists()

        cp = configparser.ConfigParser()
        cp.read_dict(DEFAULTS)   # start from defaults
        cp.read(CONFIG_FILE)     # let user's file override them

        g = cp["general"]
        w = cp["window"]
        t = cp["thumbnail"]
        c = cp["colors"]

        self.wallpaper_dir = Path(os.path.expanduser(g.get("wallpaper_dir")))
        self.feh_command = g.get("feh_command")

        self.width = w.getint("width")
        self.height = w.getint("height")
        self.opacity = w.getfloat("opacity")
        self.border_radius = w.getint("border_radius")
        self.font_family = w.get("font_family")
        self.font_size = w.getint("font_size")

        self.thumb_size = t.getint("size")

        # Alacritty palette. Selection/focus uses blue; borders/hover use
        # black (the palette's subtle dark tone), matching a terminal feel.
        self.color_bg = c.get("background")
        self.color_fg = c.get("foreground")
        self.color_black = c.get("black")
        self.color_blue = c.get("blue")
        self.color_green = c.get("green")
        self.color_red = c.get("red")
        self.color_yellow = c.get("yellow")
        self.color_magenta = c.get("magenta")
        self.color_cyan = c.get("cyan")
        self.color_white = c.get("white")

        # Convenience aliases used by the stylesheet.
        self.color_accent = self.color_blue
        self.color_selected = self.color_blue
        self.color_search_bg = self.color_black
        self.color_border = self.color_black
