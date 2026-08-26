class StdoutRedirector:
    def __init__(self, text_widget, callback=None):
        self.text_widget = text_widget
        self.callback = callback

    def write(self, string):
        # yt-dlp costuma usar \r para atualizar a mesma linha.
        # Nós vamos substituir \r por \n para não criar uma linha infinita no Tkinter.
        sanitized = string.replace('\r', '\n')
        try:
            self.text_widget.after(0, self._safe_write, sanitized)
        except Exception:
            pass  # Widget pode ter sido destruído, ignora silenciosamente

    def _safe_write(self, string):
        try:
            self.text_widget.insert("end", string)
            self.text_widget.see("end")
            if self.callback:
                self.callback(string)
        except Exception:
            pass  # Widget pode ter sido destruído

    def flush(self):
        pass
