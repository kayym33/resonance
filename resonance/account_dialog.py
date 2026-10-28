from __future__ import annotations

import time
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Callable

import customtkinter
from PIL import Image

from .constants import (
    ACCENT_DARK,
    APP_AUTHOR,
    BACKGROUND,
    HOVER,
    INK,
    INK_SOFT,
    MONO_FONT,
    MUTED,
)
from .user_profile import display_name, set_avatar, set_display_name
from .windows import cancel_pending_after, outline_width, prepare_window

if TYPE_CHECKING:
    from .app import ResonanceApp

MIN_PASSWORD_LENGTH = 8
AVATAR_SIZE = 112
IMAGE_TYPES = (
    ("images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
    ("all files", "*"),
)


def mono(size: int, weight: str = "normal") -> customtkinter.CTkFont:
    return customtkinter.CTkFont(family=MONO_FONT, size=size, weight=weight)


def describe_sync(status: str, message: str, last_synced: float | None) -> str:
    if status == "syncing":
        return "syncing..."
    if status in ("offline", "error"):
        return f"not synced: {message}" if message else "not synced"
    if status == "synced" and last_synced is not None:
        minutes = int((time.time() - last_synced) // 60)
        synced = "synced just now" if minutes < 1 else f"synced {minutes} min ago"
        # Synced, but with a caveat (recipes waiting for the server).
        return f"{synced}; {message}" if message else synced
    return message or "not synced yet"


class AccountDialog(customtkinter.CTkToplevel):
    """Sign in, or (when signed in) edit the profile and sign out."""

    def __init__(
        self,
        parent: customtkinter.CTkToplevel,
        app: ResonanceApp,
    ) -> None:
        super().__init__(parent)
        self.app: ResonanceApp = app
        self.title("account")
        self.resizable(False, False)
        self.configure(fg_color=BACKGROUND)
        self.transient(parent)
        prepare_window(self)
        scaling = customtkinter.ScalingTracker.get_window_scaling(self)
        width = 400
        x = parent.winfo_rootx() + (parent.winfo_width() - width * scaling) / 2
        y = parent.winfo_rooty() + parent.winfo_height() / 6
        self.geometry(f"+{round(x)}+{round(y)}")
        self.bind("<Escape>", lambda _event: self.destroy())

        self.body = customtkinter.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=24, pady=20)
        # Sets the dialog's width; the height follows the contents.
        customtkinter.CTkFrame(
            self.body,
            width=width - 48,
            height=1,
            fg_color="transparent",
        ).pack()
        self.status_label: customtkinter.CTkLabel | None = None
        self.app.sync.listeners.append(self.refresh_status)
        self.render()
        self.after(100, self.grab_and_focus)

    def grab_and_focus(self) -> None:
        self.grab_set()
        self.focus_force()
        if self.focus_target is not None:
            self.focus_target.focus_set()

    def render(self) -> None:
        for child in self.body.winfo_children()[1:]:
            child.destroy()
        self.status_label = None
        self.focus_target: customtkinter.CTkEntry | None = None
        if self.app.sync.session is None:
            self.render_sign_in()
        else:
            self.render_account()

    # Signed out

    def render_sign_in(self) -> None:
        self.heading("sign in")
        self.note(
            f"Sync your to-dos, calendar and settings across devices. "
            f"Accounts are invite-only: ask {APP_AUTHOR} for one."
        )
        self.email_entry = self.field("email")
        self.password_entry = self.field("password", secret=True)
        self.focus_target = self.email_entry
        self.error_label = self.error_line()
        buttons = self.button_row()
        self.sign_in_button = self.button(buttons, "sign in", self.sign_in, solid=True)
        self.button(buttons, "not now", self.destroy)
        customtkinter.CTkButton(
            buttons,
            text="reset password",
            width=0,
            height=32,
            corner_radius=0,
            fg_color="transparent",
            hover_color=HOVER,
            text_color=MUTED,
            font=mono(10),
            command=self.reset_password,
        ).pack(side="left")
        self.bind("<Return>", lambda _event: self.sign_in())

    def reset_password(self) -> None:
        # Accounts are made by hand in the Supabase dashboard, so is this.
        self.error_label.configure(
            text=f"haha... ask {APP_AUTHOR} to reset",
            text_color=MUTED,
        )

    def sign_in(self) -> None:
        email = self.email_entry.get().strip()
        password = self.password_entry.get()
        if not email or not password:
            self.error_label.configure(
                text="enter your email and password",
                text_color=ACCENT_DARK,
            )
            return
        self.error_label.configure(text="", text_color=ACCENT_DARK)
        self.sign_in_button.configure(text="signing in...", state="disabled")
        self.app.sync.sign_in(email, password, self.signed_in, self.confirm_switch)

    def confirm_switch(self) -> bool:
        return messagebox.askyesno(
            "Different account",
            "This computer has data from a different account. Signing in "
            "will replace it with this account's data. Continue?",
            parent=self,
        )

    def signed_in(self, error: str | None) -> None:
        if not self.winfo_exists():
            return
        if error is None:
            self.unbind("<Return>")
            self.render()
            return
        if error != "cancelled":
            self.error_label.configure(text=error.lower())
        self.sign_in_button.configure(text="sign in", state="normal")

    # Signed in

    def render_account(self) -> None:
        session = self.app.sync.session
        assert session is not None
        top = customtkinter.CTkFrame(self.body, fg_color="transparent")
        top.pack(fill="x")
        self.avatar_label = customtkinter.CTkLabel(
            top,
            text="",
            width=AVATAR_SIZE,
            height=AVATAR_SIZE,
        )
        self.avatar_label.pack(side="left")
        details = customtkinter.CTkFrame(top, fg_color="transparent")
        details.pack(side="left", fill="both", expand=True, padx=(16, 0))
        customtkinter.CTkLabel(
            details,
            text="account",
            font=mono(18, "bold"),
            text_color=INK,
            anchor="w",
        ).pack(fill="x")
        for text in (f"signed in as {session.email}", ""):
            label = customtkinter.CTkLabel(
                details,
                text=text,
                font=mono(10),
                text_color=MUTED,
                anchor="w",
                justify="left",
                wraplength=200,
            )
            label.pack(fill="x", pady=(2, 0))
        self.status_label = label
        self.refresh_status()
        picture_row = customtkinter.CTkFrame(details, fg_color="transparent")
        picture_row.pack(anchor="w", pady=(10, 0))
        self.button(picture_row, "choose image", self.choose_avatar, side="left")
        self.button(picture_row, "remove", self.remove_avatar, side="left")
        self.show_avatar()

        self.name_entry = self.field("display name", display_name())
        self.focus_target = self.name_entry
        name_row = self.button_row(top_gap=8)
        self.button(name_row, "save name", self.save_name, solid=True, side="left")

        self.password_entry = self.field("new password", secret=True)
        password_row = self.button_row(top_gap=8)
        self.button(password_row, "change password", self.change_password, side="left")
        self.error_label = self.error_line()

        buttons = self.button_row()
        self.button(buttons, "close", self.destroy)
        self.button(buttons, "sync now", self.app.sync.sync_now)
        self.button(buttons, "sign out", self.sign_out, color=ACCENT_DARK)

    def show_avatar(self) -> None:
        large, _icon = self.app.avatar_images()
        self.avatar_image = customtkinter.CTkImage(
            light_image=large[0],
            dark_image=large[1],
            size=(AVATAR_SIZE, AVATAR_SIZE),
        )
        self.avatar_label.configure(image=self.avatar_image)

    def choose_avatar(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="choose a picture",
            filetypes=IMAGE_TYPES,
        )
        if not path:
            return
        try:
            with Image.open(path) as image:
                set_avatar(image)
        except OSError:
            self.error_label.configure(
                text="couldn't open that image",
                text_color=ACCENT_DARK,
            )
            return
        self.avatar_changed()

    def remove_avatar(self) -> None:
        set_avatar(None)
        self.avatar_changed()

    def avatar_changed(self) -> None:
        self.error_label.configure(text="")
        self.show_avatar()
        self.app.profile_changed()

    def save_name(self) -> None:
        set_display_name(self.name_entry.get())
        self.error_label.configure(text="name saved", text_color=MUTED)
        # The fallback avatar is the name's initial.
        self.show_avatar()
        self.app.profile_changed()

    def change_password(self) -> None:
        password = self.password_entry.get()
        if len(password) < MIN_PASSWORD_LENGTH:
            self.error_label.configure(
                text=f"use at least {MIN_PASSWORD_LENGTH} characters",
                text_color=ACCENT_DARK,
            )
            return
        self.error_label.configure(text="changing password...", text_color=MUTED)
        self.app.sync.change_password(password, self.password_changed)

    def password_changed(self, error: str | None) -> None:
        if not self.winfo_exists():
            return
        if error is None:
            self.password_entry.delete(0, "end")
            self.error_label.configure(text="password changed", text_color=MUTED)
        else:
            self.error_label.configure(text=error.lower(), text_color=ACCENT_DARK)

    def sign_out(self) -> None:
        self.app.sync.sign_out()
        self.render()

    def refresh_status(self) -> None:
        if self.status_label is not None and self.winfo_exists():
            sync = self.app.sync
            self.status_label.configure(
                text=describe_sync(sync.status, sync.message, sync.last_synced)
            )

    # Building blocks

    def heading(self, text: str) -> None:
        customtkinter.CTkLabel(
            self.body,
            text=text,
            font=mono(18, "bold"),
            text_color=INK,
            anchor="w",
        ).pack(fill="x")

    def note(self, text: str) -> customtkinter.CTkLabel:
        label = customtkinter.CTkLabel(
            self.body,
            text=text,
            font=mono(10),
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=340,
        )
        label.pack(fill="x", pady=(2, 6))
        return label

    def field(
        self,
        label: str,
        value: str = "",
        secret: bool = False,
    ) -> customtkinter.CTkEntry:
        customtkinter.CTkLabel(
            self.body,
            text=label.upper(),
            font=mono(10, "bold"),
            text_color=MUTED,
            anchor="w",
            height=16,
        ).pack(fill="x", pady=(8, 0))
        entry = customtkinter.CTkEntry(
            self.body,
            height=30,
            corner_radius=0,
            border_width=outline_width(self),
            border_color=INK,
            text_color=INK,
            show="•" if secret else "",
            font=mono(12),
        )
        entry.pack(fill="x")
        if value:
            entry.insert(0, value)
        return entry

    def error_line(self) -> customtkinter.CTkLabel:
        label = customtkinter.CTkLabel(
            self.body,
            text="",
            font=mono(10),
            text_color=ACCENT_DARK,
            anchor="w",
            justify="left",
            wraplength=340,
            height=16,
        )
        label.pack(fill="x", pady=(6, 0))
        return label

    def button_row(self, top_gap: int = 14) -> customtkinter.CTkFrame:
        row = customtkinter.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", pady=(top_gap, 0))
        return row

    def button(
        self,
        row: customtkinter.CTkFrame,
        text: str,
        command: Callable[[], None],
        solid: bool = False,
        color: str = INK,
        side: str = "right",
    ) -> customtkinter.CTkButton:
        button = customtkinter.CTkButton(
            row,
            text=text,
            width=len(text) * 9 + 24,
            height=32,
            corner_radius=0,
            border_width=0 if solid else outline_width(self),
            border_color=INK,
            fg_color=INK if solid else "transparent",
            hover_color=INK_SOFT if solid else HOVER,
            text_color=BACKGROUND if solid else color,
            font=mono(11, "bold"),
            command=command,
        )
        button.pack(side=side, padx=(0, 6) if side == "left" else (6, 0))
        return button

    def destroy(self) -> None:
        if self.refresh_status in self.app.sync.listeners:
            self.app.sync.listeners.remove(self.refresh_status)
        cancel_pending_after(self)
        super().destroy()

