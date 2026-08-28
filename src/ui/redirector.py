class StdoutRedirector:
    def __init__(self, text_widget, callback=None, max_lines=1000):
        self.text_widget = text_widget
        self.callback = callback
        self.max_lines = max_lines

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
            previous_state = self.text_widget.cget("state")
            if previous_state == "disabled":
                self.text_widget.configure(state="normal")
            at_bottom = self.text_widget.yview()[1] >= 0.999
            self.text_widget.insert("end", string)
            line_count = int(self.text_widget.index("end-1c").split(".")[0])
            if line_count > self.max_lines:
                excess = line_count - self.max_lines
                self.text_widget.delete("1.0", f"{excess + 1}.0")
            if at_bottom:
                self.text_widget.see("end")
            if previous_state == "disabled":
                self.text_widget.configure(state="disabled")
            if self.callback:
                self.callback(string)
        except Exception:
            pass  # Widget might have been destroyed

    def flush(self):
        pass
