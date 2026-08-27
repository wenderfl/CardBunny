import customtkinter as ctk
import ctypes

app = ctk.CTk()
app.geometry("400x300")
app.title("Test")

# app.overrideredirect(True) # This removes taskbar icon

def remove_titlebar():
    hwnd = ctypes.windll.user32.GetParent(app.winfo_id())
    GWL_STYLE = -16
    WS_CAPTION = 0x00C00000
    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
    style = style & ~WS_CAPTION
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style)

app.after(10, remove_titlebar)

ctk.CTkLabel(app, text="Frameless with Taskbar!").pack(pady=50)

# Simulate closing after 3 seconds
app.after(3000, app.destroy)

app.mainloop()
