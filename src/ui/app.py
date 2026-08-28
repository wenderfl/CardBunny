import customtkinter as ctk
from tkinter import messagebox, filedialog
import os
import sys
import threading
import shutil
import glob
import re
import winsound
from ui.icons import create_link_icon, create_deck_icon, create_model_icon, create_play_icon, create_wait_icon, create_settings_icon, create_upload_icon
from ui.redirector import StdoutRedirector
from ui.tooltip import Tooltip
from ui.widgets import AutoHideScrollableFrame
from cardbunny.config import CONFIG, save_config
from cardbunny.anki_client import invoke_anki
from cardbunny.orchestrator import run_pipeline
from cardbunny.mapper import _map_fields_heuristic

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

class CardBunnyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CardBunny")
        available_height = max(640, self.root.winfo_screenheight() - 80)
        default_height = min(720, available_height)
        self.root.geometry(f"450x{default_height}")
        self.root.minsize(450, min(680, default_height))
        self._closing = False
        self._processing = False
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr

        # Set window icon
        icon_path = resource_path(os.path.join("assets", "icon.ico"))
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

        # Dark Cinematic Background
        self.root.configure(fg_color="#fcfaf7")

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        # Initialize Icons
        self.img_link = ctk.CTkImage(light_image=create_link_icon(color="#101544"), dark_image=create_link_icon(color="#101544"), size=(24, 24))
        self.img_deck = ctk.CTkImage(light_image=create_deck_icon(color="white"), dark_image=create_deck_icon(color="white"), size=(24, 24))
        self.img_model = ctk.CTkImage(light_image=create_model_icon(color="white"), dark_image=create_model_icon(color="white"), size=(24, 24))
        self.img_play = ctk.CTkImage(light_image=create_play_icon(color="#101544"), dark_image=create_play_icon(color="#101544"), size=(36, 36))
        self.img_wait = ctk.CTkImage(light_image=create_wait_icon(color="#101544"), dark_image=create_wait_icon(color="#101544"), size=(36, 36))
        self.img_settings = ctk.CTkImage(light_image=create_settings_icon(color="#101544"), dark_image=create_settings_icon(color="#101544"), size=(18, 18))
        self.img_upload = ctk.CTkImage(light_image=create_upload_icon(color="white"), dark_image=create_upload_icon(color="white"), size=(24, 24))

        # Branding
        self.brand_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.brand_frame.grid(row=0, column=0, sticky="ew", padx=30, pady=(24, 16))

        self.app_title_label = ctk.CTkLabel(
            self.brand_frame, text="CARD\nBUNNY",
            font=ctk.CTkFont(family="Arial", size=26, weight="bold"), 
            text_color="#101544", justify="left"
        )
        self.app_title_label.pack(side="left")

        # Settings Button
        self.settings_btn = ctk.CTkButton(
            self.brand_frame, text="", image=self.img_settings, width=42, height=42,
            corner_radius=0, fg_color="#fcfaf7", hover_color="#e6e6f5",
            border_width=3, border_color="#000000",
            command=self.open_settings,
        )
        self.settings_btn.pack(side="right", anchor="n")
        Tooltip(self.settings_btn, "SETTINGS  ·  CTRL+,")

        self.main_frame = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=1, column=0, padx=30, pady=(4, 10), sticky="nsew")
        
        # URL
        self.url_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.url_frame.pack(fill="x", pady=(0, 14))
        
        self.url_icon_bg = ctk.CTkFrame(self.url_frame, width=42, height=42, fg_color="#858dda", border_width=3, border_color="#000000", corner_radius=0)
        self.url_icon_bg.pack(side="left", padx=(0, 15))
        self.url_icon_bg.pack_propagate(False)
        self.url_icon_label = ctk.CTkLabel(self.url_icon_bg, text="", image=self.img_link)
        self.url_icon_label.pack(expand=True)
        Tooltip(self.url_icon_bg, "YOUTUBE VIDEO URL")
        
        self.url_var = ctk.StringVar()
        self.url_entry = ctk.CTkEntry(
            self.url_frame, textvariable=self.url_var, height=42, font=ctk.CTkFont(size=14, weight="bold"), 
            placeholder_text="PASTE YOUTUBE LINK...", placeholder_text_color="#555555",
            corner_radius=0, fg_color="#fcfaf7", border_width=3, border_color="#000000", text_color="#101544"
        )
        self.url_entry.pack(side="left", fill="x", expand=True)
        self.url_tooltip = Tooltip(
            self.url_entry, "PASTE A YOUTUBE URL OR SELECT A LOCAL VIDEO",
        )
        self.url_var.trace_add("write", self._on_url_changed)

        # Local files optional. Keeps URL as default flow.
        self.local_video_path = None
        self.local_srt_path = None
        self.local_files_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.local_files_frame.pack(fill="x", pady=0)

        self.local_video_label, self.local_video_clear_btn = self._create_local_file_row(
            self.local_files_frame, "Video", self.select_local_video, "#858dda"
        )
        self.local_srt_label, self.local_srt_clear_btn = self._create_local_file_row(
            self.local_files_frame, "Subtitle", self.select_local_subtitle, "#858dda"
        )
        
        # Deck
        self.deck_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.deck_frame.pack(fill="x", pady=(0, 14))
        
        self.deck_icon_bg = ctk.CTkFrame(self.deck_frame, width=42, height=42, fg_color="#6253cc", border_width=3, border_color="#000000", corner_radius=0)
        self.deck_icon_bg.pack(side="left", padx=(0, 15))
        self.deck_icon_bg.pack_propagate(False)
        self.deck_icon_label = ctk.CTkLabel(self.deck_icon_bg, text="", image=self.img_deck)
        self.deck_icon_label.pack(expand=True)
        Tooltip(self.deck_icon_bg, "ANKI DECK")
        
        self.deck_combo_shell = ctk.CTkFrame(self.deck_frame, height=42, fg_color="#000000", corner_radius=0)
        self.deck_combo_shell.pack(side="left", fill="x", expand=True)
        self.deck_combo_shell.pack_propagate(False)
        self.deck_cb = ctk.CTkComboBox(
            self.deck_combo_shell, height=36, font=ctk.CTkFont(size=14, weight="bold"), values=["Loading..."], state="readonly",
            corner_radius=0, fg_color="#fcfaf7", border_width=0, text_color="#101544",
            button_color="#FFFFFF", button_hover_color="#e6e6f5", dropdown_fg_color="#fcfaf7", dropdown_text_color="#101544"
        )
        self.deck_cb.pack(fill="both", expand=True, padx=3, pady=3)
        self.deck_cb.set("Loading...")
        
        # Model
        self.model_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.model_frame.pack(fill="x", pady=(0, 18))
        
        self.model_icon_bg = ctk.CTkFrame(self.model_frame, width=42, height=42, fg_color="#6253cc", border_width=3, border_color="#000000", corner_radius=0)
        self.model_icon_bg.pack(side="left", padx=(0, 15))
        self.model_icon_bg.pack_propagate(False)
        self.model_icon_label = ctk.CTkLabel(self.model_icon_bg, text="", image=self.img_model)
        self.model_icon_label.pack(expand=True)
        Tooltip(self.model_icon_bg, "ANKI NOTE TYPE")
        
        self.model_combo_shell = ctk.CTkFrame(self.model_frame, height=42, fg_color="#000000", corner_radius=0)
        self.model_combo_shell.pack(side="left", fill="x", expand=True)
        self.model_combo_shell.pack_propagate(False)
        self.model_cb = ctk.CTkComboBox(
            self.model_combo_shell, height=36, font=ctk.CTkFont(size=14, weight="bold"), values=["Loading..."], state="readonly",
            corner_radius=0, fg_color="#fcfaf7", border_width=0, text_color="#101544",
            button_color="#FFFFFF", button_hover_color="#e6e6f5", dropdown_fg_color="#fcfaf7", dropdown_text_color="#101544"
        )
        self.model_cb.pack(fill="both", expand=True, padx=3, pady=3)
        self.model_cb.set("Loading...")
        
        # Status Label & ProgressBar
        self.status_var = ctk.StringVar(value="STATUS: CONNECTING TO ANKI...")
        self.status_label = ctk.CTkLabel(
            self.main_frame, textvariable=self.status_var,
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#101544",
            justify="left", wraplength=390,
        )
        self.status_label.pack(anchor="w", pady=(0, 8))
        
        self.progress_frame = ctk.CTkFrame(self.main_frame, height=16, fg_color="#fcfaf7", border_width=3, border_color="#000000", corner_radius=0)
        self.progress_frame.pack(fill="x", pady=(0, 18))
        self.progress_frame.pack_propagate(False)
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, mode="determinate", height=8, corner_radius=0, fg_color="#fcfaf7", progress_color="#858dda")
        self.progress_bar.pack(fill="both", expand=True, padx=3, pady=3)
        self.progress_bar.set(0)
        
        # Stepper (Visual Step Indicator)
        self.stepper_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.stepper_frame.pack(fill="x", pady=(0, 18))
        
        self.stepper_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        self.step_1 = ctk.CTkButton(self.stepper_frame, text="1. DOWN", font=ctk.CTkFont(size=11, weight="bold"), height=35, fg_color="#fcfaf7", text_color="#101544", text_color_disabled="#555555", state="disabled", corner_radius=0, border_width=3, border_color="#000000")
        self.step_1.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        
        self.step_2 = ctk.CTkButton(self.stepper_frame, text="2. AI", font=ctk.CTkFont(size=11, weight="bold"), height=35, fg_color="#fcfaf7", text_color="#101544", text_color_disabled="#555555", state="disabled", corner_radius=0, border_width=3, border_color="#000000")
        self.step_2.grid(row=0, column=1, padx=5, sticky="ew")
        
        self.step_3 = ctk.CTkButton(self.stepper_frame, text="3. MEDIA", font=ctk.CTkFont(size=11, weight="bold"), height=35, fg_color="#fcfaf7", text_color="#101544", text_color_disabled="#555555", state="disabled", corner_radius=0, border_width=3, border_color="#000000")
        self.step_3.grid(row=0, column=2, padx=5, sticky="ew")
        
        self.step_4 = ctk.CTkButton(self.stepper_frame, text="4. ANKI", font=ctk.CTkFont(size=11, weight="bold"), height=35, fg_color="#fcfaf7", text_color="#101544", text_color_disabled="#555555", state="disabled", corner_radius=0, border_width=3, border_color="#000000")
        self.step_4.grid(row=0, column=3, padx=(5, 0), sticky="ew")
        
        # Play Button
        self.start_btn = ctk.CTkButton(
            self.main_frame, text="START", image=self.img_play, compound="left",
            height=70, corner_radius=0, font=ctk.CTkFont(size=16, weight="bold"),
            hover_color="#6253cc", fg_color="#858dda",
            text_color="#101544", text_color_disabled="#555555",
            border_width=4, border_color="#000000",
            state="disabled", command=self.start_processing,
        )
        self.start_btn.pack(fill="x", pady=(0, 18))
        Tooltip(self.start_btn, "START PROCESSING  ·  CTRL+ENTER")
        
        # Log Box
        self.log_text = ctk.CTkTextbox(
            self.main_frame, height=150, font=ctk.CTkFont(family="Consolas", size=12, weight="bold"), 
            fg_color="#e6e6f5", text_color="#444444", corner_radius=0,
            border_color="#000000", border_width=3,
        )
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")
        Tooltip(
            self.log_text,
            "ACTIVITY LOG  ·  SELECT TEXT AND PRESS CTRL+C TO COPY",
        )
        
        self.redirector = StdoutRedirector(self.log_text, self._log_sniffer)
        sys.stdout = self.redirector
        sys.stderr = self.redirector
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self._cleanup_zombie_workspaces()
        self._configure_shortcuts()
        self.root.after(200, self.load_anki_data)



    def _create_local_file_row(self, parent, label, command, bg_color):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 14))
        
        icon_bg = ctk.CTkFrame(row, width=42, height=42, fg_color=bg_color, border_width=3, border_color="#000000", corner_radius=0)
        icon_bg.pack(side="left", padx=(0, 15))
        icon_bg.pack_propagate(False)
        icon_label = ctk.CTkLabel(icon_bg, text="📄", font=ctk.CTkFont(size=18), text_color="white")
        icon_label.pack(expand=True)
        Tooltip(icon_bg, f"LOCAL {label.upper()} FILE")

        inner_frame = ctk.CTkFrame(row, fg_color="#fcfaf7", height=42, border_width=3, border_color="#000000", corner_radius=0)
        inner_frame.pack(side="left", fill="x", expand=True)
        inner_frame.pack_propagate(False)
        
        btn_text = f"SELECT {label.upper()}"
        select_btn = ctk.CTkButton(
            inner_frame, text=btn_text, width=110, height=30, fg_color="#858dda",
            hover_color="#1A4DE5", text_color="white", command=command, corner_radius=0,
            font=ctk.CTkFont(size=11, weight="bold"), border_width=2, border_color="#000000"
        )
        select_btn.pack(side="left", padx=5, pady=5)
        shortcut = "CTRL+O" if label == "Video" else "CTRL+SHIFT+O"
        Tooltip(select_btn, f"SELECT {label.upper()}  ·  {shortcut}")
        
        value_label = ctk.CTkLabel(
            inner_frame, text="NOT SELECTED", anchor="w", text_color="#555555",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        value_label.pack(side="left", fill="x", expand=True, padx=(10, 0))
        value_label.tooltip = Tooltip(value_label, "NO FILE SELECTED")
        
        clear_btn = ctk.CTkButton(
            inner_frame, text="×", width=30, height=30, fg_color="#6253cc",
            hover_color="#E60039", text_color="#101544", font=ctk.CTkFont(size=16, weight="bold"),
            command=lambda kind=label: self.clear_local_file(kind), corner_radius=0,
            border_width=2, border_color="#000000"
        )
        Tooltip(clear_btn, f"REMOVE SELECTED {label.upper()}")
        return value_label, clear_btn

    def select_local_video(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="Select video",
            filetypes=[
                ("Video files", "*.mp4 *.mkv *.webm *.avi *.mov *.m4v"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.local_video_path = os.path.abspath(path)
            self.local_video_label.configure(
                text=self._shorten_filename(path), text_color="#101544",
            )
            self.local_video_label.tooltip.set_text(self.local_video_path)
            self.local_video_clear_btn.pack(
                side="right", padx=5, pady=5, before=self.local_video_label,
            )
            self.url_entry.configure(
                placeholder_text="LOCAL VIDEO SELECTED — URL IGNORED",
                state="disabled",
            )
            self.url_tooltip.set_text(
                "LOCAL VIDEO SELECTED — THE YOUTUBE URL IS IGNORED",
            )
            self.status_var.set("Status: Local video selected")

    def select_local_subtitle(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="Select original subtitle",
            filetypes=[("SubRip Subtitle", "*.srt")],
        )
        if path:
            self.local_srt_path = os.path.abspath(path)
            self.local_srt_label.configure(
                text=self._shorten_filename(path), text_color="#101544",
            )
            self.local_srt_label.tooltip.set_text(self.local_srt_path)
            self.local_srt_clear_btn.pack(
                side="right", padx=5, pady=5, before=self.local_srt_label,
            )

    def clear_local_file(self, kind):
        if kind == "Video":
            self.local_video_path = None
            self.local_video_label.configure(text="NOT SELECTED", text_color="#555555")
            self.local_video_label.tooltip.set_text("NO FILE SELECTED")
            self.local_video_clear_btn.pack_forget()
            self.url_entry.configure(
                placeholder_text="PASTE YOUTUBE LINK...",
                state="disabled" if self._processing else "normal",
            )
            self.url_tooltip.set_text(
                "PASTE A YOUTUBE URL OR SELECT A LOCAL VIDEO",
            )
        else:
            self.local_srt_path = None
            self.local_srt_label.configure(text="NOT SELECTED", text_color="#555555")
            self.local_srt_label.tooltip.set_text("NO FILE SELECTED")
            self.local_srt_clear_btn.pack_forget()

    @staticmethod
    def _shorten_filename(path, max_length=20):
        name = os.path.basename(path)
        if len(name) <= max_length:
            return name

        stem, extension = os.path.splitext(name)
        available = max(5, max_length - len(extension) - 1)
        return f"{stem[:available]}…{extension}"

    def _configure_shortcuts(self):
        def select_video(_event=None):
            if not self._processing:
                self.select_local_video()
            return "break"

        def select_subtitle(_event=None):
            if not self._processing:
                self.select_local_subtitle()
            return "break"

        def open_settings(_event=None):
            if self.settings_btn.cget("state") == "normal":
                self.open_settings()
            return "break"

        def start(_event=None):
            if self.start_btn.cget("state") == "normal":
                self.start_processing()
            return "break"

        self.root.bind("<Control-o>", select_video)
        self.root.bind("<Control-Shift-O>", select_subtitle)
        self.root.bind("<Control-comma>", open_settings)
        self.root.bind("<Control-Return>", start)

    def _center_window(self, window, width, height):
        self.root.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
        max_x = max(10, window.winfo_screenwidth() - width - 10)
        max_y = max(10, window.winfo_screenheight() - height - 60)
        window.geometry(
            f"{width}x{height}+{max(10, min(x, max_x))}+{max(10, min(y, max_y))}"
        )

    def _safe_after(self, callback):
        if self._closing:
            return
        try:
            self.root.after(0, callback)
        except Exception:
            pass

    def _on_close(self):
        if self._closing:
            return
        if self._processing and not messagebox.askyesno(
            "Processing in progress",
            "CardBunny is still processing a video. Exit anyway?",
            icon="warning",
            parent=self.root,
        ):
            return

        self._closing = True
        if sys.stdout is self.redirector:
            sys.stdout = self._original_stdout
        if sys.stderr is self.redirector:
            sys.stderr = self._original_stderr
        try:
            self.root.destroy()
        except Exception:
            pass

    def open_settings(self):
        """Opens a single window for Anki and local AI integrations."""
        if hasattr(self, "settings_window") and self.settings_window.winfo_exists():
            self.settings_window.focus()
            return

        window = ctk.CTkToplevel(self.root)
        self.settings_window = window
        window.title("Settings")
        settings_height = min(
            700, max(580, window.winfo_screenheight() - 80),
        )
        self._center_window(window, 560, settings_height)
        window.minsize(560, min(620, settings_height))
        window.resizable(True, True)
        window.configure(fg_color="#fcfaf7")
        window.transient(self.root)
        window.grab_set()
        
        if os.path.exists(resource_path(os.path.join("assets", "icon.ico"))):
            window.iconbitmap(resource_path(os.path.join("assets", "icon.ico")))
            


        title = ctk.CTkLabel(window, text="SETTINGS", font=ctk.CTkFont(size=30, weight="bold"), text_color="#101544")
        title.pack(anchor="w", padx=24, pady=(18, 2))
        subtitle = ctk.CTkLabel(window, text="INTEGRATIONS USED IN PROCESSING", text_color="#444444", font=ctk.CTkFont(size=14, weight="bold"))
        subtitle.pack(anchor="w", padx=24, pady=(0, 12))

        divider = ctk.CTkFrame(window, height=4, fg_color="#000000", corner_radius=0)
        divider.pack(fill="x", padx=24, pady=(0, 14))

        tab_bar = ctk.CTkFrame(window, fg_color="transparent")
        tab_bar.pack(fill="x", padx=20, pady=(0, 12))
        tab_bar.grid_columnconfigure((0, 1, 2), weight=1, uniform="settings_tabs")

        content_panel = ctk.CTkFrame(
            window, fg_color="#e6e6f5", border_width=3,
            border_color="#000000", corner_radius=0,
        )
        content_panel.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        tab_options = {
            "fg_color": "transparent",
            "corner_radius": 0,
            "scrollbar_button_color": "#101544",
            "scrollbar_button_hover_color": "#858dda",
        }
        anki_tab = AutoHideScrollableFrame(content_panel, **tab_options)
        ai_tab = AutoHideScrollableFrame(content_panel, **tab_options)
        lang_tab = AutoHideScrollableFrame(content_panel, **tab_options)
        tab_frames = {"ANKI": anki_tab, "LOCAL AI": ai_tab, "LANGUAGES": lang_tab}
        tab_order = list(tab_frames)
        tab_buttons = {}
        tab_focus_targets = {}
        current_tab = {"name": "LOCAL AI"}

        def select_tab(name):
            current_tab["name"] = name
            for frame in tab_frames.values():
                frame.pack_forget()
            tab_frames[name].pack(fill="both", expand=True, padx=8, pady=8)
            for tab_name, button in tab_buttons.items():
                selected = tab_name == name
                button.configure(
                    text=f"● {tab_name}" if selected else tab_name,
                    fg_color="#101544" if selected else "#FFFFFF",
                    text_color="#FFFFFF" if selected else "#101544",
                    hover_color="#222222" if selected else "#e6e6f5",
                )
            target = tab_focus_targets.get(name)
            if target is not None:
                window.after_idle(target.focus_set)

        def cycle_tabs(direction=1):
            index = tab_order.index(current_tab["name"])
            select_tab(tab_order[(index + direction) % len(tab_order)])
            return "break"

        for column, name in enumerate(tab_frames):
            button = ctk.CTkButton(
                tab_bar, text=name, height=42, corner_radius=0,
                fg_color="#fcfaf7", hover_color="#e6e6f5", text_color="#101544",
                border_width=3, border_color="#000000",
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda tab_name=name: select_tab(tab_name),
            )
            button.grid(
                row=0, column=column, sticky="ew",
                padx=(0, 5) if column == 0 else ((5, 0) if column == 2 else 5),
            )
            tab_buttons[name] = button
            button.bind("<Left>", lambda _event: cycle_tabs(-1))
            button.bind("<Right>", lambda _event: cycle_tabs(1))

        self.settings_vars = {
            "anki_url": ctk.StringVar(value=CONFIG['anki'].get('url', 'http://127.0.0.1:8765')),
            "deck_name": ctk.StringVar(value=CONFIG['anki'].get('deck_name', '')),
            "model_name": ctk.StringVar(value=CONFIG['anki'].get('model_name', '')),
            "base_url": ctk.StringVar(value=CONFIG['translation'].get('base_url', '')),
            "ai_model": ctk.StringVar(value=CONFIG['translation'].get('model', '')),
            "api_key": ctk.StringVar(value=CONFIG['translation'].get('api_key', '')),
            "whisper_model": ctk.StringVar(value=CONFIG['whisper'].get('model_size', 'base')),
            "device": ctk.StringVar(value=CONFIG['whisper'].get('device', 'cpu')),
            "compute_type": ctk.StringVar(value=CONFIG['whisper'].get('compute_type', 'int8')),
            "cpu_threads": ctk.StringVar(value=str(CONFIG['whisper'].get('cpu_threads', 4))),
            "whisper_language": ctk.StringVar(value=CONFIG['whisper'].get('language', 'en')),
            "translation_target": ctk.StringVar(value=CONFIG['translation'].get('target_language', 'Brazilian Portuguese (pt-BR)')),
        }

        anki_url_entry = self._settings_entry(
            anki_tab, "AnkiConnect Address", "anki_url",
        )
        self._settings_entry(anki_tab, "Default Deck", "deck_name")
        self._settings_entry(anki_tab, "Default Note Type", "model_name")
        hint = ctk.CTkLabel(anki_tab, text="Anki must be open with AnkiConnect active.",
                            text_color="#444444", font=ctk.CTkFont(size=12, weight="bold"), wraplength=400, justify="left")
        hint.pack(anchor="w", padx=14, pady=(8, 0))

        base_url_entry = self._settings_entry(
            ai_tab, "OpenAI compatible endpoint", "base_url",
        )
        self._settings_entry(ai_tab, "Translation model", "ai_model")
        self._settings_entry(ai_tab, "API Key", "api_key", show="•")
        self._settings_combo(
            ai_tab,
            "Whisper Model",
            "whisper_model",
            ["small.en", "medium.en", "tiny.en", "base.en", "small", "medium", "large-v3", "turbo"],
        )

        ai_row = ctk.CTkFrame(ai_tab, fg_color="transparent")
        ai_row.pack(fill="x", padx=14, pady=(6, 0))
        self._settings_combo(ai_row, "Device", "device", ["cpu", "cuda"], side="left")
        self._settings_combo(ai_row, "Precision", "compute_type", ["int8", "float16", "float32"], side="left")
        self._settings_entry(ai_row, "Threads", "cpu_threads", width=90, side="left")

        # Languages Tab
        whisper_language_combo = self._settings_combo(
            lang_tab, 
            "Video Language (Whisper)", 
            "whisper_language", 
            ["en", "pt", "es", "fr", "de", "it", "ja", "ko", "zh", "ru"],
            allow_custom=True,
        )
        self._settings_combo(
            lang_tab, 
            "Target Language (Translation)", 
            "translation_target", 
            ["Brazilian Portuguese (pt-BR)", "English", "Spanish", "French", "German", "Japanese", "Portuguese (pt-PT)"],
            allow_custom=True,
        )
        hint_lang = ctk.CTkLabel(
            lang_tab, text="You can manually type another language if you wish.",
            text_color="#444444", font=ctk.CTkFont(size=12, weight="bold"), wraplength=400, justify="left"
        )
        hint_lang.pack(anchor="w", padx=14, pady=(8, 0))
        tab_focus_targets.update({
            "ANKI": anki_url_entry,
            "LOCAL AI": base_url_entry,
            "LANGUAGES": whisper_language_combo,
        })
        select_tab("LOCAL AI")
        window.bind("<Escape>", lambda _event: window.destroy())
        window.bind("<Control-s>", lambda _event: self.save_settings())
        window.bind("<Control-Tab>", lambda _event: cycle_tabs(1))
        window.bind("<Control-Shift-Tab>", lambda _event: cycle_tabs(-1))

        footer = ctk.CTkFrame(window, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 14))

        btn_import_shadow = ctk.CTkFrame(footer, fg_color="#000000", corner_radius=0)
        btn_import_shadow.pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_import_shadow, text="IMPORT", width=80, height=45, fg_color="#fcfaf7", hover_color="#e6e6f5",
                      text_color="#101544", border_width=3, border_color="#000000", corner_radius=0,
                      font=ctk.CTkFont(size=14, weight="bold"), command=self.import_settings).pack(padx=(0, 4), pady=(0, 4))

        btn_export_shadow = ctk.CTkFrame(footer, fg_color="#000000", corner_radius=0)
        btn_export_shadow.pack(side="left")
        ctk.CTkButton(btn_export_shadow, text="EXPORT", width=80, height=45, fg_color="#fcfaf7", hover_color="#e6e6f5",
                      text_color="#101544", border_width=3, border_color="#000000", corner_radius=0,
                      font=ctk.CTkFont(size=14, weight="bold"), command=self.export_settings).pack(padx=(0, 4), pady=(0, 4))

        btn_cancel_shadow = ctk.CTkFrame(footer, fg_color="#000000", corner_radius=0)
        btn_cancel_shadow.pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_cancel_shadow, text="CANCEL", width=120, height=45, fg_color="#6253cc", hover_color="#E60039",
                      text_color="#101544", border_width=3, border_color="#000000", corner_radius=0,
                      font=ctk.CTkFont(size=14, weight="bold"), command=window.destroy).pack(padx=(0, 4), pady=(0, 4))

        btn_save_shadow = ctk.CTkFrame(footer, fg_color="#000000", corner_radius=0)
        btn_save_shadow.pack(side="right")
        ctk.CTkButton(btn_save_shadow, text="SAVE", width=140, height=45, fg_color="#858dda", hover_color="#1A4DE5",
                      text_color="white", border_width=3, border_color="#000000", corner_radius=0,
                      font=ctk.CTkFont(size=14, weight="bold"), command=self.save_settings).pack(padx=(0, 4), pady=(0, 4))

    def _settings_entry(self, parent, label, key, show=None, width=None, side=None):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(
            fill="x", expand=side is not None,
            padx=14 if side is None else 4,
            pady=(6, 0), side=side,
        )
        ctk.CTkLabel(frame, text=label.upper(), text_color="#101544", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")

        shadow_frame = ctk.CTkFrame(frame, fg_color="#000000", corner_radius=0)
        shadow_frame.pack(fill="x", pady=(3, 0))

        entry_options = {
            "textvariable": self.settings_vars[key], "height": 45,
            "fg_color": "#FFFFFF", "border_width": 3, "border_color": "#000000",
            "corner_radius": 0, "text_color": "#101544", "font": ctk.CTkFont(size=14, weight="bold")
        }
        if show is not None:
            entry_options["show"] = show
        if width is not None:
            entry_options["width"] = width
        entry = ctk.CTkEntry(shadow_frame, **entry_options)
        entry.pack(fill="x", expand=True, padx=(0, 4), pady=(0, 4))
        return entry

    def _settings_combo(
        self, parent, label, key, values, side=None, allow_custom=False,
    ):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(
            fill="x", expand=side is not None,
            padx=14 if side is None else 4,
            pady=(6, 0), side=side,
        )
        ctk.CTkLabel(frame, text=label.upper(), text_color="#101544", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")

        shadow_frame = ctk.CTkFrame(frame, fg_color="#000000", corner_radius=0)
        shadow_frame.pack(fill="x", pady=(3, 0))

        combo = ctk.CTkComboBox(shadow_frame, variable=self.settings_vars[key], values=values, height=39,
                                width=112 if side else 200, fg_color="#FFFFFF", border_width=0,
                                corner_radius=0, text_color="#101544",
                                state="normal" if allow_custom else "readonly",
                                font=ctk.CTkFont(size=14, weight="bold"),
                                button_color="#FFFFFF", button_hover_color="#e6e6f5",
                                dropdown_fg_color="#fcfaf7", dropdown_text_color="#101544")
        combo.pack(fill="x", expand=True, padx=(3, 7), pady=(3, 7))
        return combo

    def save_settings(self):
        try:
            threads = int(self.settings_vars['cpu_threads'].get().strip())
            if threads < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Settings", "Threads must be an integer greater than zero.", parent=self.settings_window)
            return

        required = ('anki_url', 'base_url', 'ai_model', 'whisper_model')
        if any(not self.settings_vars[key].get().strip() for key in required):
            messagebox.showerror("Settings", "Fill in the required addresses and models.", parent=self.settings_window)
            return

        CONFIG['anki'].update({
            'url': self.settings_vars['anki_url'].get().strip(),
            'deck_name': self.settings_vars['deck_name'].get().strip(),
            'model_name': self.settings_vars['model_name'].get().strip(),
        })
        CONFIG['translation'].update({
            'base_url': self.settings_vars['base_url'].get().strip(),
            'model': self.settings_vars['ai_model'].get().strip(),
            'api_key': self.settings_vars['api_key'].get().strip(),
            'target_language': self.settings_vars['translation_target'].get().strip(),
        })
        CONFIG['whisper'].update({
            'model_size': self.settings_vars['whisper_model'].get().strip(),
            'device': self.settings_vars['device'].get().strip(),
            'compute_type': self.settings_vars['compute_type'].get().strip(),
            'cpu_threads': threads,
            'language': self.settings_vars['whisper_language'].get().strip(),
        })
        save_config(CONFIG)
        self.settings_window.destroy()
        self.status_var.set("Status: Settings saved")
        self.root.after(100, self.load_anki_data)
        
    def export_settings(self):
        path = filedialog.asksaveasfilename(
            parent=self.settings_window, title="Export Settings",
            defaultextension=".json", filetypes=[("JSON files", "*.json")]
        )
        if path:
            import json
            try:
                # We export the currently saved CONFIG state.
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(CONFIG, f, indent=4)
                messagebox.showinfo("Export Settings", "Settings exported successfully.", parent=self.settings_window)
            except Exception as e:
                messagebox.showerror("Error", f"Could not export settings: {e}", parent=self.settings_window)

    def import_settings(self):
        path = filedialog.askopenfilename(
            parent=self.settings_window, title="Import Settings",
            filetypes=[("JSON files", "*.json")]
        )
        if path:
            import json
            try:
                with open(path, "r", encoding="utf-8") as f:
                    new_config = json.load(f)
                CONFIG.update(new_config)
                save_config(CONFIG)
                messagebox.showinfo("Import Settings", "Settings imported successfully. Re-open settings to view changes.", parent=self.settings_window)
                self.settings_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Could not import settings: {e}", parent=self.settings_window)
        
        
    def _on_url_changed(self, *args):
        """Automatically sanitizes the URL pasted by the user."""
        try:
            raw = self.url_var.get()
            # If nothing yet, ignore
            if not raw:
                return
            
            cleaned = raw.strip()
            
            # Detect duplicate pasted URLs (e.g. https://...https://...)
            if cleaned.count('http') > 1:
                match = re.search(r'https?://[^\s]+', cleaned)
                if match:
                    cleaned = match.group(0)
            
            # Only update if changed (avoids infinite loop)
            if cleaned != raw:
                self.url_var.set(cleaned)
        except Exception:
            pass
        
    def _cleanup_zombie_workspaces(self):
        """Scans and deletes orphan workspaces from previous sessions that closed abruptly."""
        zombies = glob.glob("workspace_*")
        for zombie in zombies:
            try:
                shutil.rmtree(zombie)
            except Exception:
                pass
        
    def _update_stepper(self, step_number):
        steps = [self.step_1, self.step_2, self.step_3, self.step_4]
        # Clear all
        for btn in steps:
            btn.configure(fg_color="#fcfaf7", text_color_disabled="#555555")
            
        # Light up the current one
        if 1 <= step_number <= 4:
            steps[step_number - 1].configure(fg_color="#6253cc", text_color_disabled="#101544")
        
    def _log_sniffer(self, string):
        s = string.lower()
        transcription_progress = re.search(r"transcription_progress:\s*(\d+)%", s)
        if transcription_progress:
            percent = max(0, min(100, int(transcription_progress.group(1))))
            details = string.split("|", 1)[1].strip() if "|" in string else ""
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self.progress_bar.set(percent / 100)
            self.status_var.set(f"Transcription: {percent}% — {details}")
            self._update_stepper(2)
        elif "downloading video" in s:
            self.status_var.set("Status: Downloading video (yt-dlp)...")
            self._update_stepper(1)
        elif "preparing whisper model" in s:
            self.status_var.set("Status: Preparing Whisper model (first use may take a while)...")
            self._update_stepper(2)
        elif "whisper model" in s and "available" in s:
            self.status_var.set("Status: Transcribing audio (Whisper)...")
            self._set_indeterminate_progress()
            self._update_stepper(2)
        elif "local transcription with whisper" in s:
            self.status_var.set("Status: Transcribing Audio (Whisper)...")
            self._update_stepper(2)
        elif "starting translation" in s:
            self.status_var.set("Status: Translating Text (Omniroute AI)...")
            self._set_indeterminate_progress()
            self._update_stepper(2)
        elif "auditing voice coverage" in s:
            self.status_var.set("Status: Auditing untranscribed speeches...")
            self._set_indeterminate_progress()
            self._update_stepper(2)
        elif "slicing and exporting" in s:
            self.status_var.set("Status: Slicing Media (FFmpeg)...")
            self._set_indeterminate_progress()
            self._update_stepper(3)
        elif "added to anki" in s:
            self.status_var.set("Status: Inserting into Anki...")
            self._update_stepper(4)
        elif "cleaning" in s:
            self.status_var.set("Status: Cleaning Trash...")
            self._update_stepper(0)

    def _set_indeterminate_progress(self):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()
            
    def load_anki_data(self):
        print("Connecting to Anki...\n")
        self.status_var.set("Status: Connecting to Anki...")
        self.start_btn.configure(state="disabled")
        self.deck_cb.configure(values=["Connecting..."], state="readonly")
        self.model_cb.configure(values=["Connecting..."], state="readonly")
        self.deck_cb.set("Connecting...")
        self.model_cb.set("Connecting...")
        self._set_indeterminate_progress()

        threading.Thread(target=self._fetch_anki_data, daemon=True).start()

    def _fetch_anki_data(self):
        """Fetches Anki data away from Tk's event loop."""
        decks = invoke_anki('deckNames')
        models = invoke_anki('modelNames')

        self._safe_after(lambda: self._apply_anki_data(decks, models))

    def _apply_anki_data(self, decks, models):
        """Applies an Anki response on Tk's UI thread."""
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)

        if not decks or not models:
            self.status_var.set("Status: Anki offline or missing decks/note types")
            print("Critical Error: Anki not found.")
            self.start_btn.configure(state="disabled")
            self.deck_cb.configure(values=["Connection Error"])
            self.model_cb.configure(values=["Connection Error"])
            self.deck_cb.set("Connection Error")
            self.model_cb.set("Connection Error")
            return
            
        self.all_decks = decks
        self.current_deck_context = ""
        self.deck_cb.configure(command=self.on_deck_select)
        
        self.model_cb.configure(values=models)
        self.start_btn.configure(state="normal")
        
        saved_deck = CONFIG['anki'].get('deck_name')
        if saved_deck in decks:
            self.deck_cb.set(saved_deck)
            if "::" in saved_deck:
                self.current_deck_context = "::".join(saved_deck.split("::")[:-1])
            else:
                self.current_deck_context = ""
            self._render_deck_dropdown()
        elif decks:
            top = [d for d in decks if "::" not in d]
            first = top[0] if top else decks[0]
            self.deck_cb.set(first)
            self.current_deck_context = ""
            self._render_deck_dropdown()
            
        if CONFIG['anki']['model_name'] in models:
            self.model_cb.set(CONFIG['anki']['model_name'])
        elif models:
            self.model_cb.set(models[0])

        self.status_var.set("Status: Ready")
        print("Ready to process videos.\n")

    def on_deck_select(self, choice):
        if choice == "🔙 Back":
            if "::" in self.current_deck_context:
                self.current_deck_context = "::".join(self.current_deck_context.split("::")[:-1])
            else:
                self.current_deck_context = ""
            self._render_deck_dropdown()
            
            if self.current_deck_context:
                self.deck_cb.set(self.current_deck_context)
            else:
                top = [d for d in self.all_decks if "::" not in d]
                self.deck_cb.set(top[0] if top else "")
            return
            
        has_subdecks = any(d.startswith(choice + "::") for d in self.all_decks)
        if has_subdecks:
            self.current_deck_context = choice
            self._render_deck_dropdown()

    def _render_deck_dropdown(self):
        if not self.current_deck_context:
            values = [d for d in self.all_decks if "::" not in d]
            self.deck_cb.configure(values=values)
        else:
            context_level = self.current_deck_context.count("::")
            direct_subdecks = [
                d for d in self.all_decks 
                if d.startswith(self.current_deck_context + "::") and d.count("::") == context_level + 1
            ]
            values = ["🔙 Back", self.current_deck_context] + direct_subdecks
            self.deck_cb.configure(values=values)

    def start_processing(self):
        url = self.url_var.get().strip()
        deck = self.deck_cb.get()
        model = self.model_cb.get()
        
        if not url and not self.local_video_path:
            messagebox.showerror("Warning", "Insert a YouTube link or select a local video.")
            return

        if self.local_video_path and not os.path.isfile(self.local_video_path):
            messagebox.showerror("Warning", "The selected local video is no longer available.")
            self.clear_local_file("Video")
            return

        if self.local_srt_path and not os.path.isfile(self.local_srt_path):
            messagebox.showerror("Warning", "The selected subtitle is no longer available.")
            self.clear_local_file("Subtitle")
            return
            
        invalid_markers = ("Loading", "Connecting", "Error")
        if (
            not deck or not model
            or any(marker in deck for marker in invalid_markers)
            or any(marker in model for marker in invalid_markers)
            or deck == "🔙 Back"
        ):
            messagebox.showerror(
                "Anki selection",
                "Choose a valid deck and note type before starting.",
                parent=self.root,
            )
            return

        self.open_field_preview(url, deck, model)

    def open_field_preview(self, url, deck, model):
        """Loads note fields without blocking Tk's event loop."""
        self.start_btn.configure(
            state="disabled", image=self.img_wait, text="LOADING FIELDS...",
        )
        self.status_var.set("Status: Loading note fields from Anki...")
        self._set_indeterminate_progress()
        threading.Thread(
            target=self._fetch_field_preview_data,
            args=(url, deck, model),
            daemon=True,
        ).start()

    def _fetch_field_preview_data(self, url, deck, model):
        fields = invoke_anki('modelFieldNames', modelName=model)
        self._safe_after(
            lambda: self._finish_field_preview_load(
                url, deck, model, fields,
            )
        )

    def _finish_field_preview_load(self, url, deck, model, fields):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.start_btn.configure(
            state="normal", image=self.img_play, text="START",
        )

        if not fields:
            self.status_var.set("Status: Could not load note fields")
            messagebox.showerror(
                "Deck Fields",
                f"Could not get fields for note type '{model}'.",
                parent=self.root,
            )
            return
        self.status_var.set("Status: Ready")
        self._show_field_preview(url, deck, model, fields)

    def _show_field_preview(self, url, deck, model, fields):
        """Shows and allows editing the destination of each data."""
        if hasattr(self, "field_preview_window") and self.field_preview_window.winfo_exists():
            self.field_preview_window.destroy()

        window = ctk.CTkToplevel(self.root)
        self.field_preview_window = window
        window.title("Field Preview")
        self._center_window(window, 590, 620)
        window.minsize(560, 500)
        window.configure(fg_color="#fcfaf7")
        window.transient(self.root)
        window.grab_set()

        ctk.CTkLabel(
            window, text="FIELD PREVIEW", font=ctk.CTkFont(size=30, weight="bold"), text_color="#101544"
        ).pack(anchor="w", padx=24, pady=(30, 2))
        ctk.CTkLabel(
            window, text=f"MODEL: {model}\nCHOOSE THE CONTENT EACH FIELD WILL RECEIVE.",
            justify="left", text_color="#444444", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=24, pady=(0, 20))

        source_labels = {
            "Do not fill": None,
            "Scene audio (MP3)": "audio",
            "Video clip (WebM)": "clip",
            "Scene image (JPG)": "snapshot",
            "Original subtitle": "english_subtitle",
            "Translated subtitle": "portuguese_subtitle",
            "Card identifier": "index",
        }
        self.field_source_labels = source_labels

        saved = CONFIG.get('field_mappings', {}).get(model, {})
        valid_saved = {
            slot: field for slot, field in saved.items()
            if field in fields and slot in source_labels.values()
        }
        suggested = valid_saved or _map_fields_heuristic(fields)
        field_to_slot = {field: slot for slot, field in suggested.items() if field}
        slot_to_label = {slot: label for label, slot in source_labels.items()}

        list_frame = AutoHideScrollableFrame(
            window, fg_color="#e6e6f5", corner_radius=0,
            border_width=3, border_color="#000000",
            scrollbar_button_color="#101544",
            scrollbar_button_hover_color="#858dda",
        )
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 14))
        list_frame.grid_columnconfigure(0, minsize=170)
        list_frame.grid_columnconfigure(1, weight=1, minsize=300)
        self.field_mapping_vars = {}
        first_mapping_combo = None

        for row, field in enumerate(fields):
            ctk.CTkLabel(
                list_frame, text=field.upper(), anchor="w", justify="left",
                wraplength=160, font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#101544",
            ).grid(row=row, column=0, padx=(10, 14), pady=10, sticky="w")
            initial_label = slot_to_label.get(field_to_slot.get(field), "Do not fill")
            variable = ctk.StringVar(value=initial_label)
            self.field_mapping_vars[field] = variable
            combo_shadow = ctk.CTkFrame(list_frame, fg_color="#000000", corner_radius=0)
            combo_shadow.grid(row=row, column=1, padx=(0, 10), pady=10, sticky="ew")
            mapping_combo = ctk.CTkComboBox(
                combo_shadow, variable=variable, values=list(source_labels.keys()),
                state="readonly", height=39, fg_color="#fcfaf7", border_width=0,
                dropdown_fg_color="#fcfaf7", dropdown_text_color="#101544", text_color="#101544",
                font=ctk.CTkFont(size=13, weight="bold"), corner_radius=0, button_color="#FFFFFF", button_hover_color="#e6e6f5"
            )
            mapping_combo.pack(fill="x", expand=True, padx=(3, 7), pady=(3, 7))
            if first_mapping_combo is None:
                first_mapping_combo = mapping_combo

        ctk.CTkLabel(
            window,
            text="EACH CONTENT TYPE CAN BE ASSIGNED TO ONLY ONE FIELD.",
            text_color="#555555", font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(anchor="w", padx=24, pady=(0, 10))

        footer = ctk.CTkFrame(window, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 20))

        btn_back_shadow = ctk.CTkFrame(footer, fg_color="#000000", corner_radius=0)
        btn_back_shadow.pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            btn_back_shadow, text="BACK", width=100, height=45, fg_color="#6253cc", hover_color="#E60039",
            text_color="#101544", border_width=3, border_color="#000000", corner_radius=0, font=ctk.CTkFont(size=14, weight="bold"),
            command=window.destroy,
        ).pack(padx=(0, 4), pady=(0, 4))

        btn_confirm_shadow = ctk.CTkFrame(footer, fg_color="#000000", corner_radius=0)
        btn_confirm_shadow.pack(side="right")
        ctk.CTkButton(
            btn_confirm_shadow, text="CONFIRM AND START", width=200, height=45, fg_color="#858dda", hover_color="#1A4DE5",
            text_color="white", border_width=3, border_color="#000000", corner_radius=0, font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._confirm_field_preview(url, deck, model),
        ).pack(padx=(0, 4), pady=(0, 4))
        window.bind("<Escape>", lambda _event: window.destroy())
        window.bind(
            "<Control-Return>",
            lambda _event: self._confirm_field_preview(url, deck, model),
        )
        if first_mapping_combo is not None:
            window.after(120, first_mapping_combo.focus_set)

    def _confirm_field_preview(self, url, deck, model):
        field_mapping = {}
        for field, variable in self.field_mapping_vars.items():
            slot = self.field_source_labels[variable.get()]
            if slot is None:
                continue
            if slot in field_mapping:
                label = variable.get()
                messagebox.showerror(
                    "Deck Fields", f"'{label}' was assigned to more than one field.",
                    parent=self.field_preview_window,
                )
                return
            field_mapping[slot] = field

        if not field_mapping:
            messagebox.showerror(
                "Deck Fields", "Configure at least one field before starting.",
                parent=self.field_preview_window,
            )
            return

        CONFIG['anki']['deck_name'] = deck
        CONFIG['anki']['model_name'] = model
        CONFIG.setdefault('field_mappings', {})[model] = field_mapping
        save_config(CONFIG)
        self.field_preview_window.destroy()
        self._begin_processing(url, field_mapping)

    def _begin_processing(self, url, field_mapping):
        self._processing = True
        self.start_btn.configure(
            state="disabled", image=self.img_wait, text="WORKING...",
        )
        self.settings_btn.configure(state="disabled")
        self.url_entry.configure(state="disabled")
        self.deck_cb.configure(state="disabled")
        self.model_cb.configure(state="disabled")
        self._set_local_controls_state("disabled")
        
        self.status_var.set("Status: Initializing Pipeline...")
        self._update_stepper(0)
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start() # Starts bar animation
        
        self._clear_log()
        print(f"URL: {url}\n")
        
        threading.Thread(
            target=self._run_pipeline_thread,
            args=(url, self.local_video_path, self.local_srt_path, field_mapping),
            daemon=True,
        ).start()

    def _clear_log(self):
        previous_state = self.log_text.cget("state")
        if previous_state == "disabled":
            self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        if previous_state == "disabled":
            self.log_text.configure(state="disabled")
        
    def _run_pipeline_thread(self, url, local_video=None, local_srt=None, field_mapping=None):
        work_dir = None
        try:
            success, work_dir = run_pipeline(
                url, local_video=local_video, local_srt_en=local_srt,
                field_mapping=field_mapping,
            )
            self._safe_after(
                lambda s=success, w=work_dir: self._handle_completion(s, w)
            )
        except Exception as e:
            import traceback
            err_detail = traceback.format_exc()
            print(f"\nCRITICAL ERROR: {e}")
            print(err_detail)
            self._safe_after(
                lambda: self.status_var.set("Status: Critical Error!")
            )
            # Clean workspace if exists
            if work_dir and os.path.exists(work_dir):
                try:
                    shutil.rmtree(work_dir)
                except Exception:
                    pass
            self._safe_after(self._unlock_ui)
            
    def _handle_completion(self, success, work_dir):
        if success:
            self.status_var.set("Status: Finished Successfully!")
            print("\nFINISHED.")
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass
            self._unlock_ui()
            self._show_completion_dialog(work_dir)
        else:
            self.status_var.set("Status: Failed!")
            print("\nFAILED.")
            print("\nCleaning temporary files (failed)...")
            try:
                if work_dir and os.path.isdir(work_dir):
                    shutil.rmtree(work_dir)
            except Exception:
                pass
            self._unlock_ui()

    def _show_completion_dialog(self, work_dir):
        window = ctk.CTkToplevel(self.root)
        window.title("Process Complete")
        self._center_window(window, 520, 320)
        window.resizable(False, False)
        window.configure(fg_color="#fcfaf7")
        window.transient(self.root)
        window.grab_set()

        ctk.CTkLabel(
            window, text="PROCESS COMPLETE",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#101544",
        ).pack(anchor="w", padx=24, pady=(22, 2))
        ctk.CTkLabel(
            window, text="THE CARDS WERE ADDED TO ANKI.",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#444444",
        ).pack(anchor="w", padx=24, pady=(0, 14))

        panel = ctk.CTkFrame(
            window, fg_color="#e6e6f5", corner_radius=0,
            border_width=3, border_color="#000000",
        )
        panel.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        ctk.CTkLabel(
            panel,
            text=(
                "TEMPORARY FILES\n"
                "Choose whether to keep the downloaded video, subtitles, "
                "and generated media."
            ),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#101544", justify="left", anchor="w",
            wraplength=440,
        ).pack(fill="x", padx=16, pady=(14, 8))
        path_label = ctk.CTkLabel(
            panel, text=os.path.abspath(work_dir) if work_dir else "No workspace",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#555555", justify="left", anchor="w",
            wraplength=440,
        )
        path_label.pack(fill="x", padx=16, pady=(0, 12))

        footer = ctk.CTkFrame(window, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 18))

        def add_action(text, width, color, text_color, command):
            shadow = ctk.CTkFrame(footer, fg_color="#000000", corner_radius=0)
            shadow.pack(side="left", padx=(0, 10))
            button = ctk.CTkButton(
                shadow, text=text, width=width, height=44,
                fg_color=color, hover_color="#e6e6f5",
                text_color=text_color, corner_radius=0,
                border_width=3, border_color="#000000",
                font=ctk.CTkFont(size=12, weight="bold"),
                command=command,
            )
            button.pack(padx=(0, 4), pady=(0, 4))
            return button

        workspace_exists = bool(work_dir and os.path.isdir(work_dir))
        delete_button = add_action(
            "DELETE FILES", 135, "#6253cc", "#101544",
            lambda: self._complete_workspace_action(
                window, work_dir, "delete",
            ),
        )
        open_button = add_action(
            "OPEN FOLDER", 125, "#858dda", "#FFFFFF",
            lambda: self._complete_workspace_action(
                window, work_dir, "open",
            ),
        )
        keep_button = add_action(
            "KEEP FILES", 120, "#858dda", "#101544",
            lambda: self._complete_workspace_action(
                window, work_dir, "keep",
            ),
        )
        if not workspace_exists:
            delete_button.configure(state="disabled")
            open_button.configure(state="disabled")
        window.protocol(
            "WM_DELETE_WINDOW",
            lambda: self._complete_workspace_action(
                window, work_dir, "keep",
            ),
        )
        window.bind(
            "<Escape>",
            lambda _event: self._complete_workspace_action(
                window, work_dir, "keep",
            ),
        )
        window.after(120, keep_button.focus_set)

    def _complete_workspace_action(self, window, work_dir, action):
        if action == "delete":
            if not messagebox.askyesno(
                "Delete temporary files?",
                "Permanently delete the temporary workspace?",
                icon="warning", parent=window,
            ):
                return
            try:
                if work_dir and os.path.isdir(work_dir):
                    shutil.rmtree(work_dir)
                print("\nTemporary folder deleted.")
            except Exception as error:
                messagebox.showerror(
                    "Temporary files",
                    f"Could not delete the workspace:\n{error}",
                    parent=window,
                )
                return
        elif action == "open":
            try:
                os.startfile(os.path.abspath(work_dir))
                print(f"\nKeeping temporary folder: {work_dir}")
            except Exception as error:
                messagebox.showerror(
                    "Temporary files",
                    f"Could not open the workspace:\n{error}",
                    parent=window,
                )
                return
        else:
            print(f"\nKeeping temporary folder: {work_dir}")

        window.destroy()
            
    def _unlock_ui(self):
        self._processing = False
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.start_btn.configure(
            state="normal", image=self.img_play, text="START",
        )
        self.settings_btn.configure(state="normal")
        self.url_entry.configure(
            state="disabled" if self.local_video_path else "normal",
        )
        self.deck_cb.configure(state="readonly")
        self.model_cb.configure(state="readonly")
        self._set_local_controls_state("normal")

    def _set_local_controls_state(self, state):
        def update_descendants(widget):
            for child in widget.winfo_children():
                if isinstance(child, ctk.CTkButton):
                    child.configure(state=state)
                update_descendants(child)

        update_descendants(self.local_files_frame)

def launch_gui():
    root = ctk.CTk()
    
    import os
    import sys
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        
    icon_path = os.path.join(base_path, "assets", "icon.ico")
    if os.path.exists(icon_path):
        try:
            root.iconbitmap(icon_path)
        except Exception:
            pass

    app = CardBunnyApp(root)
    root.mainloop()
