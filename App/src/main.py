from __future__ import annotations

import colorsys
import ctypes
import json
import os
import sys
import tkinter as tk
from tkinter import font as tkfont
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageTk


APP_TITLE = "Notte dei Ricercatori"
THEMES = {
    "Animali": {
        "background": "assets/Animali.png",
        "button": "#8FCBE8",
        "hover": "#A7D8EE",
        "pressed": "#78B8D8",
        "border": "#76B9D6",
        "inner_border": "#C7ECF7",
        "text": "#FFFFFF",
    },
    "Natura": {
        "background": "assets/Natura.png",
        "button": "#A8D5A2",
        "hover": "#BCE2B7",
        "pressed": "#91C58B",
        "border": "#92C58D",
        "inner_border": "#D9F0D5",
        "text": "#FFFFFF",
    },
    "Feste": {
        "background": "assets/Feste.png",
        "button": "#D8A7B1",
        "hover": "#E6BEC6",
        "pressed": "#C8919D",
        "border": "#C58F9A",
        "inner_border": "#F1D7DC",
        "text": "#FFFFFF",
    },
    "Fantasy": {
        "background": "assets/Fantasy.png",
        "button": "#F2D98B",
        "hover": "#F7E6A9",
        "pressed": "#E5CB76",
        "border": "#E6C96F",
        "inner_border": "#FFF3C6",
        "text": "#FFFFFF",
    },
}


DIFFICULTY_FIELD_COUNTS = {
    "Facile": 4,
    "Medio": 8,
    "Difficile": None,
}

# Spessore del contorno chiaro nei messaggi di vittoria e sconfitta.
# Contorno raddoppiato rispetto alla versione precedente: da 5 a 10 pixel.
RESULT_OUTLINE_RADIUS = 10
RESULT_OUTLINE_OFFSETS = tuple(
    (dx, dy)
    for dx in range(-RESULT_OUTLINE_RADIUS, RESULT_OUTLINE_RADIUS + 1)
    for dy in range(-RESULT_OUTLINE_RADIUS, RESULT_OUTLINE_RADIUS + 1)
    if 0 < dx * dx + dy * dy <= RESULT_OUTLINE_RADIUS ** 2
)


def evaluate_game_answers(
    saved_words: list[str],
    answers: list[str],
    difficulty: str,
) -> tuple[bool, int, int]:
    """Return (won, correctly matched fields, fields required to win).

    Matching ignores order and case. A saved occurrence can only validate
    one entered occurrence, even if the player writes it more than once.
    """
    expected = Counter(
        word.strip().casefold()
        for word in saved_words
        if word.strip()
    )
    entered_values = [
        answer.strip().casefold()
        for answer in answers
        if answer.strip()
    ]
    entered = Counter(entered_values)

    configured_count = DIFFICULTY_FIELD_COUNTS[difficulty]
    required_count = (
        len(saved_words) if configured_count is None else configured_count
    )
    correct_count = sum(
        min(amount, expected.get(word, 0))
        for word, amount in entered.items()
    )
    won = (
        len(entered_values) == required_count
        and correct_count == required_count
    )
    return won, correct_count, required_count


def resource_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        base_path = Path(
            getattr(
                sys,
                "_MEIPASS",
                Path(sys.executable).parent,
            )
        )
    else:
        base_path = Path(__file__).resolve().parent.parent

    return base_path / relative_path


def app_data_folder() -> Path:
    root = Path(os.getenv("LOCALAPPDATA", Path.home()))
    folder = root / "SharperNightApp"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def app_config_path() -> Path:
    return app_data_folder() / "config.json"


