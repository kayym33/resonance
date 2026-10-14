from __future__ import annotations

import customtkinter

from .constants import ACCENT, BACKGROUND, INK, INK_SOFT, MONO_FONT, MUTED
from .windows import cancel_pending_after, outline_width

TOAST_WIDTH = 320
TOAST_MARGIN = 24
TOAST_GAP = 10
TOAST_SHOW_MS = 15_000


def mono(size: int, weight: str = "normal") -> customtkinter.CTkFont:
    return customtkinter.CTkFont(family=MONO_FONT, size=size, weight=weight)


class Toast(customtkinter.CTkToplevel):
    """A borderless always-on-top note in the screen's bottom-right corner,
    for when the system can't show a notification. Click to dismiss.

    ``stack`` is the list of toasts already showing; this one sits above
    them and removes itself when it closes.
    """

    def __init__(
        self,
        parent: customtkinter.CTk,
        title: str,
        body: str,
        stack: list[Toast],
    ) -> None:
        super().__init__(parent)
        self.stack = stack
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=BACKGROUND)

        frame = customtkinter.CTkFrame(
            self,
            fg_color=BACKGROUND,
            border_color=INK,
            border_width=outline_width(self),
            corner_radius=0,
        )
        frame.pack(fill="both", expand=True)
        customtkinter.CTkFrame(
            frame,
            width=TOAST_WIDTH,
            height=1,
            fg_color="transparent",
        ).pack(padx=8, pady=(4, 0))
        header = customtkinter.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(4, 0))
        customtkinter.CTkLabel(
            header,
            text="■",
            font=mono(10),
            text_color=ACCENT,
            height=16,
        ).pack(side="left", padx=(0, 6))
        customtkinter.CTkLabel(
            header,
            text="REMINDER",
            font=mono(10, "bold"),
            text_color=MUTED,
            height=16,
        ).pack(side="left")
        customtkinter.CTkLabel(
            frame,
            text=title,
            font=mono(14, "bold"),
            text_color=INK,
            anchor="w",
            justify="left",
            wraplength=TOAST_WIDTH - 20,
        ).pack(fill="x", padx=14, pady=(2, 0))
        customtkinter.CTkLabel(
            frame,
            text=body,
            font=mono(11),
            text_color=INK_SOFT,
            anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 12))

        self.bind_all_children(self)
        stack.append(self)
        self.place_in_corner()
        self.deiconify()
        self.after(TOAST_SHOW_MS, self.destroy)

    def bind_all_children(self, widget: customtkinter.CTkBaseClass) -> None:
        widget.bind("<Button-1>", lambda _event: self.destroy())
        for child in widget.winfo_children():
            self.bind_all_children(child)

    def place_in_corner(self) -> None:
        """Bottom-right, above the toasts already showing."""
        self.update_idletasks()
        y = self.winfo_screenheight() - TOAST_MARGIN
        for toast in self.stack:
            if toast is self:
                break
            y -= toast.winfo_reqheight() + TOAST_GAP
        x = self.winfo_screenwidth() - TOAST_MARGIN - self.winfo_reqwidth()
        y -= self.winfo_reqheight()
        self.geometry(f"+{x}+{y}")

    def destroy(self) -> None:
        # A click and the timer can both close it.
        if self not in self.stack:
            return
        self.stack.remove(self)
        cancel_pending_after(self)
        super().destroy()
