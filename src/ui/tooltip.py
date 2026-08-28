import tkinter as tk


class Tooltip:
    """Small, dependency-free tooltip for Tk/CustomTkinter widgets."""

    def __init__(self, widget, text="", delay=450):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._after_id = None
        self._window = None

        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<FocusIn>", self._schedule, add="+")
        widget.bind("<FocusOut>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def set_text(self, text):
        self.text = text or ""
        if not self.text:
            self._hide()

    def _schedule(self, _event=None):
        self._cancel()
        if self.text:
            self._after_id = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        self._after_id = None
        if self._window is not None or not self.text:
            return

        try:
            x = self.widget.winfo_rootx() + 8
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
            screen_width = self.widget.winfo_screenwidth()

            window = tk.Toplevel(self.widget)
            window.wm_overrideredirect(True)
            window.attributes("-topmost", True)
            label = tk.Label(
                window,
                text=self.text,
                bg="#111111",
                fg="#FFFFFF",
                font=("Segoe UI", 9, "bold"),
                padx=8,
                pady=5,
                relief="solid",
                borderwidth=1,
                justify="left",
            )
            label.pack()
            window.update_idletasks()
            x = min(x, max(0, screen_width - window.winfo_reqwidth() - 8))
            window.wm_geometry(f"+{x}+{y}")
            self._window = window
        except Exception:
            self._window = None

    def _hide(self, _event=None):
        self._cancel()
        if self._window is not None:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None
