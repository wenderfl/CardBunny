class StdoutRedirector:
    def __init__(self, text_widget, callback=None):
        self.text_widget = text_widget
        self.callback = callback

    def write(self, string):
        # yt-dlp often uses \r to update the same line.
        # We replace \r with \n to avoid creating an infinite line in Tkinter.
        sanitized = string.replace('\r', '\n')
        try:
            self.text_widget.after(0, self._safe_write, sanitized)
        except Exception:
            pass  # Widget might have been destroyed, ignore silently

    def _safe_write(self, string):
        try:
            self.text_widget.insert("end", string)
            self.text_widget.see("end")
            if self.callback:
                self.callback(string)
        except Exception:
            pass  # Widget might have been destroyed

    def flush(self):
        pass
