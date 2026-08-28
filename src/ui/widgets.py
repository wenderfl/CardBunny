import customtkinter as ctk


class AutoHideScrollableFrame(ctk.CTkScrollableFrame):
    """Scrollable frame whose scrollbar only appears when content overflows."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._scrollbar_update_job = None
        self.bind("<Configure>", self._schedule_scrollbar_update, add="+")
        self._parent_canvas.bind(
            "<Configure>", self._schedule_scrollbar_update, add="+",
        )
        self.after_idle(self._update_scrollbar_visibility)

    def _schedule_scrollbar_update(self, _event=None):
        if self._scrollbar_update_job is None:
            self._scrollbar_update_job = self.after_idle(
                self._update_scrollbar_visibility,
            )

    def _update_scrollbar_visibility(self):
        self._scrollbar_update_job = None
        try:
            bounds = self._parent_canvas.bbox("all")
            content_height = 0 if bounds is None else bounds[3] - bounds[1]
            viewport_height = self._parent_canvas.winfo_height()
            needs_scrollbar = content_height > viewport_height + 2

            if needs_scrollbar and not self._scrollbar.winfo_ismapped():
                self._scrollbar.grid()
            elif not needs_scrollbar and self._scrollbar.winfo_ismapped():
                self._scrollbar.grid_remove()
        except Exception:
            pass