class SharperNightApp(tk.Tk):
    def __init__(self) -> None:
        if sys.platform.startswith("win"):
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "NotteDeiRicercatori.SharperNightApp"
                )
            except OSError:
                pass

        super().__init__()

        self.title(APP_TITLE)
        self._set_window_icon()
        self.geometry("1200x720")
        self.minsize(900, 600)

        if sys.platform.startswith("win"):
            self.state("zoomed")

        self.background_photo = None
        self.resize_job = None
        self.current_screen = "home"

        self.button_images: dict[str, dict[str, ImageTk.PhotoImage]] = {}
        self.button_counter = 0
        self.screen_widgets: list[tk.Widget] = []
        self.scroll_background_photos: list[ImageTk.PhotoImage] = []
        self.background_rendered: Image.Image | None = None
        self.words_canvas: tk.Canvas | None = None
        self.game_canvas: tk.Canvas | None = None
        self.words_scroll_height = 0
        self.game_scroll_height = 0

        self.current_theme = "Animali"
        self.current_difficulty = "Difficile"
        self.words: list[str] = []
        self.pending_values: list[str] = []
        self.pending_entries: list[tk.Entry] = []

        self._load_config()
        self.background_source = self._load_theme_background()

        self.canvas = tk.Canvas(
            self,
            highlightthickness=0,
            borderwidth=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.background_id = self.canvas.create_image(
            0,
            0,
            anchor="nw",
            tags=("background",),
        )

        self.canvas.bind(
            "<Configure>",
            self._schedule_resize,
        )

        self._show_home_screen()

    def _set_window_icon(self) -> None:
        icon_file = resource_path("assets/icona.ico")
        if not icon_file.is_file():
            return

        if sys.platform.startswith("win"):
            try:
                self.iconbitmap(default=str(icon_file))
                return
            except tk.TclError:
                pass

        # Fallback for systems where iconbitmap cannot load .ico files.
        try:
            with Image.open(icon_file) as icon_image:
                self._window_icon_photo = ImageTk.PhotoImage(
                    icon_image.convert("RGBA")
                )
            self.iconphoto(True, self._window_icon_photo)
        except (OSError, tk.TclError):
            pass

    def _theme(self) -> dict[str, str]:
        return THEMES[self.current_theme]

    def _load_background(self, relative_path: str) -> Image.Image:
        selected_path = resource_path(relative_path)

        if not selected_path.is_file():
            selected_path = resource_path("assets/Animali.png")

        return Image.open(selected_path).convert("RGB")

    def _load_theme_background(self) -> Image.Image:
        return self._load_background(
            self._theme()["background"]
        )

    def _set_background(self, relative_path: str) -> None:
        self.background_source = self._load_background(
            relative_path
        )

        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)

        self._resize_interface(
            width,
            height,
        )

    def _refresh_background(self) -> None:
        self._set_background(
            self._theme()["background"]
        )

    def _pin_scroll_background(self, canvas: tk.Canvas) -> None:
        """Keep the wallpaper at one fixed screen position while rows scroll."""
        items = canvas.find_withtag("scroll_background")
        if items:
            canvas.coords(items[0], 0, canvas.canvasy(0))
            canvas.tag_lower(items[0])

    def _paint_scroll_background(
        self,
        canvas: tk.Canvas,
        content_height: int,
    ) -> None:
        """Continue the main wallpaper into the scrolling viewport seamlessly.

        Tkinter canvases cannot actually be transparent. Instead, show the
        corresponding crop of the *same* full-window wallpaper, and keep
        that crop fixed when scrolling the text fields over it.
        """
        if not canvas.winfo_exists():
            return

        viewport_width = canvas.winfo_width()
        viewport_height = canvas.winfo_height()
        root_width = self.canvas.winfo_width()
        root_height = self.canvas.winfo_height()
        if min(viewport_width, viewport_height, root_width, root_height) <= 1:
            return

        wallpaper = self.background_rendered
        if wallpaper is None or wallpaper.size != (root_width, root_height):
            wallpaper = ImageOps.fit(
                self.background_source,
                (root_width, root_height),
                method=Image.Resampling.LANCZOS,
            )

        # Using root coordinates avoids re-scaling and duplicating decorations.
        left = canvas.winfo_rootx() - self.canvas.winfo_rootx()
        top = canvas.winfo_rooty() - self.canvas.winfo_rooty()
        crop = wallpaper.crop(
            (left, top, left + viewport_width, top + viewport_height)
        )
        photo = ImageTk.PhotoImage(crop)

        canvas.delete("scroll_background")
        self.scroll_background_photos[:] = [photo]
        canvas.create_image(
            0,
            canvas.canvasy(0),
            anchor="nw",
            image=photo,
            tags=("scroll_background",),
        )
        canvas.tag_lower("scroll_background")

    def _connect_scrollbar(
        self,
        canvas: tk.Canvas,
        scrollbar: tk.Scrollbar,
    ) -> None:
        """Move content and scrollbar, not the displayed wallpaper."""
        def on_scroll(first: str, last: str) -> None:
            scrollbar.set(first, last)
            self._pin_scroll_background(canvas)

        canvas.configure(yscrollcommand=on_scroll)

    def _load_config(self) -> None:
        path = app_config_path()

        if not path.is_file():
            return

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        theme = data.get("theme")
        if theme in THEMES:
            self.current_theme = theme

        difficulty = data.get("difficulty")
        if difficulty in DIFFICULTY_FIELD_COUNTS:
            self.current_difficulty = difficulty

        words = data.get("words")
        if isinstance(words, list):
            self.words = [
                str(word).strip()
                for word in words
                if str(word).strip()
            ]

    def _save_config(self) -> None:
        data = {
            "theme": self.current_theme,
            "difficulty": self.current_difficulty,
            "words": self.words,
        }

        path = app_config_path()
        temporary = path.with_suffix(".tmp")

        temporary.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temporary.replace(path)

    def _clear_screen(self) -> None:
        self.canvas.delete("interface")
        self.button_images.clear()
        self.scroll_background_photos.clear()

        for widget in self.screen_widgets:
            try:
                widget.destroy()
            except tk.TclError:
                pass

        self.screen_widgets.clear()
        self.pending_entries.clear()
        self.words_canvas = None
        self.game_canvas = None

    def _create_balloon_image(
        self,
        width: int,
        height: int,
        color: str,
        pressed: bool = False,
    ) -> ImageTk.PhotoImage:
        theme = self._theme()
        padding = 18

        image = Image.new(
            "RGBA",
            (
                width + padding * 2,
                height + padding * 2,
            ),
            (0, 0, 0, 0),
        )

        shadow = Image.new(
            "RGBA",
            image.size,
            (0, 0, 0, 0),
        )

        shadow_draw = ImageDraw.Draw(shadow)
        shadow_offset = 8 if not pressed else 4

        shadow_draw.rounded_rectangle(
            (
                padding,
                padding + shadow_offset,
                padding + width,
                padding + height + shadow_offset,
            ),
            radius=height // 2,
            fill=(45, 70, 90, 75),
        )

        shadow = shadow.filter(
            ImageFilter.GaussianBlur(7)
        )
        image.alpha_composite(shadow)

        draw = ImageDraw.Draw(image)
        top = padding + (4 if pressed else 0)

        draw.rounded_rectangle(
            (
                padding,
                top,
                padding + width,
                top + height,
            ),
            radius=height // 2,
            fill=color,
            outline=theme["border"],
            width=4,
        )

        draw.rounded_rectangle(
            (
                padding + 7,
                top + 7,
                padding + width - 7,
                top + height - 7,
            ),
            radius=max(1, height // 2 - 7),
            outline=theme["inner_border"],
            width=3,
        )

        if not pressed:
            highlight = Image.new(
                "RGBA",
                image.size,
                (0, 0, 0, 0),
            )

            highlight_draw = ImageDraw.Draw(highlight)

            highlight_draw.rounded_rectangle(
                (
                    padding + 20,
                    top + 9,
                    padding + width - 20,
                    top + max(20, height // 2),
                ),
                radius=max(1, height // 3),
                fill=(255, 255, 255, 42),
            )

            highlight = highlight.filter(
                ImageFilter.GaussianBlur(5)
            )
            image.alpha_composite(highlight)

        return ImageTk.PhotoImage(image)

    def _create_canvas_button(
        self,
        canvas: tk.Canvas,
        text: str,
        x: int,
        y: int,
        width: int,
        height: int,
        font_size: int,
        command,
        anchor: str = "center",
        tags: tuple[str, ...] = (),
    ) -> tuple[int, int]:
        self.button_counter += 1
        tag = f"balloon_button_{self.button_counter}"

        theme = self._theme()

        normal_photo = self._create_balloon_image(
            width,
            height,
            theme["button"],
        )
        hover_photo = self._create_balloon_image(
            width,
            height,
            theme["hover"],
        )
        pressed_photo = self._create_balloon_image(
            width,
            height,
            theme["pressed"],
            pressed=True,
        )

        self.button_images[tag] = {
            "normal": normal_photo,
            "hover": hover_photo,
            "pressed": pressed_photo,
        }

        all_tags = (tag,) + tags

        image_id = canvas.create_image(
            x,
            y,
            image=normal_photo,
            anchor=anchor,
            tags=all_tags,
        )

        if anchor == "nw":
            text_x = x + width // 2 + 18
            text_y = y + height // 2 + 18
        else:
            text_x = x
            text_y = y

        text_id = canvas.create_text(
            text_x,
            text_y,
            text=text,
            fill=theme["text"],
            font=(
                "Segoe UI",
                font_size,
                "bold",
            ),
            tags=all_tags,
        )

        pressed_state = {"down": False}

        def enter(_event) -> None:
            canvas.configure(cursor="hand2")
            if not pressed_state["down"]:
                canvas.itemconfigure(
                    image_id,
                    image=hover_photo,
                )

        def leave(_event) -> None:
            canvas.configure(cursor="arrow")
            if pressed_state["down"]:
                canvas.move(text_id, 0, -4)
                pressed_state["down"] = False

            canvas.itemconfigure(
                image_id,
                image=normal_photo,
            )

        def press(_event) -> None:
            if pressed_state["down"]:
                return

            pressed_state["down"] = True

            canvas.itemconfigure(
                image_id,
                image=pressed_photo,
            )
            canvas.move(
                text_id,
                0,
                4,
            )

        def release(_event) -> None:
            if not pressed_state["down"]:
                return

            pressed_state["down"] = False

            canvas.itemconfigure(
                image_id,
                image=hover_photo,
            )
            canvas.move(
                text_id,
                0,
                -4,
            )

            command()

        canvas.tag_bind(tag, "<Enter>", enter)
        canvas.tag_bind(tag, "<Leave>", leave)
        canvas.tag_bind(tag, "<ButtonPress-1>", press)
        canvas.tag_bind(tag, "<ButtonRelease-1>", release)

        return image_id, text_id

    def _create_back_button(self, command) -> None:
        self._create_canvas_button(
            canvas=self.canvas,
            text="←  Indietro",
            x=25,
            y=25,
            width=210,
            height=70,
            font_size=17,
            command=command,
            anchor="nw",
            tags=("interface",),
        )

    def _show_home_screen(self) -> None:
        self.current_screen = "home"
        self._clear_screen()
        self._refresh_background()

        width = max(
            self.canvas.winfo_width(),
            900,
        )
        height = max(
            self.canvas.winfo_height(),
            600,
        )

        self._create_canvas_button(
            canvas=self.canvas,
            text="⚙  Impostazioni",
            x=25,
            y=25,
            width=255,
            height=70,
            font_size=17,
            command=self._show_settings_screen,
            anchor="nw",
            tags=("interface", "settings_button"),
        )

        self._create_canvas_button(
            canvas=self.canvas,
            text="GIOCA",
            x=width // 2,
            y=height // 2,
            width=360,
            height=125,
            font_size=30,
            command=self._start_game,
            tags=("interface", "play_button"),
        )

    def _show_settings_screen(self) -> None:
        self.current_screen = "settings"
        self._clear_screen()
        self._refresh_background()

        self._create_back_button(
            self._show_home_screen
        )

        width = max(
            self.canvas.winfo_width(),
            900,
        )
        height = max(
            self.canvas.winfo_height(),
            600,
        )

        center_x = width // 2
        center_y = height // 2

        self._create_canvas_button(
            canvas=self.canvas,
            text="Tema",
            x=center_x,
            y=center_y - 135,
            width=300,
            height=88,
            font_size=23,
            command=self._show_theme_screen,
            tags=("interface",),
        )

        self._create_canvas_button(
            canvas=self.canvas,
            text="Difficoltà",
            x=center_x,
            y=center_y,
            width=300,
            height=88,
            font_size=23,
            command=self._show_difficulty_screen,
            tags=("interface",),
        )

        self._create_canvas_button(
            canvas=self.canvas,
            text="Parole",
            x=center_x,
            y=center_y + 135,
            width=300,
            height=88,
            font_size=23,
            command=self._show_words_screen,
            tags=("interface",),
        )

    def _show_theme_screen(self) -> None:
        self.current_screen = "theme"
        self._clear_screen()
        self._refresh_background()

        self._create_back_button(
            self._show_settings_screen
        )

        width = max(
            self.canvas.winfo_width(),
            900,
        )
        height = max(
            self.canvas.winfo_height(),
            600,
        )

        center_x = width // 2
        first_y = height // 2 - 120
        row_width = 430
        row_height = 82

        theme_names = (
            "Animali",
            "Natura",
            "Feste",
            "Fantasy",
        )

        for index, theme_name in enumerate(theme_names):
            row_y = first_y + index * 120
            row_tag = f"theme_option_{index}"
            is_selected = theme_name == self.current_theme

            left = center_x - row_width // 2
            right = center_x + row_width // 2
            top = row_y - row_height // 2
            bottom = row_y + row_height // 2

            self.canvas.create_rectangle(
                left,
                top,
                right,
                bottom,
                fill="#FFFFFF",
                outline=self._theme()["border"],
                width=3,
                tags=("interface", row_tag),
            )

            radio_x = left + 42
            radio_radius = 15

            self.canvas.create_oval(
                radio_x - radio_radius,
                row_y - radio_radius,
                radio_x + radio_radius,
                row_y + radio_radius,
                fill="#FFFFFF",
                outline=self._theme()["border"],
                width=3,
                tags=("interface", row_tag),
            )

            if is_selected:
                inner_radius = 8
                self.canvas.create_oval(
                    radio_x - inner_radius,
                    row_y - inner_radius,
                    radio_x + inner_radius,
                    row_y + inner_radius,
                    fill=self._theme()["button"],
                    outline="",
                    tags=("interface", row_tag),
                )

            self.canvas.create_text(
                left + 82,
                row_y,
                text=theme_name,
                anchor="w",
                fill="#4A4A4A",
                font=("Segoe UI", 22, "bold"),
                tags=("interface", row_tag),
            )

            def select_theme(
                _event=None,
                value=theme_name,
            ) -> None:
                self._select_theme(value)

            self.canvas.tag_bind(
                row_tag,
                "<Button-1>",
                select_theme,
            )
            self.canvas.tag_bind(
                row_tag,
                "<Enter>",
                lambda _event: self.canvas.configure(
                    cursor="hand2"
                ),
            )
            self.canvas.tag_bind(
                row_tag,
                "<Leave>",
                lambda _event: self.canvas.configure(
                    cursor="arrow"
                ),
            )

    def _select_theme(self, theme_name: str) -> None:
        if theme_name not in THEMES:
            return

        if theme_name == self.current_theme:
            return

        self.current_theme = theme_name
        self._save_config()
        self._refresh_background()
        self._show_theme_screen()

    def _show_difficulty_screen(self) -> None:
        self.current_screen = "difficulty"
        self._clear_screen()
        self._refresh_background()

        self._create_back_button(
            self._show_settings_screen
        )

        width = max(
            self.canvas.winfo_width(),
            900,
        )
        height = max(
            self.canvas.winfo_height(),
            600,
        )

        center_x = width // 2
        first_y = height // 2 - 120
        row_width = 430
        row_height = 82

        difficulty_names = (
            "Facile",
            "Medio",
            "Difficile",
        )

        for index, difficulty_name in enumerate(difficulty_names):
            row_y = first_y + index * 120
            row_tag = f"difficulty_option_{index}"
            is_selected = difficulty_name == self.current_difficulty

            left = center_x - row_width // 2
            right = center_x + row_width // 2
            top = row_y - row_height // 2
            bottom = row_y + row_height // 2

            self.canvas.create_rectangle(
                left,
                top,
                right,
                bottom,
                fill="#FFFFFF",
                outline=self._theme()["border"],
                width=3,
                tags=("interface", row_tag),
            )

            radio_x = left + 42
            radio_radius = 15

            self.canvas.create_oval(
                radio_x - radio_radius,
                row_y - radio_radius,
                radio_x + radio_radius,
                row_y + radio_radius,
                fill="#FFFFFF",
                outline=self._theme()["border"],
                width=3,
                tags=("interface", row_tag),
            )

            if is_selected:
                inner_radius = 8
                self.canvas.create_oval(
                    radio_x - inner_radius,
                    row_y - inner_radius,
                    radio_x + inner_radius,
                    row_y + inner_radius,
                    fill=self._theme()["button"],
                    outline="",
                    tags=("interface", row_tag),
                )

            self.canvas.create_text(
                left + 82,
                row_y,
                text=difficulty_name,
                anchor="w",
                fill="#4A4A4A",
                font=("Segoe UI", 22, "bold"),
                tags=("interface", row_tag),
            )

            def select_difficulty(
                _event=None,
                value=difficulty_name,
            ) -> None:
                self._select_difficulty(value)

            self.canvas.tag_bind(
                row_tag,
                "<Button-1>",
                select_difficulty,
            )
            self.canvas.tag_bind(
                row_tag,
                "<Enter>",
                lambda _event: self.canvas.configure(
                    cursor="hand2"
                ),
            )
            self.canvas.tag_bind(
                row_tag,
                "<Leave>",
                lambda _event: self.canvas.configure(
                    cursor="arrow"
                ),
            )

    def _select_difficulty(self, difficulty_name: str) -> None:
        if difficulty_name not in DIFFICULTY_FIELD_COUNTS:
            return

        if difficulty_name == self.current_difficulty:
            return

        self.current_difficulty = difficulty_name
        self._save_config()
        self._show_difficulty_screen()

    def _show_words_screen(self) -> None:
        self.current_screen = "words"
        self._clear_screen()
        self._refresh_background()

        self._create_back_button(
            self._show_settings_screen
        )

        panel = tk.Frame(
            self.canvas,
            bg=self._theme()["button"],
            bd=0,
            highlightthickness=0,
        )
        panel.place(
            relx=0.5,
            rely=0.18,
            anchor="n",
            relwidth=0.76,
            relheight=0.74,
        )
        self.screen_widgets.append(panel)

        words_canvas = tk.Canvas(
            panel,
            bg=self._theme()["button"],
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = tk.Scrollbar(
            panel,
            orient="vertical",
            command=words_canvas.yview,
        )

        self._connect_scrollbar(words_canvas, scrollbar)

        words_canvas.pack(
            side="left",
            fill="both",
            expand=True,
        )
        scrollbar.pack(
            side="right",
            fill="y",
        )

        self.words_canvas = words_canvas

        panel.update_idletasks()

        self._render_words_content()

        words_canvas.bind(
            "<Configure>",
            lambda _event: self._paint_scroll_background(
                words_canvas, self.words_scroll_height
            ),
        )
        words_canvas.bind(
            "<MouseWheel>",
            lambda event: words_canvas.yview_scroll(
                -1 if event.delta > 0 else 1,
                "units",
            ),
        )

    def _collect_pending_values(self) -> list[str]:
        if not self.pending_entries:
            return list(self.pending_values)

        return [
            entry.get()
            for entry in self.pending_entries
        ]

    def _render_words_content(self) -> None:
        canvas = self.words_canvas
        for child in canvas.winfo_children():
            child.destroy()
        canvas.delete("all")

        self.button_images = {
            key: value
            for key, value in self.button_images.items()
            if not key.startswith("word_")
        }

        self.pending_entries.clear()

        canvas.update_idletasks()

        available_width = max(
            canvas.winfo_width(),
            700,
        )

        row_width = min(
            820,
            available_width - 80,
        )
        row_width = max(
            560,
            row_width,
        )

        left = max(
            35,
            (available_width - row_width) // 2,
        )

        y = 28
        theme = self._theme()

        for index, word in enumerate(self.words):
            card_height = 70

            card = self._create_balloon_image(
                row_width - 105,
                card_height,
                theme["button"],
            )

            card_key = f"word_card_{index}_{id(card)}"
            self.button_images[card_key] = {
                "normal": card,
            }

            canvas.create_image(
                left,
                y,
                image=card,
                anchor="nw",
            )

            canvas.create_text(
                left + 34,
                y + card_height // 2 + 18,
                text=word,
                anchor="w",
                fill=theme["text"],
                font=(
                    "Segoe UI",
                    20,
                    "bold",
                ),
            )

            self._create_canvas_button(
                canvas=canvas,
                text="🗑",
                x=left + row_width - 88,
                y=y + 10,
                width=64,
                height=54,
                font_size=19,
                command=lambda word_index=index: self._delete_word(
                    word_index
                ),
                anchor="nw",
            )

            y += 105

        for index, value in enumerate(self.pending_values):
            entry_frame = tk.Frame(
                canvas,
                bg="#FFFFFF",
            )

            entry = tk.Entry(
                entry_frame,
                font=(
                    "Segoe UI",
                    17,
                ),
                relief="flat",
                bd=0,
            )
            entry.insert(
                0,
                value,
            )
            entry.pack(
                fill="both",
                expand=True,
                padx=18,
                pady=13,
            )

            entry_window = canvas.create_window(
                left + 18,
                y + 18,
                window=entry_frame,
                anchor="nw",
                width=row_width - 235,
                height=58,
            )

            canvas.create_rectangle(
                left + 18,
                y + 18,
                left + row_width - 217,
                y + 76,
                fill="#FFFFFF",
                outline=theme["border"],
                width=3,
            )
            canvas.tag_lower(
                canvas.find_all()[-1],
                entry_window,
            )

            self.pending_entries.append(entry)

            self._create_canvas_button(
                canvas=canvas,
                text="Aggiungi",
                x=left + row_width - 190,
                y=y + 5,
                width=170,
                height=64,
                font_size=16,
                command=lambda row_index=index: self._save_pending_word(
                    row_index
                ),
                anchor="nw",
            )

            y += 100

        self._create_canvas_button(
            canvas=canvas,
            text="Aggiungi Parola",
            x=left,
            y=y,
            width=255,
            height=70,
            font_size=17,
            command=self._add_pending_word,
            anchor="nw",
        )

        y += 120
        self.words_scroll_height = y

        canvas.configure(
            scrollregion=(
                0,
                0,
                available_width,
                y,
            )
        )
        self._paint_scroll_background(
            canvas,
            y,
        )

    def _add_pending_word(self) -> None:
        self.pending_values = self._collect_pending_values()
        self.pending_values.append("")
        self._render_words_content()

        self.words_canvas.yview_moveto(1.0)

    def _save_pending_word(
        self,
        index: int,
    ) -> None:
        values = self._collect_pending_values()

        if not 0 <= index < len(values):
            return

        word = values[index].strip()

        if not word:
            return

        self.words.append(word)
        values.pop(index)

        self.pending_values = values
        self._save_config()
        self._render_words_content()

    def _delete_word(
        self,
        index: int,
    ) -> None:
        self.pending_values = self._collect_pending_values()

        if not 0 <= index < len(self.words):
            return

        self.words.pop(index)
        self._save_config()
        self._render_words_content()

    def _schedule_resize(
        self,
        event: tk.Event,
    ) -> None:
        if self.resize_job is not None:
            self.after_cancel(
                self.resize_job
            )

        self.resize_job = self.after(
            40,
            lambda: self._resize_interface(
                event.width,
                event.height,
            ),
        )

    def _resize_interface(
        self,
        width: int,
        height: int,
    ) -> None:
        if width <= 1 or height <= 1:
            return

        resized = ImageOps.fit(
            self.background_source,
            (
                width,
                height,
            ),
            method=Image.Resampling.LANCZOS,
        )

        self.background_rendered = resized
        self.background_photo = ImageTk.PhotoImage(
            resized
        )

        self.canvas.itemconfigure(
            self.background_id,
            image=self.background_photo,
        )

        if self.current_screen == "words" and self.words_canvas is not None:
            self._paint_scroll_background(
                self.words_canvas, self.words_scroll_height
            )
        elif self.current_screen == "play" and self.game_canvas is not None:
            self._paint_scroll_background(
                self.game_canvas, self.game_scroll_height
            )

        if self.current_screen == "home":
            play_items = self.canvas.find_withtag(
                "play_button"
            )

            if len(play_items) >= 2:
                self.canvas.coords(
                    play_items[0],
                    width // 2,
                    height // 2,
                )
                self.canvas.coords(
                    play_items[1],
                    width // 2,
                    height // 2,
                )

        if self.current_screen in ("victory", "defeat"):
            self._layout_result_message(width, height)

        if self.current_screen == "play":
            confirm_items = self.canvas.find_withtag(
                "confirm_button"
            )

            if len(confirm_items) >= 2:
                self.canvas.coords(
                    confirm_items[0],
                    width // 2,
                    height - 78,
                )
                self.canvas.coords(
                    confirm_items[1],
                    width // 2,
                    height - 78,
                )

    def _start_game(self) -> None:
        self.current_screen = "play"
        self._clear_screen()
        self._refresh_background()

        self._create_back_button(
            self._show_home_screen
        )

        panel = tk.Frame(
            self.canvas,
            bg=self._theme()["button"],
            bd=0,
            highlightthickness=0,
        )
        panel.place(
            relx=0.5,
            rely=0.17,
            anchor="n",
            relwidth=0.72,
            relheight=0.60,
        )
        self.screen_widgets.append(panel)

        game_canvas = tk.Canvas(
            panel,
            bg=self._theme()["button"],
            highlightthickness=0,
            borderwidth=0,
        )

        scrollbar = tk.Scrollbar(
            panel,
            orient="vertical",
            command=game_canvas.yview,
        )

        self._connect_scrollbar(game_canvas, scrollbar)

        game_canvas.pack(
            side="left",
            fill="both",
            expand=True,
        )

        scrollbar.pack(
            side="right",
            fill="y",
        )

        game_canvas.update_idletasks()
        self.game_canvas = game_canvas

        game_canvas.bind(
            "<Configure>",
            lambda _event: self._paint_scroll_background(
                game_canvas, self.game_scroll_height
            ),
        )

        self.game_entries: list[tk.Entry] = []

        available_width = max(
            game_canvas.winfo_width(),
            700,
        )

        row_width = min(
            720,
            available_width - 80,
        )

        row_width = max(
            500,
            row_width,
        )

        left = max(
            35,
            (available_width - row_width) // 2,
        )

        y = 30

        configured_count = DIFFICULTY_FIELD_COUNTS[
            self.current_difficulty
        ]
        field_count = (
            len(self.words)
            if configured_count is None
            else configured_count
        )

        for _index in range(field_count):
            entry_frame = tk.Frame(
                game_canvas,
                bg="#FFFFFF",
            )

            entry = tk.Entry(
                entry_frame,
                font=(
                    "Segoe UI",
                    18,
                ),
                relief="flat",
                bd=0,
                justify="center",
            )

            entry.pack(
                fill="both",
                expand=True,
                padx=18,
                pady=13,
            )

            game_canvas.create_rectangle(
                left,
                y,
                left + row_width,
                y + 66,
                fill="#FFFFFF",
                outline=self._theme()["border"],
                width=3,
            )

            game_canvas.create_window(
                left + 4,
                y + 4,
                window=entry_frame,
                anchor="nw",
                width=row_width - 8,
                height=58,
            )

            self.game_entries.append(entry)
            y += 92

        self.game_scroll_height = y + 30
        game_canvas.configure(
            scrollregion=(
                0,
                0,
                available_width,
                self.game_scroll_height,
            )
        )
        self._paint_scroll_background(
            game_canvas,
            self.game_scroll_height,
        )

        root_width = max(
            self.canvas.winfo_width(),
            900,
        )
        root_height = max(
            self.canvas.winfo_height(),
            600,
        )

        self._create_canvas_button(
            canvas=self.canvas,
            text="CONFERMA",
            x=root_width // 2,
            y=root_height - 78,
            width=280,
            height=82,
            font_size=21,
            command=self._confirm_game,
            tags=("interface", "confirm_button"),
        )

        game_canvas.bind(
            "<MouseWheel>",
            lambda event: game_canvas.yview_scroll(
                -1 if event.delta > 0 else 1,
                "units",
            ),
        )

    def _confirm_game(self) -> None:
        answers = [entry.get() for entry in self.game_entries]
        won, correct_count, required_count = evaluate_game_answers(
            self.words, answers, self.current_difficulty
        )
        if won:
            self._show_victory_screen()
        else:
            self._show_defeat_screen(correct_count, required_count)

    def _result_text_colors(self) -> tuple[str, str]:
        """Choose a dark shade of the wallpaper's dominant hue for each theme."""
        preview = self.background_source.resize(
            (96, 96), Image.Resampling.BOX
        )
        palette_image = preview.quantize(
            colors=8, method=Image.Quantize.MEDIANCUT
        )
        counts = palette_image.getcolors(96 * 96)
        palette = palette_image.getpalette()
        dominant_index = max(counts)[1]
        start = dominant_index * 3
        red, green, blue = palette[start:start + 3]

        hue, _, saturation = colorsys.rgb_to_hls(
            red / 255, green / 255, blue / 255
        )
        # If the most common wallpaper shade is neutral, borrow the theme hue.
        if saturation < 0.14:
            color = self._theme()["button"].lstrip("#")
            channels = tuple(
                int(color[position:position + 2], 16) / 255
                for position in (0, 2, 4)
            )
            hue, _, saturation = colorsys.rgb_to_hls(*channels)

        deep_rgb = colorsys.hls_to_rgb(
            hue, 0.17, min(0.92, max(0.62, saturation * 0.92))
        )
        deep_color = "#{:02x}{:02x}{:02x}".format(
            *(round(channel * 255) for channel in deep_rgb)
        )
        edge_color = "#{:02x}{:02x}{:02x}".format(
            *(round(channel * 0.80 + 255 * 0.20)
              for channel in (red, green, blue))
        )
        return deep_color, edge_color

    def _layout_result_message(self, width: int, height: int) -> None:
        """Resize the two Curlz MT lines to fit without changing line breaks."""
        if self.current_screen not in ("victory", "defeat"):
            return
        if not getattr(self, "_result_lines", None):
            return
        if not self.canvas.find_withtag("result_line_0"):
            return

        self._result_fonts = []  # Keep Tk font objects alive after this call.
        x = width // 2
        positions = (int(height * 0.43), int(height * 0.63))

        for index, line in enumerate(self._result_lines):
            is_score = self.current_screen == "defeat" and index == 1
            target_size = min(
                115 if not is_score else 90,
                max(30, int(height * (0.15 if not is_score else 0.12))),
            )
            font = tkfont.Font(
                root=self,
                family="Curlz MT",
                size=target_size,
                weight="bold",
            )
            while target_size > 22:
                font.configure(size=target_size)
                if (
                    font.measure(line) <= width * 0.90
                    and font.metrics("linespace") <= height * 0.19
                ):
                    break
                target_size -= 2
            self._result_fonts.append(font)

            y = positions[index]
            outline_ids = self.canvas.find_withtag(
                f"result_line_{index}_outline"
            )
            for item_id, (dx, dy) in zip(
                outline_ids,
                RESULT_OUTLINE_OFFSETS,
            ):
                self.canvas.coords(item_id, x + dx, y + dy)
                self.canvas.itemconfigure(item_id, font=font)

            for item_id in self.canvas.find_withtag(f"result_line_{index}"):
                self.canvas.coords(item_id, x, y)
                self.canvas.itemconfigure(item_id, font=font)

    def _show_result_screen(
        self,
        screen: str,
        first_line: str,
        second_line: str,
    ) -> None:
        self.current_screen = screen
        self._clear_screen()
        self._refresh_background()
        self._result_lines = (first_line, second_line)
        deep_color, edge_color = self._result_text_colors()

        for index, line in enumerate(self._result_lines):
            for _ in RESULT_OUTLINE_OFFSETS:
                self.canvas.create_text(
                    0, 0,
                    text=line,
                    fill=edge_color,
                    anchor="center",
                    justify="center",
                    tags=("interface", f"result_line_{index}_outline"),
                )
            self.canvas.create_text(
                0, 0,
                text=line,
                fill=deep_color,
                anchor="center",
                justify="center",
                tags=("interface", f"result_line_{index}"),
            )

        self._layout_result_message(
            max(self.canvas.winfo_width(), 900),
            max(self.canvas.winfo_height(), 600),
        )
        self._create_back_button(self._show_home_screen)

    def _show_victory_screen(self) -> None:
        self._show_result_screen(
            "victory",
            "CONGRATULAZIONI!",
            "LE HAI INDOVINATE TUTTE!",
        )

    def _show_defeat_screen(
        self, correct_count: int, required_count: int
    ) -> None:
        self._show_result_screen(
            "defeat",
            "Uhm... Non funziona! Riprova!",
            f"Ne hai indovinate {correct_count} su {required_count}",
        )


if __name__ == "__main__":
    app = SharperNightApp()
    app.mainloop()
