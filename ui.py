"""
ui.py
-----
The PyQt6 UI layer: a small frameless, floating, dark, square-cornered
window with a search box and a vertical rofi/dmenu-style list of
wallpapers (thumbnail + filename per row). Pure UI concerns only -
file scanning and wallpaper-setting live in wallpaper_manager.py.

Thumbnails that are already cached on disk are loaded instantly.
Thumbnails that still need generating are done in a background thread
pool so the window appears immediately and never blocks on I/O.
"""
from pathlib import Path

from PyQt6.QtCore import Qt, QSize, QObject, QRunnable, QThreadPool, pyqtSignal
from PyQt6.QtGui import QIcon, QKeyEvent, QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QApplication,
)

from config import Config
from wallpaper_manager import WallpaperManager

# How many rows Page Up/Page Down jump by when key events are forwarded
# from the search box (native QListWidget page handling doesn't apply
# since the list never actually has focus).
PAGE_STEP = 6

# Extra item-data roles: PATH_ROLE already used Qt.ItemDataRole.UserRole;
# NAME_ROLE stores the plain filename so the star marker can be added or
# removed without parsing/stripping the displayed text.
PATH_ROLE = Qt.ItemDataRole.UserRole
NAME_ROLE = Qt.ItemDataRole.UserRole + 1


class ThumbnailSignals(QObject):
    """QRunnable can't emit signals itself, so it borrows this QObject."""
    ready = pyqtSignal(str, str)  # wallpaper path, thumbnail path


class ThumbnailWorker(QRunnable):
    """Generates one missing thumbnail off the GUI thread."""

    def __init__(self, manager: WallpaperManager, wallpaper, signals: ThumbnailSignals):
        super().__init__()
        self.manager = manager
        self.wallpaper = wallpaper
        self.signals = signals

    def run(self):
        self.manager.ensure_thumbnail(self.wallpaper)
        self.signals.ready.emit(str(self.wallpaper.path), str(self.wallpaper.thumb_path))


