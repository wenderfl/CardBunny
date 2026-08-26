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
from auto_anki.config import CONFIG, save_config
from auto_anki.anki_client import invoke_anki
from auto_anki.orchestrator import run_pipeline
from auto_anki.mapper import _map_fields_heuristic

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AutoAnkiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Auto Movies Anki")
        self.root.geometry("450x720")
        self.root.minsize(450, 680)
        
        # Fundo Cinematográfico Escuro
        self.root.configure(fg_color="#141414")
        
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        self.main_frame = ctk.CTkFrame(self.root, corner_radius=20, fg_color="transparent")
        self.main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        
        # Carregar CTkImages
        self.img_link = ctk.CTkImage(light_image=create_link_icon(color="#B3B3B3"), dark_image=create_link_icon(color="#B3B3B3"), size=(30, 30))
        self.img_deck = ctk.CTkImage(light_image=create_deck_icon(), dark_image=create_deck_icon(), size=(30, 30))
        self.img_model = ctk.CTkImage(light_image=create_model_icon(), dark_image=create_model_icon(), size=(30, 30))
        self.img_play = ctk.CTkImage(light_image=create_play_icon(), dark_image=create_play_icon(), size=(40, 40))
        self.img_wait = ctk.CTkImage(light_image=create_wait_icon(color="#B3B3B3"), dark_image=create_wait_icon(color="#B3B3B3"), size=(40, 40))
        self.img_settings = ctk.CTkImage(light_image=create_settings_icon(color="#A3A3A3"), dark_image=create_settings_icon(color="#A3A3A3"), size=(18, 18))

        # Acesso discreto às configurações
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent", height=28)
        self.header_frame.pack(fill="x", pady=(0, 2))
        self.settings_btn = ctk.CTkButton(
            self.header_frame, text="", image=self.img_settings, width=30, height=30,
            corner_radius=8, fg_color="transparent", hover_color="#2A2A2A",
            command=self.open_settings,
        )
        self.settings_btn.pack(side="right")
        
        # URL
        self.url_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.url_frame.pack(fill="x", pady=(0, 15))
        
        self.url_icon_label = ctk.CTkLabel(self.url_frame, text="", image=self.img_link)
        self.url_icon_label.pack(side="left", padx=(0, 10))
        
        self.url_var = ctk.StringVar()
        self.url_entry = ctk.CTkEntry(self.url_frame, textvariable=self.url_var, height=45, font=ctk.CTkFont(size=14), placeholder_text="Colar link do YouTube...", corner_radius=10, fg_color="#333333", border_width=0)
        self.url_entry.pack(side="left", fill="x", expand=True)
        # Limpar URL automaticamente quando o usuário colar
        self.url_var.trace_add("write", self._on_url_changed)

        # Arquivos locais opcionais. Mantêm a URL como fluxo padrão.
        self.local_video_path = None
        self.local_srt_path = None
        self.local_files_frame = ctk.CTkFrame(self.main_frame, fg_color="#202020", corner_radius=10)
        self.local_files_frame.pack(fill="x", pady=(0, 14))

        local_header = ctk.CTkLabel(
            self.local_files_frame, text="Arquivos locais (opcional)",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="gray75",
        )
        local_header.pack(anchor="w", padx=12, pady=(9, 4))

        self.local_video_label = self._create_local_file_row(
            self.local_files_frame, "Vídeo", self.select_local_video
        )
        self.local_srt_label = self._create_local_file_row(
            self.local_files_frame, "Legenda", self.select_local_subtitle
        )
        ctk.CTkLabel(
            self.local_files_frame,
            text="A legenda selecionada será traduzida pela IA local.",
            font=ctk.CTkFont(size=10), text_color="gray55",
        ).pack(anchor="w", padx=12, pady=(2, 8))
        
        # Deck
        self.deck_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.deck_frame.pack(fill="x", pady=(0, 10))
        
        self.deck_icon_label = ctk.CTkLabel(self.deck_frame, text="", image=self.img_deck)
        self.deck_icon_label.pack(side="left", padx=(0, 10))
        
        self.deck_cb = ctk.CTkComboBox(self.deck_frame, height=45, font=ctk.CTkFont(size=14), values=["Carregando..."], state="readonly", corner_radius=10, fg_color="#333333", border_width=0, button_color="#333333", button_hover_color="#555555", dropdown_fg_color="#333333")
        self.deck_cb.pack(side="left", fill="x", expand=True)
        
        # Model
        self.model_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.model_frame.pack(fill="x", pady=(0, 20))
        
        self.model_icon_label = ctk.CTkLabel(self.model_frame, text="", image=self.img_model)
        self.model_icon_label.pack(side="left", padx=(0, 10))
        
        self.model_cb = ctk.CTkComboBox(self.model_frame, height=45, font=ctk.CTkFont(size=14), values=["Carregando..."], state="readonly", corner_radius=10, fg_color="#333333", border_width=0, button_color="#333333", button_hover_color="#555555", dropdown_fg_color="#333333")
        self.model_cb.pack(side="left", fill="x", expand=True)
        
        # Status Label & ProgressBar
        self.status_var = ctk.StringVar(value="Status: Ocioso")
        self.status_label = ctk.CTkLabel(self.main_frame, textvariable=self.status_var, font=ctk.CTkFont(size=12, weight="bold"), text_color="gray70")
        self.status_label.pack(anchor="w", padx=10, pady=(0, 5))
        
        self.progress_bar = ctk.CTkProgressBar(self.main_frame, mode="indeterminate", height=6, progress_color="#E50914")
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 10))
        self.progress_bar.set(0)
        
        # Stepper (Indicador Visual de Etapas)
        self.stepper_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.stepper_frame.pack(fill="x", padx=10, pady=(0, 20))
        
        self.stepper_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        self.step_1 = ctk.CTkButton(self.stepper_frame, text="1. Down", font=ctk.CTkFont(size=10, weight="bold"), height=25, fg_color="#333333", text_color="gray70", state="disabled")
        self.step_1.grid(row=0, column=0, padx=2, sticky="ew")
        
        self.step_2 = ctk.CTkButton(self.stepper_frame, text="2. IA", font=ctk.CTkFont(size=10, weight="bold"), height=25, fg_color="#333333", text_color="gray70", state="disabled")
        self.step_2.grid(row=0, column=1, padx=2, sticky="ew")
        
        self.step_3 = ctk.CTkButton(self.stepper_frame, text="3. Mídia", font=ctk.CTkFont(size=10, weight="bold"), height=25, fg_color="#333333", text_color="gray70", state="disabled")
        self.step_3.grid(row=0, column=2, padx=2, sticky="ew")
        
        self.step_4 = ctk.CTkButton(self.stepper_frame, text="4. Anki", font=ctk.CTkFont(size=10, weight="bold"), height=25, fg_color="#333333", text_color="gray70", state="disabled")
        self.step_4.grid(row=0, column=3, padx=2, sticky="ew")
        
        # Botão Vermelho Netflix
        self.start_btn = ctk.CTkButton(self.main_frame, text="", image=self.img_play, height=70, corner_radius=20, hover_color="#B20710", fg_color="#E50914", command=self.start_processing)
        self.start_btn.pack(fill="x", pady=(0, 20))
        
        # Caixa Log
        self.log_text = ctk.CTkTextbox(self.main_frame, height=150, font=ctk.CTkFont(family="Consolas", size=11), fg_color="#000000", corner_radius=10, border_color="#333333", border_width=1)
        self.log_text.pack(fill="both", expand=True)
        
        self.redirector = StdoutRedirector(self.log_text, self._log_sniffer)
        sys.stdout = self.redirector
        sys.stderr = self.redirector
        
        self._cleanup_zombie_workspaces()
        self.root.after(200, self.load_anki_data)

    def _create_local_file_row(self, parent, label, command):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=2)
        ctk.CTkButton(
            row, text=f"{label}…", width=82, height=28, fg_color="#333333",
            hover_color="#444444", command=command,
        ).pack(side="left")
        value_label = ctk.CTkLabel(
            row, text="Não selecionado", anchor="w", text_color="gray55",
            font=ctk.CTkFont(size=11),
        )
        value_label.pack(side="left", fill="x", expand=True, padx=8)
        ctk.CTkButton(
            row, text="×", width=27, height=27, fg_color="transparent",
            hover_color="#3A3A3A", text_color="gray60",
            command=lambda kind=label: self.clear_local_file(kind),
        ).pack(side="right")
        return value_label

    def select_local_video(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="Selecionar vídeo",
            filetypes=[
                ("Arquivos de vídeo", "*.mp4 *.mkv *.webm *.avi *.mov *.m4v"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if path:
            self.local_video_path = os.path.abspath(path)
            self.local_video_label.configure(text=os.path.basename(path), text_color="gray80")
            self.url_entry.configure(placeholder_text="URL dispensada: usando vídeo local")

    def select_local_subtitle(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="Selecionar legenda original",
            filetypes=[("Legenda SubRip", "*.srt")],
        )
        if path:
            self.local_srt_path = os.path.abspath(path)
            self.local_srt_label.configure(text=os.path.basename(path), text_color="gray80")

    def clear_local_file(self, kind):
        if kind == "Vídeo":
            self.local_video_path = None
            self.local_video_label.configure(text="Não selecionado", text_color="gray55")
            self.url_entry.configure(placeholder_text="Colar link do YouTube...")
        else:
            self.local_srt_path = None
            self.local_srt_label.configure(text="Não selecionado", text_color="gray55")

    def open_settings(self):
        """Abre uma janela única para as integrações do Anki e da IA local."""
        if hasattr(self, "settings_window") and self.settings_window.winfo_exists():
            self.settings_window.focus()
            return

        window = ctk.CTkToplevel(self.root)
        self.settings_window = window
        window.title("Configurações")
        window.geometry("500x590")
        window.resizable(False, False)
        window.configure(fg_color="#141414")
        window.transient(self.root)
        window.grab_set()

        title = ctk.CTkLabel(window, text="Configurações", font=ctk.CTkFont(size=22, weight="bold"))
        title.pack(anchor="w", padx=24, pady=(22, 2))
        subtitle = ctk.CTkLabel(window, text="Integrações usadas no processamento", text_color="gray60")
        subtitle.pack(anchor="w", padx=24, pady=(0, 16))

        tabs = ctk.CTkTabview(window, fg_color="#202020", segmented_button_selected_color="#E50914",
                              segmented_button_selected_hover_color="#B20710")
        tabs.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        anki_tab = tabs.add("Anki")
        ai_tab = tabs.add("IA local")

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
        }

        self._settings_entry(anki_tab, "Endereço do AnkiConnect", "anki_url")
        self._settings_entry(anki_tab, "Baralho padrão", "deck_name")
        self._settings_entry(anki_tab, "Tipo de nota padrão", "model_name")
        hint = ctk.CTkLabel(anki_tab, text="O Anki precisa estar aberto com o AnkiConnect ativo.",
                            text_color="gray60", wraplength=400, justify="left")
        hint.pack(anchor="w", padx=14, pady=(8, 0))

        self._settings_entry(ai_tab, "Endpoint compatível com OpenAI", "base_url")
        self._settings_entry(ai_tab, "Modelo de tradução", "ai_model")
        self._settings_entry(ai_tab, "Chave da API", "api_key", show="•")
        self._settings_combo(ai_tab, "Modelo Whisper", "whisper_model", ["tiny", "base", "small", "medium", "large-v3"])

        ai_row = ctk.CTkFrame(ai_tab, fg_color="transparent")
        ai_row.pack(fill="x", padx=14, pady=(8, 0))
        self._settings_combo(ai_row, "Dispositivo", "device", ["cpu", "cuda"], side="left")
        self._settings_combo(ai_row, "Precisão", "compute_type", ["int8", "float16", "float32"], side="left")
        self._settings_entry(ai_row, "Threads", "cpu_threads", width=90, side="left")

        footer = ctk.CTkFrame(window, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 20))
        ctk.CTkButton(footer, text="Cancelar", width=100, fg_color="#333333", hover_color="#444444",
                      command=window.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(footer, text="Salvar", width=110, fg_color="#E50914", hover_color="#B20710",
                      command=self.save_settings).pack(side="right")

    def _settings_entry(self, parent, label, key, show=None, width=None, side=None):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x" if side is None else None, padx=14 if side is None else 4,
                   pady=(10, 0), side=side)
        ctk.CTkLabel(frame, text=label, text_color="gray75").pack(anchor="w")
        entry_options = {
            "textvariable": self.settings_vars[key], "height": 36,
            "fg_color": "#303030", "border_width": 0,
        }
        if show is not None:
            entry_options["show"] = show
        if width is not None:
            entry_options["width"] = width
        entry = ctk.CTkEntry(frame, **entry_options)
        entry.pack(fill="x" if width is None else None, pady=(3, 0))
        return entry

    def _settings_combo(self, parent, label, key, values, side=None):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x" if side is None else None, padx=14 if side is None else 4,
                   pady=(10, 0), side=side)
        ctk.CTkLabel(frame, text=label, text_color="gray75").pack(anchor="w")
        combo = ctk.CTkComboBox(frame, variable=self.settings_vars[key], values=values, height=36,
                                width=112 if side else 200, fg_color="#303030", border_width=0)
        combo.pack(fill="x" if side is None else None, pady=(3, 0))
        return combo

    def save_settings(self):
        try:
            threads = int(self.settings_vars['cpu_threads'].get().strip())
            if threads < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Configurações", "Threads deve ser um número inteiro maior que zero.", parent=self.settings_window)
            return

        required = ('anki_url', 'base_url', 'ai_model', 'whisper_model')
        if any(not self.settings_vars[key].get().strip() for key in required):
            messagebox.showerror("Configurações", "Preencha os endereços e modelos obrigatórios.", parent=self.settings_window)
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
        })
        CONFIG['whisper'].update({
            'model_size': self.settings_vars['whisper_model'].get().strip(),
            'device': self.settings_vars['device'].get().strip(),
            'compute_type': self.settings_vars['compute_type'].get().strip(),
            'cpu_threads': threads,
        })
        save_config(CONFIG)
        self.settings_window.destroy()
        self.status_var.set("Status: Configurações salvas")
        self.root.after(100, self.load_anki_data)
        
    def _on_url_changed(self, *args):
        """Sanitiza automaticamente a URL colada pelo usuário."""
        try:
            raw = self.url_var.get()
            # Se não tem nada ainda, ignora
            if not raw:
                return
            
            cleaned = raw.strip()
            
            # Detectar URLs duplicadas coladas (ex: https://...https://...)
            if cleaned.count('http') > 1:
                match = re.search(r'https?://[^\s]+', cleaned)
                if match:
                    cleaned = match.group(0)
            
            # Só atualiza se mudou algo (evita loop infinito)
            if cleaned != raw:
                self.url_var.set(cleaned)
        except Exception:
            pass
        
    def _cleanup_zombie_workspaces(self):
        """Varre e apaga workspaces órfãos de sessões anteriores que fecharam de forma abrupta."""
        zombies = glob.glob("workspace_*")
        for zombie in zombies:
            try:
                shutil.rmtree(zombie)
            except Exception:
                pass
        
    def _update_stepper(self, step_number):
        steps = [self.step_1, self.step_2, self.step_3, self.step_4]
        # Apaga todos
        for btn in steps:
            btn.configure(fg_color="#333333", text_color="gray70")
            
        # Acende o atual
        if 1 <= step_number <= 4:
            steps[step_number - 1].configure(fg_color="#E50914", text_color="white")
        
    def _log_sniffer(self, string):
        s = string.lower()
        if "baixando vídeo" in s:
            self.status_var.set("Status: Baixando vídeo (yt-dlp)...")
            self._update_stepper(1)
        elif "transcrição local com whisper" in s:
            self.status_var.set("Status: Transcrevendo Áudio (Whisper)...")
            self._update_stepper(2)
        elif "iniciando tradução" in s:
            self.status_var.set("Status: Traduzindo Texto (Omniroute IA)...")
            self._update_stepper(2)
        elif "fatiamento e exportação" in s:
            self.status_var.set("Status: Fatiando Mídias (FFmpeg)...")
            self._update_stepper(3)
        elif "adicionado ao anki" in s:
            self.status_var.set("Status: Inserindo no Anki...")
            self._update_stepper(4)
        elif "limpando" in s:
            self.status_var.set("Status: Limpando Lixeira...")
            self._update_stepper(0)
            
    def load_anki_data(self):
        print("Conectando ao Anki...\n")
        decks = invoke_anki('deckNames')
        models = invoke_anki('modelNames')
        
        if decks is None or models is None:
            self.status_var.set("Erro Crítico: Anki Desligado!")
            print("Erro Crítico: Anki não encontrado.")
            self.start_btn.configure(state="disabled")
            self.deck_cb.configure(values=["Erro de Conexão"])
            self.model_cb.configure(values=["Erro de Conexão"])
            return
            
        self.deck_cb.configure(values=decks)
        self.model_cb.configure(values=models)
        self.start_btn.configure(state="normal")
        
        if CONFIG['anki']['deck_name'] in decks:
            self.deck_cb.set(CONFIG['anki']['deck_name'])
        elif decks:
            self.deck_cb.set(decks[0])
            
        if CONFIG['anki']['model_name'] in models:
            self.model_cb.set(CONFIG['anki']['model_name'])
        elif models:
            self.model_cb.set(models[0])
            
        print("Pronto para processar vídeos.\n")

    def start_processing(self):
        url = self.url_var.get().strip()
        deck = self.deck_cb.get()
        model = self.model_cb.get()
        
        if not url and not self.local_video_path:
            messagebox.showerror("Aviso", "Insira um link do YouTube ou selecione um vídeo local.")
            return

        if self.local_video_path and not os.path.isfile(self.local_video_path):
            messagebox.showerror("Aviso", "O vídeo local selecionado não está mais disponível.")
            self.clear_local_file("Vídeo")
            return

        if self.local_srt_path and not os.path.isfile(self.local_srt_path):
            messagebox.showerror("Aviso", "A legenda selecionada não está mais disponível.")
            self.clear_local_file("Legenda")
            return
            
        if "Carregando" in deck or "Erro" in deck:
            return

        self.open_field_preview(url, deck, model)

    def open_field_preview(self, url, deck, model):
        """Mostra e permite editar o destino de cada dado antes do pipeline."""
        fields = invoke_anki('modelFieldNames', modelName=model)
        if not fields:
            messagebox.showerror("Campos do deck", f"Não foi possível obter os campos do modelo '{model}'.")
            return

        if hasattr(self, "field_preview_window") and self.field_preview_window.winfo_exists():
            self.field_preview_window.destroy()

        window = ctk.CTkToplevel(self.root)
        self.field_preview_window = window
        window.title("Prévia dos campos")
        window.geometry("590x620")
        window.minsize(520, 500)
        window.configure(fg_color="#141414")
        window.transient(self.root)
        window.grab_set()

        ctk.CTkLabel(
            window, text="Prévia dos campos", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(anchor="w", padx=24, pady=(22, 2))
        ctk.CTkLabel(
            window, text=f"Modelo: {model}\nEscolha o conteúdo que cada campo receberá.",
            justify="left", text_color="gray60",
        ).pack(anchor="w", padx=24, pady=(0, 14))

        source_labels = {
            "Não preencher": None,
            "Áudio da cena (MP3)": "audio",
            "Clipe de vídeo (WebM)": "clip",
            "Imagem da cena (JPG)": "snapshot",
            "Legenda original": "english_subtitle",
            "Legenda traduzida": "portuguese_subtitle",
            "Identificador do card": "index",
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

        list_frame = ctk.CTkScrollableFrame(window, fg_color="#202020", corner_radius=12)
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 14))
        list_frame.grid_columnconfigure(1, weight=1)
        self.field_mapping_vars = {}

        for row, field in enumerate(fields):
            ctk.CTkLabel(
                list_frame, text=field, anchor="w", font=ctk.CTkFont(size=12, weight="bold")
            ).grid(row=row, column=0, padx=(10, 14), pady=7, sticky="w")
            initial_label = slot_to_label.get(field_to_slot.get(field), "Não preencher")
            variable = ctk.StringVar(value=initial_label)
            self.field_mapping_vars[field] = variable
            ctk.CTkComboBox(
                list_frame, variable=variable, values=list(source_labels.keys()),
                state="readonly", height=34, fg_color="#303030", border_width=0,
                dropdown_fg_color="#303030",
            ).grid(row=row, column=1, padx=(0, 10), pady=7, sticky="ew")

        ctk.CTkLabel(
            window,
            text="Cada tipo de conteúdo pode ser atribuído a apenas um campo.",
            text_color="gray55", font=ctk.CTkFont(size=10),
        ).pack(anchor="w", padx=24, pady=(0, 10))

        footer = ctk.CTkFrame(window, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 20))
        ctk.CTkButton(
            footer, text="Voltar", width=100, fg_color="#333333", hover_color="#444444",
            command=window.destroy,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            footer, text="Confirmar e iniciar", width=155, fg_color="#E50914", hover_color="#B20710",
            command=lambda: self._confirm_field_preview(url, deck, model),
        ).pack(side="right")

    def _confirm_field_preview(self, url, deck, model):
        field_mapping = {}
        for field, variable in self.field_mapping_vars.items():
            slot = self.field_source_labels[variable.get()]
            if slot is None:
                continue
            if slot in field_mapping:
                label = variable.get()
                messagebox.showerror(
                    "Campos do deck", f"'{label}' foi atribuído a mais de um campo.",
                    parent=self.field_preview_window,
                )
                return
            field_mapping[slot] = field

        if not field_mapping:
            messagebox.showerror(
                "Campos do deck", "Configure ao menos um campo antes de iniciar.",
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
        
        self.status_var.set("Status: Inicializando Pipeline...")
        self.progress_bar.start() # Inicia animação da barra
        
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
            print(f"\nERRO CRÍTICO: {e}")
            print(err_detail)
            self.root.after(0, lambda: self.status_var.set("Status: Erro Crítico!"))
            # Limpar workspace se existir
            if work_dir and os.path.exists(work_dir):
                try:
                    shutil.rmtree(work_dir)
                except Exception:
                    pass
            self.root.after(0, self._unlock_ui)
            
    def _handle_completion(self, success, work_dir):
        if success:
            self.status_var.set("Status: Finalizado com Sucesso!")
            print("\nFINALIZADO.")
            # Notificação sonora de conclusão
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass
            
            # Perguntar ao usuário o que fazer com os temporários
            result = messagebox.askyesnocancel(
                "Processo Concluído", 
                "O processo terminou com sucesso!\n\n"
                "Os arquivos temporários (vídeos baixados e legendas) ocupam espaço no disco.\n\n"
                "• [Sim] - Excluir pasta temporária agora (Recomendado)\n"
                "• [Não] - Manter os arquivos e abrir a pasta para visualizar\n"
                "• [Cancelar] - Apenas manter os arquivos"
            )
            
            if result is True:
                print("\nLimpando arquivos temporários...")
                try:
                    shutil.rmtree(work_dir)
                    print("Pasta excluída.")
                except Exception as e:
                    print(f"Aviso: Não foi possível deletar {work_dir}. Erro: {e}")
            elif result is False:
                print(f"\nMantendo pasta temporária: {work_dir}")
                # Abrir pasta no Windows
                os.startfile(os.path.abspath(work_dir))
            else:
                print(f"\nMantendo pasta temporária: {work_dir}")
                
        else:
            self.status_var.set("Status: Falhou!")
            print("\nFALHOU.")
            print("\nLimpando arquivos temporários (falha)...")
            try:
                shutil.rmtree(work_dir)
            except:
                pass
                
        self._unlock_ui()
            
    def _unlock_ui(self):
        self.progress_bar.stop()
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
    app = AutoAnkiApp(root)
    root.mainloop()
