"""
wallpaper_manager.py
---------------------
Everything that isn't UI: finding wallpaper files, generating and
caching thumbnails, detecting the currently-set wallpaper, and
invoking feh to apply a new one.
"""
import hashlib
import subprocess
from pathlib import Path

from PIL import Image

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


class Wallpaper:
    """Simple data holder: a source image + its cached thumbnail."""

    def __init__(self, path: Path, thumb_path: Path):
        self.path = path
        self.thumb_path = thumb_path
        self.name = path.name  # full filename, including extension


class WallpaperManager:
    def __init__(self, wallpaper_dir: Path, thumb_dir: Path, thumb_size: int):
        self.wallpaper_dir = wallpaper_dir
        self.thumb_dir = thumb_dir
        self.thumb_size = thumb_size
        self.thumb_dir.mkdir(parents=True, exist_ok=True)

    def _thumb_path_for(self, image_path: Path) -> Path:
        """
        Deterministic cache filename based on path + mtime + thumb size.
        Including mtime means replacing a file regenerates its thumbnail
        automatically instead of showing a stale cached image.
        """
        key = f"{image_path}-{image_path.stat().st_mtime}-{self.thumb_size}"
        digest = hashlib.sha1(key.encode()).hexdigest()
        return self.thumb_dir / f"{digest}.png"

    def list_wallpapers(self):
        """
        Scan the wallpaper directory ONCE and return Wallpaper objects.
        Deliberately does NOT generate thumbnails here - that's slow on
        first run with many images and would block the UI at startup.
        The caller (UI) shows rows immediately and generates any missing
        thumbnails in the background via ensure_thumbnail().
        """
        if not self.wallpaper_dir.exists():
            return []

        wallpapers = []
        for entry in sorted(self.wallpaper_dir.iterdir()):
            if not entry.is_file() or entry.suffix.lower() not in SUPPORTED_EXTS:
                continue

            try:
                thumb_path = self._thumb_path_for(entry)
            except FileNotFoundError:
                continue  # file vanished mid-scan

            wallpapers.append(Wallpaper(entry, thumb_path))

        return wallpapers

    def ensure_thumbnail(self, wallpaper: "Wallpaper"):
        """
        Generate the thumbnail for a single wallpaper if it isn't already
        cached. Safe to call from a background thread - it's pure file
        I/O / Pillow work, no Qt objects involved.
        """
        if not wallpaper.thumb_path.exists():
            self._generate_thumbnail(wallpaper.path, wallpaper.thumb_path)

    def _generate_thumbnail(self, src: Path, dst: Path):
        """Create a downscaled PNG thumbnail for fast grid loading."""
        try:
            with Image.open(src) as img:
                img = img.convert("RGB")
                img.thumbnail((self.thumb_size, self.thumb_size), Image.LANCZOS)
                img.save(dst, "PNG")
        except Exception as e:
            print(f"[i3x11wpl] failed to generate thumbnail for {src}: {e}")

    @staticmethod
    def get_current_wallpaper():
        """
        Best-effort detection of the current wallpaper by reading
        ~/.fehbg, which feh rewrites every time it sets a background.
        """
        fehbg = Path.home() / ".fehbg"
        if not fehbg.exists():
            return None
        try:
            content = fehbg.read_text()
            for line in content.splitlines():
                if "feh" in line and "'" in line:
                    # Lines look like: feh --bg-fill '/path/to/image.jpg'
                    parts = line.split("'")
                    if len(parts) >= 2:
                        return Path(parts[-2])
        except Exception:
            pass
        return None

    def set_wallpaper(self, feh_command: str, image_path: Path):
        """
        Apply the wallpaper by shelling out to feh (non-blocking).
        start_new_session detaches feh into its own process group so it
        never lingers as a child tied to us - avoids orphan processes.
        """
        cmd = feh_command.split() + [str(image_path)]
        subprocess.Popen(
            cmd,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