class WallpaperPicker(QWidget):
    def __init__(self, config: Config, manager: WallpaperManager):
        super().__init__()
        self.config = config
        self.manager = manager
        self.current_wallpaper = WallpaperManager.get_current_wallpaper()
        self.all_wallpapers = []  # full, unfiltered list - scanned once at startup

        self.thumbnail_signals = ThumbnailSignals()
        self.thumbnail_signals.ready.connect(self._on_thumbnail_ready)
        self.thread_pool = QThreadPool.globalInstance()

        self._setup_window()
        self._build_ui()
        self.load_wallpapers()

    # ------------------------------------------------------------------
    # Window setup: frameless, translucent, floating, centered - like Rofi
    # ------------------------------------------------------------------
    def _setup_window(self):
        # Tool = no taskbar entry; FramelessWindowHint = no titlebar/borders;
        # StaysOnTop = floats above normal windows, like a rofi/dmenu popup.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(self.config.opacity)
        self.setWindowTitle("i3x11wpl")

        self.resize(self.config.width, self.config.height)
        self._center_on_screen()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        x = screen.x() + (screen.width() - self.width()) // 2
        y = screen.y() + (screen.height() - self.height()) // 2
        self.move(x, y)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        c = self.config

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame(self)
        self.card.setObjectName("card")
        outer.addWidget(self.card)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(8)

        # --- search box (focused immediately, no click needed) --------
        self.search_box = QLineEdit(self.card)
        self.search_box.setObjectName("search")
        self.search_box.setPlaceholderText("Search wallpapers...")
        self.search_box.textChanged.connect(self._on_search_changed)
        self.search_box.installEventFilter(self)  # forward nav keys to the list
        card_layout.addWidget(self.search_box)

        # --- vertical wallpaper list (rofi-style, one row per item) ---
        self.list_widget = QListWidget(self.card)
        self.list_widget.setObjectName("list")
        self.list_widget.setViewMode(QListWidget.ViewMode.ListMode)
        self.list_widget.setFlow(QListWidget.Flow.TopToBottom)
        self.list_widget.setWrapping(False)
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.setSpacing(1)
        self.list_widget.setIconSize(QSize(c.thumb_size, c.thumb_size))
        # Scrollbar stays hidden; wheel/keys still scroll fine without it.
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.itemClicked.connect(self._select_current_item)
        self.list_widget.itemActivated.connect(self._select_current_item)
        card_layout.addWidget(self.list_widget)

        self.setStyleSheet(self._stylesheet())

        font = QFont(c.font_family, c.font_size)
        self.setFont(font)
        self.search_box.setFont(font)
        self.list_widget.setFont(font)

        self.search_box.setFocus()

    def _stylesheet(self) -> str:
        c = self.config
        radius = c.border_radius  # 0 by default - flat, square, dmenu-like
        return f"""
            #card {{
                background-color: {c.color_bg};
                border: 1px solid {c.color_border};
                border-radius: {radius}px;
            }}
            #search {{
                background-color: {c.color_search_bg};
                color: {c.color_fg};
                border: 1px solid {c.color_border};
                border-radius: {radius}px;
                padding: 6px 8px;
            }}
            #list {{
                background-color: transparent;
                border: none;
                color: {c.color_fg};
                outline: none;
            }}
            #list::item {{
                color: {c.color_fg};
                padding: 4px 6px;
                border: none;
                border-radius: 0px;
            }}
            #list::item:selected {{
                background-color: {c.color_blue};
                color: {c.color_bg};
                border-radius: 0px;
            }}
            #list::item:hover:!selected {{
                background-color: rgba(255, 255, 255, 12);
                border-radius: 0px;
            }}
        """

    # ------------------------------------------------------------------
    # Data loading / filtering
    # ------------------------------------------------------------------
    def load_wallpapers(self):
        """Scan the wallpaper dir once, show rows instantly, then fill in
        any missing thumbnails asynchronously so startup stays fast."""
        self.all_wallpapers = self.manager.list_wallpapers()
        self._populate_list(self.all_wallpapers)

    def _populate_list(self, wallpapers):
        self.list_widget.clear()
        placeholder = QIcon()  # blank until the real thumbnail is ready

        for wp in wallpapers:
            has_cached_thumb = wp.thumb_path.exists()
            icon = QIcon(str(wp.thumb_path)) if has_cached_thumb else placeholder

            item = QListWidgetItem(icon, "")
            item.setData(PATH_ROLE, str(wp.path))
            item.setData(NAME_ROLE, wp.name)
            self._refresh_item_label(item)
            self.list_widget.addItem(item)

            # Only queue background work for thumbnails that don't exist
            # yet - already-cached ones loaded instantly above, so repeat
            # launches stay fast and never regenerate anything.
            if not has_cached_thumb:
                worker = ThumbnailWorker(self.manager, wp, self.thumbnail_signals)
                self.thread_pool.start(worker)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _on_thumbnail_ready(self, wallpaper_path: str, thumb_path: str):
        """Background worker finished generating a thumbnail - drop the
        icon into the matching row now that it exists."""
        icon = QIcon(thumb_path)
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if item.data(PATH_ROLE) == wallpaper_path:
                item.setIcon(icon)
                break

    def _refresh_item_label(self, item: QListWidgetItem):
        """Rebuild one row's display text: full filename, plus a star if
        it's the currently-applied wallpaper."""
        name = item.data(NAME_ROLE)
        path = Path(item.data(PATH_ROLE))
        if self.current_wallpaper and path == self.current_wallpaper:
            item.setText(f"\u2605 {name}")
        else:
            item.setText(name)

    def _refresh_all_labels(self):
        """Re-mark the active wallpaper across all visible rows - used
        after applying a new wallpaper so the star moves without
        rebuilding (and losing selection/focus in) the whole list."""
        for row in range(self.list_widget.count()):
            self._refresh_item_label(self.list_widget.item(row))

    def _on_search_changed(self, text: str):
        text = text.lower().strip()
        if not text:
            filtered = self.all_wallpapers
        else:
            filtered = [wp for wp in self.all_wallpapers if text in wp.name.lower()]
        self._populate_list(filtered)

    # ------------------------------------------------------------------
    # Selection handling
    # ------------------------------------------------------------------
    def _select_current_item(self, item: QListWidgetItem = None):
        """Apply the chosen wallpaper but keep the picker open - Enter
        (or a click) can be pressed repeatedly to preview different
        wallpapers without relaunching the app."""
        item = item or self.list_widget.currentItem()
        if item is None:
            return
        path = Path(item.data(PATH_ROLE))
        self.manager.set_wallpaper(self.config.feh_command, path)

        self.current_wallpaper = path
        self._refresh_all_labels()

        # Keep this row selected/highlighted and keyboard focus in the
        # search box so browsing can continue immediately.
        self.list_widget.setCurrentItem(item)
        self.search_box.setFocus()

    def _quit(self):
        """Close and terminate the process cleanly - no orphaned Python
        process left behind in the terminal."""
        # Drop any thumbnail jobs that haven't started yet; running ones
        # are short file writes and finish on their own almost instantly.
        self.thread_pool.clear()
        self.close()
        QApplication.instance().quit()

    # ------------------------------------------------------------------
    # Keyboard handling. Focus stays in the search box the whole time
    # (Rofi-style: always ready to type) - Up/Down/Enter/Escape/Home/End/
    # PageUp/PageDown are intercepted here and forwarded to the list.
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):
        if obj is self.search_box and event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Down:
                self._move_selection(1)
                return True
            if key == Qt.Key.Key_Up:
                self._move_selection(-1)
                return True
            if key == Qt.Key.Key_PageDown:
                self._move_selection(PAGE_STEP)
                return True
            if key == Qt.Key.Key_PageUp:
                self._move_selection(-PAGE_STEP)
                return True
            if key == Qt.Key.Key_Home:
                self._set_row(0)
                return True
            if key == Qt.Key.Key_End:
                self._set_row(self.list_widget.count() - 1)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._select_current_item()
                return True
            if key == Qt.Key.Key_Escape:
                self._quit()
                return True
        return super().eventFilter(obj, event)

    def _move_selection(self, delta: int):
        count = self.list_widget.count()
        if count == 0:
            return
        row = self.list_widget.currentRow()
        self._set_row(max(0, min(count - 1, row + delta)))

    def _set_row(self, row: int):
        if 0 <= row < self.list_widget.count():
            self.list_widget.setCurrentRow(row)
            self.list_widget.scrollToItem(self.list_widget.currentItem())

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self._quit()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        # Fallback in case the window gets closed some other way (e.g.
        # window manager action) - still make sure the app quits.
        self.thread_pool.clear()
        QApplication.instance().quit()
        super().closeEvent(event)
