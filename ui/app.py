import customtkinter as ctk
from tkinter import messagebox, filedialog
import os
import sys
import threading
import shutil
import glob
import re
import winsound
from ui.icons import create_link_icon, create_deck_icon, create_model_icon, create_play_icon, create_wait_icon, create_settings_icon
from ui.redirector import StdoutRedirector
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
        self.root.geometry("450x720")
        self.root.minsize(450, 680)

        # Set window icon
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

        # Dark Cinematic Background
        self.root.configure(fg_color="#FFFFFF")

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        # Initialize Icons
        self.img_link = ctk.CTkImage(light_image=create_link_icon(color="#111111"), dark_image=create_link_icon(color="#111111"), size=(24, 24))
        self.img_deck = ctk.CTkImage(light_image=create_deck_icon(color="white"), dark_image=create_deck_icon(color="white"), size=(24, 24))
        self.img_model = ctk.CTkImage(light_image=create_model_icon(color="white"), dark_image=create_model_icon(color="white"), size=(24, 24))
        self.img_play = ctk.CTkImage(light_image=create_play_icon(color="#111111"), dark_image=create_play_icon(color="#111111"), size=(36, 36))
        self.img_wait = ctk.CTkImage(light_image=create_wait_icon(color="#111111"), dark_image=create_wait_icon(color="#111111"), size=(36, 36))
        self.img_settings = ctk.CTkImage(light_image=create_settings_icon(color="#111111"), dark_image=create_settings_icon(color="#111111"), size=(18, 18))

        # Branding
        self.brand_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.brand_frame.grid(row=0, column=0, sticky="ew", padx=30, pady=(30, 20))

        self.app_title_label = ctk.CTkLabel(
            self.brand_frame, text="CARD\nBUNNY",
            font=ctk.CTkFont(family="Arial", size=26, weight="bold"), 
            text_color="#111111", justify="left"
        )
        self.app_title_label.pack(side="left")

        # Settings Button
        self.settings_btn = ctk.CTkButton(
            self.brand_frame, text="", image=self.img_settings, width=42, height=42,
            corner_radius=0, fg_color="#FFFFFF", hover_color="#F4F4F0",
            border_width=3, border_color="#000000",
            command=self.open_settings,
        )
        self.settings_btn.pack(side="right", anchor="n")

        self.main_frame = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=1, column=0, padx=30, pady=10, sticky="nsew")
        
        # URL
        self.url_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.url_frame.pack(fill="x", pady=(0, 20))
        
        self.url_icon_bg = ctk.CTkFrame(self.url_frame, width=42, height=42, fg_color="#FFD13B", border_width=3, border_color="#000000", corner_radius=0)
        self.url_icon_bg.pack(side="left", padx=(0, 15))
        self.url_icon_bg.pack_propagate(False)
        self.url_icon_label = ctk.CTkLabel(self.url_icon_bg, text="", image=self.img_link)
        self.url_icon_label.pack(expand=True)
        
        self.url_var = ctk.StringVar()
        self.url_entry = ctk.CTkEntry(
            self.url_frame, textvariable=self.url_var, height=42, font=ctk.CTkFont(size=14, weight="bold"), 
            placeholder_text="PASTE YOUTUBE LINK...", placeholder_text_color="#555555",
            corner_radius=0, fg_color="#FFFFFF", border_width=3, border_color="#000000", text_color="#111111"
        )
        self.url_entry.pack(side="left", fill="x", expand=True)
        self.url_var.trace_add("write", self._on_url_changed)

        # Local files optional. Keeps URL as default flow.
        self.local_video_path = None
        self.local_srt_path = None
        self.local_files_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.local_files_frame.pack(fill="x", pady=0)

        self.local_video_label = self._create_local_file_row(
            self.local_files_frame, "Video", self.select_local_video, "#3366FF"
        )
        self.local_srt_label = self._create_local_file_row(
            self.local_files_frame, "Subtitle", self.select_local_subtitle, "#3366FF"
        )
        
        # Deck
        self.deck_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.deck_frame.pack(fill="x", pady=(0, 20))
        
        self.deck_icon_bg = ctk.CTkFrame(self.deck_frame, width=42, height=42, fg_color="#FF3366", border_width=3, border_color="#000000", corner_radius=0)
        self.deck_icon_bg.pack(side="left", padx=(0, 15))
        self.deck_icon_bg.pack_propagate(False)
        self.deck_icon_label = ctk.CTkLabel(self.deck_icon_bg, text="", image=self.img_deck)
        self.deck_icon_label.pack(expand=True)
        
        self.deck_cb = ctk.CTkComboBox(
            self.deck_frame, height=42, font=ctk.CTkFont(size=14, weight="bold"), values=["Loading..."], state="readonly", 
            corner_radius=0, fg_color="#FFFFFF", border_width=3, border_color="#000000", text_color="#111111",
            button_color="#FFFFFF", button_hover_color="#EAEAEA", dropdown_fg_color="#FFFFFF", dropdown_text_color="#111111"
        )
        self.deck_cb.pack(side="left", fill="x", expand=True)
        
        # Model
        self.model_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.model_frame.pack(fill="x", pady=(0, 25))
        
        self.model_icon_bg = ctk.CTkFrame(self.model_frame, width=42, height=42, fg_color="#FF3366", border_width=3, border_color="#000000", corner_radius=0)
        self.model_icon_bg.pack(side="left", padx=(0, 15))
        self.model_icon_bg.pack_propagate(False)
        self.model_icon_label = ctk.CTkLabel(self.model_icon_bg, text="", image=self.img_model)
        self.model_icon_label.pack(expand=True)
        
        self.model_cb = ctk.CTkComboBox(
            self.model_frame, height=42, font=ctk.CTkFont(size=14, weight="bold"), values=["Loading..."], state="readonly", 
            corner_radius=0, fg_color="#FFFFFF", border_width=3, border_color="#000000", text_color="#111111",
            button_color="#FFFFFF", button_hover_color="#EAEAEA", dropdown_fg_color="#FFFFFF", dropdown_text_color="#111111"
        )
        self.model_cb.pack(side="left", fill="x", expand=True)
        
        # Status Label & ProgressBar
        self.status_var = ctk.StringVar(value="STATUS: IDLE")
        self.status_label = ctk.CTkLabel(
            self.main_frame, textvariable=self.status_var,
            font=ctk.CTkFont(size=13, weight="bold"), text_color="#111111",
            justify="left", wraplength=390,
        )
        self.status_label.pack(anchor="w", pady=(0, 8))
        
        self.progress_frame = ctk.CTkFrame(self.main_frame, height=12, fg_color="#FFFFFF", border_width=3, border_color="#000000", corner_radius=0)
        self.progress_frame.pack(fill="x", pady=(0, 25))
        self.progress_frame.pack_propagate(False)
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, mode="indeterminate", height=12, corner_radius=0, fg_color="#FFFFFF", progress_color="#3366FF")
        self.progress_bar.pack(fill="both", expand=True)
        self.progress_bar.set(0)
        
        # Stepper (Visual Step Indicator)
        self.stepper_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.stepper_frame.pack(fill="x", pady=(0, 25))
        
        self.stepper_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        self.step_1 = ctk.CTkButton(self.stepper_frame, text="1. DOWN", font=ctk.CTkFont(size=11, weight="bold"), height=35, fg_color="#FFFFFF", text_color="#111111", text_color_disabled="#777777", state="disabled", corner_radius=0, border_width=3, border_color="#000000")
        self.step_1.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        
        self.step_2 = ctk.CTkButton(self.stepper_frame, text="2. AI", font=ctk.CTkFont(size=11, weight="bold"), height=35, fg_color="#FFFFFF", text_color="#111111", text_color_disabled="#777777", state="disabled", corner_radius=0, border_width=3, border_color="#000000")
        self.step_2.grid(row=0, column=1, padx=5, sticky="ew")
        
        self.step_3 = ctk.CTkButton(self.stepper_frame, text="3. MEDIA", font=ctk.CTkFont(size=11, weight="bold"), height=35, fg_color="#FFFFFF", text_color="#111111", text_color_disabled="#777777", state="disabled", corner_radius=0, border_width=3, border_color="#000000")
        self.step_3.grid(row=0, column=2, padx=5, sticky="ew")
        
        self.step_4 = ctk.CTkButton(self.stepper_frame, text="4. ANKI", font=ctk.CTkFont(size=11, weight="bold"), height=35, fg_color="#FFFFFF", text_color="#111111", text_color_disabled="#777777", state="disabled", corner_radius=0, border_width=3, border_color="#000000")
        self.step_4.grid(row=0, column=3, padx=(5, 0), sticky="ew")
        
        # Play Button
        self.start_btn = ctk.CTkButton(
            self.main_frame, text="", image=self.img_play, height=70, corner_radius=0, 
            hover_color="#E5BC35", fg_color="#FFD13B", border_width=4, border_color="#000000", command=self.start_processing
        )
        self.start_btn.pack(fill="x", pady=(0, 25))
        
        # Log Box
        self.log_text = ctk.CTkTextbox(
            self.main_frame, height=150, font=ctk.CTkFont(family="Consolas", size=12, weight="bold"), 
            fg_color="#F8F8F8", text_color="#444444", corner_radius=0, border_color="#000000", border_width=3
        )
        self.log_text.pack(fill="both", expand=True)
        
        self.redirector = StdoutRedirector(self.log_text, self._log_sniffer)
        sys.stdout = self.redirector
        sys.stderr = self.redirector
        
        self._cleanup_zombie_workspaces()
        self.root.after(200, self.load_anki_data)



    def _create_local_file_row(self, parent, label, command, bg_color):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 20))
        
        icon_bg = ctk.CTkFrame(row, width=42, height=42, fg_color=bg_color, border_width=3, border_color="#000000", corner_radius=0)
        icon_bg.pack(side="left", padx=(0, 15))
        icon_bg.pack_propagate(False)
        ctk.CTkLabel(icon_bg, text="📄", font=ctk.CTkFont(size=18), text_color="white").pack(expand=True)

        inner_frame = ctk.CTkFrame(row, fg_color="#FFFFFF", height=42, border_width=3, border_color="#000000", corner_radius=0)
        inner_frame.pack(side="left", fill="x", expand=True)
        inner_frame.pack_propagate(False)
        
        btn_text = f"Select {label.title()}"
        ctk.CTkButton(
            inner_frame, text=btn_text, width=100, height=30, fg_color="#3366FF",
            hover_color="#1A4DE5", text_color="white", command=command, corner_radius=0,
            font=ctk.CTkFont(size=11, weight="bold"), border_width=2, border_color="#000000"
        ).pack(side="left", padx=5, pady=5)
        
        value_label = ctk.CTkLabel(
            inner_frame, text="NOT SELECTED", anchor="w", text_color="#555555",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        value_label.pack(side="left", fill="x", expand=True, padx=(10, 0))
        
        ctk.CTkButton(
            inner_frame, text="×", width=30, height=30, fg_color="#FF3366",
            hover_color="#E60039", text_color="white", font=ctk.CTkFont(size=16, weight="bold"),
            command=lambda kind=label: self.clear_local_file(kind), corner_radius=0,
            border_width=2, border_color="#000000"
        ).pack(side="right", padx=5, pady=5)
        return value_label

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
            self.local_video_label.configure(text=os.path.basename(path), text_color="#111111")
            self.url_entry.configure(placeholder_text="URL bypassed: using local video")

    def select_local_subtitle(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="Select original subtitle",
            filetypes=[("SubRip Subtitle", "*.srt")],
        )
        if path:
            self.local_srt_path = os.path.abspath(path)
            self.local_srt_label.configure(text=os.path.basename(path), text_color="#111111")

    def clear_local_file(self, kind):
        if kind == "Video":
            self.local_video_path = None
            self.local_video_label.configure(text="NOT SELECTED", text_color="#555555")
            self.url_entry.configure(placeholder_text="Paste YouTube link...")
        else:
            self.local_srt_path = None
            self.local_srt_label.configure(text="NOT SELECTED", text_color="#555555")

    def open_settings(self):
        """Opens a single window for Anki and local AI integrations."""
        if hasattr(self, "settings_window") and self.settings_window.winfo_exists():
            self.settings_window.focus()
            return

        window = ctk.CTkToplevel(self.root)
        self.settings_window = window
        window.title("Settings")
        window.geometry("500x590")
        window.resizable(False, False)
        window.configure(fg_color="#FFFFFF")
        window.transient(self.root)
        window.grab_set()
        
        if os.path.exists(resource_path("icon.ico")):
            window.iconbitmap(resource_path("icon.ico"))
            


        title = ctk.CTkLabel(window, text="SETTINGS", font=ctk.CTkFont(size=30, weight="bold"), text_color="#111111")
        title.pack(anchor="w", padx=24, pady=(10, 2))
        subtitle = ctk.CTkLabel(window, text="INTEGRATIONS USED IN PROCESSING", text_color="#444444", font=ctk.CTkFont(size=14, weight="bold"))
        subtitle.pack(anchor="w", padx=24, pady=(0, 16))

        tabs = ctk.CTkTabview(window, fg_color="#F4F4F0", segmented_button_selected_color="#111111",
                              segmented_button_selected_hover_color="#222222",
                              segmented_button_unselected_color="#FFFFFF",
                              segmented_button_unselected_hover_color="#EAEAEA",
                              text_color="#111111", border_width=3, border_color="#000000", corner_radius=0)
        tabs.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        anki_tab = tabs.add("Anki")
        ai_tab = tabs.add("Local AI")
        lang_tab = tabs.add("Languages")

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

        self._settings_entry(anki_tab, "AnkiConnect Address", "anki_url")
        self._settings_entry(anki_tab, "Default Deck", "deck_name")
        self._settings_entry(anki_tab, "Default Note Type", "model_name")
        hint = ctk.CTkLabel(anki_tab, text="Anki must be open with AnkiConnect active.",
                            text_color="#444444", font=ctk.CTkFont(size=12, weight="bold"), wraplength=400, justify="left")
        hint.pack(anchor="w", padx=14, pady=(8, 0))

        self._settings_entry(ai_tab, "OpenAI compatible endpoint", "base_url")
        self._settings_entry(ai_tab, "Translation model", "ai_model")
        self._settings_entry(ai_tab, "API Key", "api_key", show="•")
        self._settings_combo(
            ai_tab,
            "Whisper Model",
            "whisper_model",
            ["small.en", "medium.en", "tiny.en", "base.en", "small", "medium", "large-v3", "turbo"],
        )

        ai_row = ctk.CTkFrame(ai_tab, fg_color="transparent")
        ai_row.pack(fill="x", padx=14, pady=(8, 0))
        self._settings_combo(ai_row, "Device", "device", ["cpu", "cuda"], side="left")
        self._settings_combo(ai_row, "Precision", "compute_type", ["int8", "float16", "float32"], side="left")
        self._settings_entry(ai_row, "Threads", "cpu_threads", width=90, side="left")

        # Languages Tab
        self._settings_combo(
            lang_tab, 
            "Video Language (Whisper)", 
            "whisper_language", 
            ["en", "pt", "es", "fr", "de", "it", "ja", "ko", "zh", "ru"]
        )
        self._settings_combo(
            lang_tab, 
            "Target Language (Translation)", 
            "translation_target", 
            ["Brazilian Portuguese (pt-BR)", "English", "Spanish", "French", "German", "Japanese", "Portuguese (pt-PT)"]
        )
        hint_lang = ctk.CTkLabel(
            lang_tab, text="You can manually type another language if you wish.",
            text_color="#444444", font=ctk.CTkFont(size=12, weight="bold"), wraplength=400, justify="left"
        )
        hint_lang.pack(anchor="w", padx=14, pady=(8, 0))

        footer = ctk.CTkFrame(window, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 20))

        btn_import_shadow = ctk.CTkFrame(footer, fg_color="#000000", corner_radius=0)
        btn_import_shadow.pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_import_shadow, text="IMPORT", width=80, height=45, fg_color="#FFFFFF", hover_color="#F4F4F0",
                      text_color="#111111", border_width=3, border_color="#000000", corner_radius=0,
                      font=ctk.CTkFont(size=14, weight="bold"), command=self.import_settings).pack(padx=(0, 4), pady=(0, 4))

        btn_export_shadow = ctk.CTkFrame(footer, fg_color="#000000", corner_radius=0)
        btn_export_shadow.pack(side="left")
        ctk.CTkButton(btn_export_shadow, text="EXPORT", width=80, height=45, fg_color="#FFFFFF", hover_color="#F4F4F0",
                      text_color="#111111", border_width=3, border_color="#000000", corner_radius=0,
                      font=ctk.CTkFont(size=14, weight="bold"), command=self.export_settings).pack(padx=(0, 4), pady=(0, 4))

        btn_cancel_shadow = ctk.CTkFrame(footer, fg_color="#000000", corner_radius=0)
        btn_cancel_shadow.pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_cancel_shadow, text="CANCEL", width=120, height=45, fg_color="#FF3366", hover_color="#E60039",
                      text_color="white", border_width=3, border_color="#000000", corner_radius=0,
                      font=ctk.CTkFont(size=14, weight="bold"), command=window.destroy).pack(padx=(0, 4), pady=(0, 4))

        btn_save_shadow = ctk.CTkFrame(footer, fg_color="#000000", corner_radius=0)
        btn_save_shadow.pack(side="right")
        ctk.CTkButton(btn_save_shadow, text="SAVE", width=140, height=45, fg_color="#3366FF", hover_color="#1A4DE5",
                      text_color="white", border_width=3, border_color="#000000", corner_radius=0,
                      font=ctk.CTkFont(size=14, weight="bold"), command=self.save_settings).pack(padx=(0, 4), pady=(0, 4))

    def _settings_entry(self, parent, label, key, show=None, width=None, side=None):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x" if side is None else None, padx=14 if side is None else 4,
                   pady=(10, 0), side=side)
        ctk.CTkLabel(frame, text=label.upper(), text_color="#111111", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")

        shadow_frame = ctk.CTkFrame(frame, fg_color="#000000", corner_radius=0)
        shadow_frame.pack(fill="x" if width is None else None, pady=(3, 0))

        entry_options = {
            "textvariable": self.settings_vars[key], "height": 45,
            "fg_color": "#FFFFFF", "border_width": 3, "border_color": "#000000",
            "corner_radius": 0, "text_color": "#111111", "font": ctk.CTkFont(size=14, weight="bold")
        }
        if show is not None:
            entry_options["show"] = show
        if width is not None:
            entry_options["width"] = width
        entry = ctk.CTkEntry(shadow_frame, **entry_options)
        entry.pack(fill="x" if width is None else None, expand=True, padx=(0, 4), pady=(0, 4))
        return entry

    def _settings_combo(self, parent, label, key, values, side=None):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x" if side is None else None, padx=14 if side is None else 4,
                   pady=(10, 0), side=side)
        ctk.CTkLabel(frame, text=label.upper(), text_color="#111111", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")

        shadow_frame = ctk.CTkFrame(frame, fg_color="#000000", corner_radius=0)
        shadow_frame.pack(fill="x" if side is None else None, pady=(3, 0))

        combo = ctk.CTkComboBox(shadow_frame, variable=self.settings_vars[key], values=values, height=45,
                                width=112 if side else 200, fg_color="#FFFFFF", border_width=3,
                                border_color="#000000", corner_radius=0, text_color="#111111",
                                font=ctk.CTkFont(size=14, weight="bold"),
                                button_color="#FFFFFF", button_hover_color="#EAEAEA",
                                dropdown_fg_color="#FFFFFF", dropdown_text_color="#111111")
        combo.pack(fill="x" if side is None else None, expand=True, padx=(0, 4), pady=(0, 4))
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
            btn.configure(fg_color="#FFFFFF", text_color_disabled="#777777")
            
        # Light up the current one
        if 1 <= step_number <= 4:
            steps[step_number - 1].configure(fg_color="#FF3366", text_color_disabled="white")
        
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
        decks = invoke_anki('deckNames')
        models = invoke_anki('modelNames')
        
        if decks is None or models is None:
            self.status_var.set("Critical Error: Anki Offline!")
            print("Critical Error: Anki not found.")
            self.start_btn.configure(state="disabled")
            self.deck_cb.configure(values=["Connection Error"])
            self.model_cb.configure(values=["Connection Error"])
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
            
        if "Loading" in deck or "Error" in deck or deck == "🔙 Back":
            return

        self.open_field_preview(url, deck, model)

    def open_field_preview(self, url, deck, model):
        """Shows and allows editing the destination of each data before the pipeline."""
        fields = invoke_anki('modelFieldNames', modelName=model)
        if not fields:
            messagebox.showerror("Deck Fields", f"Could not get fields for model '{model}'.")
            return

        if hasattr(self, "field_preview_window") and self.field_preview_window.winfo_exists():
            self.field_preview_window.destroy()

        window = ctk.CTkToplevel(self.root)
        self.field_preview_window = window
        window.title("Field Preview")
        window.geometry("590x620")
        window.minsize(520, 500)
        window.configure(fg_color="#FFFFFF")
        window.transient(self.root)
        window.grab_set()

        ctk.CTkLabel(
            window, text="FIELD PREVIEW", font=ctk.CTkFont(size=30, weight="bold"), text_color="#111111"
        ).pack(anchor="w", padx=24, pady=(30, 2))
        ctk.CTkLabel(
            window, text=f"MODEL: {model}\nCHOOSE THE CONTENT EACH FIELD WILL RECEIVE.",
            justify="left", text_color="#444444", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=24, pady=(0, 20))

        source_labels = {
            "Do not fill": None,
            "Scene audio (MP3)": "audio",
            "Video clip (MP4)": "clip",
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

        list_frame = ctk.CTkScrollableFrame(window, fg_color="#F4F4F0", corner_radius=0, border_width=3, border_color="#000000")
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 14))
        list_frame.grid_columnconfigure(1, weight=1)
        self.field_mapping_vars = {}

        for row, field in enumerate(fields):
            ctk.CTkLabel(
                list_frame, text=field.upper(), anchor="w", font=ctk.CTkFont(size=13, weight="bold"), text_color="#111111"
            ).grid(row=row, column=0, padx=(10, 14), pady=10, sticky="w")
            initial_label = slot_to_label.get(field_to_slot.get(field), "Do not fill")
            variable = ctk.StringVar(value=initial_label)
            self.field_mapping_vars[field] = variable
            combo_shadow = ctk.CTkFrame(list_frame, fg_color="#000000", corner_radius=0)
            combo_shadow.grid(row=row, column=1, padx=(0, 10), pady=10, sticky="ew")
            ctk.CTkComboBox(
                combo_shadow, variable=variable, values=list(source_labels.keys()),
                state="readonly", height=45, fg_color="#FFFFFF", border_width=3, border_color="#000000",
                dropdown_fg_color="#FFFFFF", dropdown_text_color="#111111", text_color="#111111",
                font=ctk.CTkFont(size=13, weight="bold"), corner_radius=0, button_color="#FFFFFF", button_hover_color="#EAEAEA"
            ).pack(fill="x", expand=True, padx=(0, 4), pady=(0, 4))

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
            btn_back_shadow, text="BACK", width=100, height=45, fg_color="#FF3366", hover_color="#E60039",
            text_color="white", border_width=3, border_color="#000000", corner_radius=0, font=ctk.CTkFont(size=14, weight="bold"),
            command=window.destroy,
        ).pack(padx=(0, 4), pady=(0, 4))

        btn_confirm_shadow = ctk.CTkFrame(footer, fg_color="#000000", corner_radius=0)
        btn_confirm_shadow.pack(side="right")
        ctk.CTkButton(
            btn_confirm_shadow, text="CONFIRM AND START", width=200, height=45, fg_color="#3366FF", hover_color="#1A4DE5",
            text_color="white", border_width=3, border_color="#000000", corner_radius=0, font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._confirm_field_preview(url, deck, model),
        ).pack(padx=(0, 4), pady=(0, 4))

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
        self.start_btn.configure(state="disabled", image=self.img_wait)
        self.url_entry.configure(state="disabled")
        self.deck_cb.configure(state="disabled")
        self.model_cb.configure(state="disabled")
        self._set_local_controls_state("disabled")
        
        self.status_var.set("Status: Initializing Pipeline...")
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start() # Starts bar animation
        
        self.log_text.delete("0.0", "end")
        print(f"URL: {url}\n")
        
        threading.Thread(
            target=self._run_pipeline_thread,
            args=(url, self.local_video_path, self.local_srt_path, field_mapping),
            daemon=True,
        ).start()
        
    def _run_pipeline_thread(self, url, local_video=None, local_srt=None, field_mapping=None):
        work_dir = None
        try:
            success, work_dir = run_pipeline(
                url, local_video=local_video, local_srt_en=local_srt,
                field_mapping=field_mapping,
            )
            self.root.after(0, lambda s=success, w=work_dir: self._handle_completion(s, w))
        except Exception as e:
            import traceback
            err_detail = traceback.format_exc()
            print(f"\nCRITICAL ERROR: {e}")
            print(err_detail)
            self.root.after(0, lambda: self.status_var.set("Status: Critical Error!"))
            # Clean workspace if exists
            if work_dir and os.path.exists(work_dir):
                try:
                    shutil.rmtree(work_dir)
                except Exception:
                    pass
            self.root.after(0, self._unlock_ui)
            
    def _handle_completion(self, success, work_dir):
        if success:
            self.status_var.set("Status: Finished Successfully!")
            print("\nFINISHED.")
            # Completion sound notification
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass
            
            # Ask the user what to do with temporaries
            result = messagebox.askyesnocancel(
                "Process Completed", 
                "The process finished successfully!\n\n"
                "Temporary files (downloaded videos and subtitles) take up disk space.\n\n"
                "• [Yes] - Delete temporary folder now (Recommended)\n"
                "• [No] - Keep files and open folder to view\n"
                "• [Cancel] - Just keep files"
            )
            
            if result is True:
                print("\nCleaning temporary files...")
                try:
                    shutil.rmtree(work_dir)
                    print("Folder deleted.")
                except Exception as e:
                    print(f"Warning: Could not delete {work_dir}. Error: {e}")
            elif result is False:
                print(f"\nKeeping temporary folder: {work_dir}")
                # Open folder in Windows
                os.startfile(os.path.abspath(work_dir))
            else:
                print(f"\nKeeping temporary folder: {work_dir}")
                
        else:
            self.status_var.set("Status: Failed!")
            print("\nFAILED.")
            print("\nCleaning temporary files (failed)...")
            try:
                shutil.rmtree(work_dir)
            except:
                pass
                
        self._unlock_ui()
            
    def _unlock_ui(self):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.set(0)
        self.start_btn.configure(state="normal", image=self.img_play)
        self.url_entry.configure(state="normal")
        self.deck_cb.configure(state="readonly")
        self.model_cb.configure(state="readonly")
        self._set_local_controls_state("normal")

    def _set_local_controls_state(self, state):
        for child in self.local_files_frame.winfo_children():
            if isinstance(child, ctk.CTkFrame):
                for widget in child.winfo_children():
                    if isinstance(widget, ctk.CTkButton):
                        widget.configure(state=state)

def launch_gui():
    root = ctk.CTk()
    
    import os
    import sys
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        
    icon_path = os.path.join(base_path, "icon.ico")
    if os.path.exists(icon_path):
        try:
            root.iconbitmap(icon_path)
        except Exception:
            pass

    app = CardBunnyApp(root)
    root.mainloop()
