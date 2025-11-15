import tkinter as tk
from tkinter import ttk
from tkinter import font
from tkinter import messagebox
from tkinter import filedialog
import logging
from typing import Callable, Optional, List
import os
import sys
import subprocess


class Handlers:
    """GUIApp handlers, to be filled in by the application code where desired."""

    join: Callable[[str, str, Optional[str], Optional[str]], None] = lambda *_: logging.warning("Not implemented")
    update_user: Callable[[str], None] = lambda *_: logging.warning("Not implemented")
    leave: Callable[[], None] = lambda *_: logging.warning("Not implemented")
    list_users: Callable[[], List[str]] = lambda *_: logging.warning("Not implemented")
    send_message: Callable[[str, str], None] = lambda *_: logging.warning("Not implemented")
    send_file: Callable[[str, str], None] = lambda *_: logging.warning("Not implemented")


class GuiApp:
    """GUI logic, to be driven from the application code."""

    def __init__(self, handlers: Handlers = Handlers()):
        """Public API: create the GUI with the provided handlers."""

        self.root = tk.Tk()
        self.root.title("Chat App")
        self.root.geometry("1000x650")  # width x height in pixels
        self.root.tk.call("tk", "scaling", 1.8)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        # GUI starts in not-joined state
        self.state_joined = False

        # Register handlers (if any provided)
        self.handlers = handlers

        # Create the UI widgets
        self.widgets = _GuiWidgets(self)

    def start(self):
        """Public API: start the GUI event loop."""
        self.root.mainloop()

    # -------------------------------------------------------------------------
    # Callbacks invoked by DDS / application
    # -------------------------------------------------------------------------

    def user_joined(self, user, group, name: str = "", last_name: str = ""):
        """Public API: update the UI to reflect a new user has joined.
        - Add the user's group to the combobox if applicable.
        - Add the user's details to the Online users list.
        - Print a message in the chat indicating user has joined.
        """

        # Early exit if not in the right state
        if not self.state_joined:
            return
        
        if group != self.widgets.group_entry.get():
            return

        # Add to online users - early exit if exception
        if not self.widgets.online_users_tree.add_user(user, group, name, last_name):
            return

        # Update the message board
        space = " " if (name and last_name) else ""
        fullname_str = f" ({name}{space}{last_name})" if (name or last_name) else ""
        joined_str = f"> {user}{fullname_str} joined on group {group}."
        self.widgets.message_text.append_line(joined_str)

    def user_left(self, user):
        """Public API: update the UI to reflect a user has left."""
        if not self.state_joined:
            return

        # Remove from online users - early exit if exception
        if not self.widgets.online_users_tree.delete_user(user):
            return

        # Update the message board
        left_str = f"> {user} dropped."
        self.widgets.message_text.append_line(left_str)

    def message_received(self, user, destination, message):
        """Public API: add a (received) text message to the board."""

        dest_str = "you" if destination == self.widgets.user_entry.get() else destination
        fullmsg_str = f"{user} (to {dest_str}): {message}"
        self.widgets.message_text.append_line(fullmsg_str)

    def file_received(self, user, destination, file_path, mime_type):
        """Public API: show a received file in the Message Board with interaction."""

        dest_str = "you" if destination == self.widgets.user_entry.get() else destination
        filename = os.path.basename(file_path)

        if mime_type.startswith("image/"):
            # Insert a text line + inline thumbnail
            self.widgets.message_text.append_line(
                f"{user} sent an image to {dest_str}: {filename}"
            )
            self.widgets.insert_image(file_path)
        else:
            # Insert a clickable link line for videos/other files
            self.widgets.insert_file_link(
                f"{user} sent a file to {dest_str}: {filename} [open]",
                file_path,
            )

    # -------------------------------------------------------------------------
    # Internal GUI actions
    # -------------------------------------------------------------------------

    def _close(self):
        """Private API: trigger leave command (if appropriate) when closing the GUI."""
        if self.state_joined:
            self._leave()
        self.root.destroy()

    def _join(self):
        """Private API: update the UI to reflect joining the chat and call the handler."""

        # Deny joining if missing key information
        user = self.widgets.user_entry.get()
        group = self.widgets.group_entry.get()
        if not all((user, group)):
            _ = "username" if not user else "group"
            __ = " and group." if not any((user, group)) else "."
            error_msg = f"Please insert a {_}{__}"
            messagebox.showerror(title="Error", message=error_msg)
            return

        # Update the joined state
        self.state_joined = True

        # Execute the action using details in the widgets
        kwargs = {ename: entry.get() for ename, entry in self.widgets.entry_widgets.items()}
        self.handlers.join(*kwargs.values())

        # Set all entry widgets to read only
        for entry in self.widgets.entry_widgets.values():
            entry.config(state="readonly")

        # Enable UI elements that shall not be available unless joined
        widgets = {
            self.widgets.group_entry: tk.NORMAL,
            self.widgets.update_button: tk.NORMAL,
            self.widgets.message_input: tk.NORMAL,
            self.widgets.send_button: tk.NORMAL,
            self.widgets.send_file_button: tk.NORMAL,
            self.widgets.online_users_button_refresh: tk.NORMAL,
            self.widgets.online_users_button_collapse: tk.NORMAL,
        }
        for widget, state in widgets.items():
            widget.config(state=state)

        # Change the button text and update its function
        self.widgets.join_button.config(text="Leave", command=self._leave)

    def _leave(self):
        """Private API: update the UI to reflect leaving the chat and call the handler."""

        # Update the joined state
        self.state_joined = False

        # Execute the action using details in the widgets
        self.handlers.leave()

        # Set all entry widgets to normal
        for entry in self.widgets.entry_widgets.values():
            entry.config(state=tk.NORMAL)

        # Clear all online users
        for item in self.widgets.online_users_tree.get_children():
            self.widgets.online_users_tree.delete(item)

        # Clear all text from the message board
        self.widgets.message_text.clear()

        # Disable other UI elements that shall not be available unless joined
        widgets = {
            self.widgets.update_button: tk.DISABLED,
            self.widgets.message_input: tk.DISABLED,
            self.widgets.send_button: tk.DISABLED,
            self.widgets.send_file_button: tk.DISABLED,
            self.widgets.online_users_button_refresh: tk.DISABLED,
            self.widgets.online_users_button_collapse: tk.DISABLED,
        }
        for widget, state in widgets.items():
            widget.config(state=state)

        # Change the button text and update its function
        self.widgets.join_button.config(text="Join", command=self._join)

    def _update_user(self):
        """Private API: execute the handler to update the user group."""
        if not self.state_joined:
            return
        self.handlers.update_user(self.widgets.group_entry.get())

    def _list_users(self):
        """Private API: execute the handler to get the list of users, then repopulate online users."""
        users = self.handlers.list_users()

        # Clear all online users
        for item in self.widgets.online_users_tree.get_children():
            self.widgets.online_users_tree.delete(item)

        # Add all users to online users list
        for entry in users if users else []:
            user = entry[0]
            group = entry[1]
            name = entry[2] if len(entry) > 2 else ""
            last_name = entry[3] if len(entry) > 3 else ""
            self.widgets.online_users_tree.add_user(user, group, name, last_name)

    def _send_message(self):
        """Private API: send the message to selected user or group."""
        if not self.state_joined:
            return

        # Determine if the destination is a user or a group
        selected_user = (
            self.widgets.online_users_tree.selection()[0]
            if self.widgets.online_users_tree.selection()
            else ""
        )
        group = self.widgets.group_entry.get()
        destination = selected_user if selected_user else group

        # Message text to send
        message = self.widgets.message_input.get()

        # Execute the handler
        self.handlers.send_message(destination, message)

        # Clear the message text entry
        self.widgets.message_input.delete(0, tk.END)

    def _send_file(self, destination, file_path):
        """Private API: forward a file send request to the handler."""
        if not self.state_joined:
            return
        self.handlers.send_file(destination, file_path)


class _GuiWidgets:
    """Create and manage all GUI widgets without implementing the logic."""

    def __init__(self, app: GuiApp):
        self.app = app
        self._image_refs: List[tk.PhotoImage] = []
        self._file_links: dict[str, str] = {}
        self._create_widgets()
        self._bind_ctrl_backspace()
        self._bind_enter()

    # ------------------------------------------------------------------    
    # Widget creation
    # ------------------------------------------------------------------

    def _create_widgets(self):
        """Create and configure all widgets."""
        self.root = self.app.root

        # --- Top frame for user input
        self.top_frame = ttk.Frame(self.root)
        self.top_frame.pack(fill=tk.X, padx=10, pady=5, anchor=tk.NW)

        # User
        self.user_label = ttk.Label(self.top_frame, text="User:")
        self.user_label.grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.user_entry = ttk.Entry(self.top_frame)
        self.user_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W + tk.E)

        # Group
        self.group_label = ttk.Label(self.top_frame, text="Group:")
        self.group_label.grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        self.group_entry = ttk.Entry(self.top_frame)
        self.group_entry.grid(row=0, column=3, padx=5, pady=5, sticky=tk.W + tk.E)

        # Name
        self.name_label = ttk.Label(self.top_frame, text="First name:")
        self.name_label.grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.name_entry = ttk.Entry(self.top_frame)
        self.name_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W + tk.E)

        # Last name
        self.last_name_label = ttk.Label(self.top_frame, text="Last name:")
        self.last_name_label.grid(row=1, column=2, padx=5, pady=5, sticky=tk.W)
        self.last_name_entry = ttk.Entry(self.top_frame)
        self.last_name_entry.grid(row=1, column=3, padx=5, pady=5, sticky=tk.W + tk.E)

        # Buttons
        self.join_button = ttk.Button(self.top_frame, text="Join", command=self.app._join)
        self.join_button.grid(row=0, column=4, padx=5, pady=5)
        self.update_button = ttk.Button(self.top_frame, text="Update", command=self.app._update_user)
        self.update_button.grid(row=1, column=4, padx=5, pady=5)
        self.update_button.config(state=tk.DISABLED)

        # Configure entries to expand in the grid
        self.top_frame.columnconfigure(1, weight=1)
        self.top_frame.columnconfigure(3, weight=1)

        # Collection of entry widgets
        self.entry_widget_names = ["user", "group", "name", "last_name"]
        self.entry_widgets = {ename: getattr(self, f"{ename}_entry") for ename in self.entry_widget_names}

        # --- Bottom frame
        self.bottom_frame = ttk.Frame(self.root)
        self.bottom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5, anchor=tk.NW)
        self.bottom_frame.columnconfigure(0, weight=1)
        self.bottom_frame.rowconfigure(0, weight=1)

        # Message board frame: label, board, scrollbar
        self.message_board_frame = ttk.Frame(self.bottom_frame)
        self.message_board_frame.grid(row=0, column=0, padx=5, pady=5, sticky=tk.W + tk.E + tk.N + tk.S)

        self.message_board_label = ttk.Label(self.message_board_frame, text="Message Board:")
        self.message_board_label.pack(anchor=tk.W)

        # --- Search bar for message history ---
        self.search_frame = ttk.Frame(self.message_board_frame)
        self.search_frame.pack(anchor=tk.W, fill=tk.X, pady=(0, 3))

        self.search_label = ttk.Label(self.search_frame, text="Search:")
        self.search_label.pack(side=tk.LEFT)

        self.search_entry = ttk.Entry(self.search_frame, width=20)
        self.search_entry.pack(side=tk.LEFT, padx=(3, 3))

        self.search_button = ttk.Button(self.search_frame, text="Search", command=self._search_messages)
        self.search_button.pack(side=tk.LEFT)

        self.clear_search_button = ttk.Button(self.search_frame, text="Clear", command=self._clear_search)
        self.clear_search_button.pack(side=tk.LEFT, padx=(3, 0))

        # Message text widget
        self.message_text = tk.Text(self.message_board_frame, height=10, width=50)
        self.message_text.config(state=tk.DISABLED)

        def append_line(text_str: str):
            self.message_text.config(state=tk.NORMAL)
            self.message_text.insert(tk.END, f"{text_str}\n")
            self.message_text.see(tk.END)
            self.message_text.config(state=tk.DISABLED)

        def clear():
            self.message_text.config(state=tk.NORMAL)
            self.message_text.delete("1.0", tk.END)
            self.message_text.config(state=tk.DISABLED)

        self.message_text.append_line = append_line  # type: ignore[attr-defined]
        self.message_text.clear = clear              # type: ignore[attr-defined]

        self.message_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.message_scrollbar = ttk.Scrollbar(
            self.message_board_frame, orient="vertical", command=self.message_text.yview
        )
        self.message_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.message_text.config(yscrollcommand=self.message_scrollbar.set)

        # Message input frame: input (with font) and send button
        self.message_input_frame = ttk.Frame(self.bottom_frame)
        self.message_input_frame.grid(row=1, column=0, padx=5, sticky=tk.W + tk.E + tk.N + tk.S)

        message_input_font = font.Font(family="Consolas", size=10)
        self.message_input = tk.Entry(self.message_input_frame, width=50, font=message_input_font)
        self.message_input.bind("<Return>", lambda event: self.app._send_message())
        self.message_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.message_input.config(state=tk.DISABLED)

        self.send_button = ttk.Button(self.message_input_frame, text="Send", command=self.app._send_message)
        self.send_button.pack(side=tk.RIGHT)
        self.send_button.config(state=tk.DISABLED)

        # Send File button
        self.send_file_button = ttk.Button(
            self.message_input_frame, text="Send file...", command=self._choose_file_and_send
        )
        self.send_file_button.pack(side=tk.RIGHT, padx=(5, 0))
        self.send_file_button.config(state=tk.DISABLED)

        # Online users frame: Online users list
        self.online_users_frame = ttk.Frame(self.bottom_frame)
        self.online_users_frame.grid(
            row=0,
            column=1,
            padx=(15, 0),
            pady=5,
            sticky=tk.W + tk.E + tk.N + tk.S,
            rowspan=2,
        )

        # Online users label and buttons
        self.online_users_label_frame = ttk.Frame(self.online_users_frame)
        self.online_users_label_frame.pack(anchor=tk.W, fill=tk.X, pady=(0, 5))

        self.online_users_label = ttk.Label(self.online_users_label_frame, text="Online users:", anchor="w")
        self.online_users_label.grid(row=0, column=0, padx=(0, 10), sticky=tk.W)

        self.online_users_button_refresh = ttk.Button(
            self.online_users_label_frame, text="\u21BB", width=4, command=self.app._list_users
        )
        self.online_users_button_refresh.grid(row=0, column=1, sticky=tk.E)
        self.online_users_button_refresh.config(state=tk.DISABLED)

        def collapse_cmd():
            self.online_users_button_collapse.state = not self.online_users_button_collapse.state
            for iid in self.online_users_tree.get_children():
                self.online_users_tree.item(iid, open=self.online_users_button_collapse.state)

        self.online_users_button_collapse = ttk.Button(
            self.online_users_label_frame, text="\u00B1", width=2
        )
        self.online_users_button_collapse.state = True
        self.online_users_button_collapse.config(command=collapse_cmd)
        self.online_users_button_collapse.grid(row=0, column=2, sticky=tk.E)
        self.online_users_button_collapse.config(state=tk.DISABLED)

        self.online_users_label_frame.columnconfigure(0, weight=1)

        # Online users list/tree and scrollbar
        self.online_users_list_frame = ttk.Frame(self.online_users_frame)
        self.online_users_list_frame.pack(fill=tk.BOTH, expand=True)

        self.online_users_tree = ttk.Treeview(
            self.online_users_list_frame, columns=(), show="tree", selectmode="browse"
        )

        def add_user(user, group, name, last_name):
            users = list(self.online_users_tree.get_children())
            # Early exit if user is already in the list with the same group
            for existing_user in users:
                if existing_user == user:
                    existing_group = (
                        self.online_users_tree.item(existing_user, "text").split(" (")[-1].rstrip(")")
                    )
                    if existing_group == group:
                        logging.exception(
                            f"user {user} already exists in the list with the same group!"
                        )
                        return False
                    else:
                        # Update the group if it has changed
                        self.online_users_tree.item(existing_user, text=f"{user} ({group})")
                        return True
            # Sort the new list of users so we can add the new user in the right position
            users.append(user)
            users.sort()
            user_text = f"{user} ({group})"
            self.online_users_tree.insert("", users.index(user), user, text=user_text)
            space = " " if (name and last_name) else ""
            fullname_str = f"{name}{space}{last_name}" if (name or last_name) else ""
            if fullname_str:
                self.online_users_tree.insert(user, "end", text=fullname_str)
            # Expand/collapse the newly added item according to the collapse button state
            self.online_users_tree.item(user, open=self.online_users_button_collapse.state)
            return True

        def delete_user(user):
            if user not in self.online_users_tree.get_children():
                logging.exception(f"user {user} doesn't exist in the list!")
                return False
            self.online_users_tree.delete(user)
            return True

        self.online_users_tree.add_user = add_user  # type: ignore[attr-defined]
        self.online_users_tree.delete_user = delete_user  # type: ignore[attr-defined]

        self.online_users_tree.heading("#0", text="User")
        self.online_users_tree.column("#0", width=200)

        # Only allow selecting users from the tree (not their optional details)
        self.online_users_tree.selection_prev = None

        def on_select(event):
            selected_item = self.online_users_tree.selection()
            if selected_item:
                if selected_item[0] == self.online_users_tree.selection_prev:
                    # De-selected a user
                    self.online_users_tree.selection_remove(selected_item[0])
                    self.online_users_tree.selection_prev = None
                else:
                    # Selected a user item or its subitem
                    parent = self.online_users_tree.parent(selected_item[0])
                    if parent:
                        # Selected a sub-item: restore previous selection
                        to_select = self.online_users_tree.selection_prev
                        to_select = "" if to_select is None else to_select
                        self.online_users_tree.selection_prev = None
                        self.online_users_tree.selection_set(to_select)
                    else:
                        # Selected a user item
                        self.online_users_tree.selection_prev = selected_item[0]
            else:
                self.online_users_tree.selection_prev = None

        self.online_users_tree.bind("<<TreeviewSelect>>", on_select)
        self.online_users_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.online_users_scrollbar = ttk.Scrollbar(
            self.online_users_list_frame, orient="vertical", command=self.online_users_tree.yview
        )
        self.online_users_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.online_users_tree.config(yscrollcommand=self.online_users_scrollbar.set)

    # ------------------------------------------------------------------
    # Key bindings
    # ------------------------------------------------------------------

    def _bind_ctrl_backspace(self):
        """Bind Ctrl+Backspace to delete word for entry widgets."""

        def delete_word(event):
            widget = event.widget
            index = widget.index(tk.INSERT)
            text = widget.get()
            # Find the start of the word
            while index > 0 and text[index - 1] == " ":
                index -= 1
            while index > 0 and text[index - 1] != " ":
                index -= 1
            widget.delete(index, tk.INSERT)
            return "break"

        for entry in self.entry_widgets.values():
            entry.bind("<Control-BackSpace>", delete_word)
        self.message_input.bind("<Control-BackSpace>", delete_word)

    def _bind_enter(self):
        """Bind Enter key to the join button command for entry widgets."""
        for entry in self.entry_widgets.values():
            entry.bind("<Return>", lambda event: self.join_button.invoke())

    # ------------------------------------------------------------------
    # Search / highlight functionality
    # ------------------------------------------------------------------

    def _search_messages(self):
        """Highlight all occurrences of the search term in the message board."""

        term = self.search_entry.get().strip()
        self.message_text.config(state=tk.NORMAL)
        self.message_text.tag_remove("search_highlight", "1.0", tk.END)

        if not term:
            self.message_text.config(state=tk.DISABLED)
            return

        start_pos = "1.0"
        while True:
            idx = self.message_text.search(term, start_pos, tk.END, nocase=True)
            if not idx:
                break

            end_pos = f"{idx}+{len(term)}c"
            self.message_text.tag_add("search_highlight", idx, end_pos)
            start_pos = end_pos

        self.message_text.tag_config("search_highlight", background="yellow")
        self.message_text.config(state=tk.DISABLED)

    def _clear_search(self):
        """Remove all search highlights from the message board."""
        self.message_text.config(state=tk.NORMAL)
        self.message_text.tag_remove("search_highlight", "1.0", tk.END)
        self.message_text.config(state=tk.DISABLED)
        self.search_entry.delete(0, tk.END)

    # ------------------------------------------------------------------
    # Multimedia helpers
    # ------------------------------------------------------------------

    def _choose_file_and_send(self):
        """Open OS dialog, then ask app to send the chosen file."""

        file_path = filedialog.askopenfilename(
            title="Select file to send",
            filetypes=[
                (
                    "Images and videos",
                    ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp",
                    "*.mp4", "*.mov", "*.avi", "*.mkv"),
                ),
                ("Images", ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp")),
                ("Videos", ("*.mp4", "*.mov", "*.avi", "*.mkv")),
                ("All files", "*"),
            ],
        )
        if not file_path:
            return

        # Destination: selected user if any, otherwise current group
        sel = self.online_users_tree.selection()
        if sel:
            # item text is "user (group)" → take the user part before space
            text = self.online_users_tree.item(sel[0], "text")
            destination = text.split(" ")[0]
        else:
            destination = self.group_entry.get()

        self.app._send_file(destination, file_path)

    def insert_image(self, file_path: str):
        """Insert an inline image into the message board."""
        try:
            img = tk.PhotoImage(file=file_path)
        except Exception as e:
            logging.warning(f"Could not load image {file_path}: {e}")
            self.message_text.append_line(f"[image: {os.path.basename(file_path)}]")
            return

        self._image_refs.append(img)
        self.message_text.config(state=tk.NORMAL)
        self.message_text.image_create(tk.END, image=img)
        self.message_text.insert(tk.END, "\n")
        self.message_text.see(tk.END)
        self.message_text.config(state=tk.DISABLED)

    def insert_file_link(self, label: str, file_path: str):
        """Insert clickable text that opens the file with the OS viewer."""

        tag = f"file_link_{len(self._file_links)}"
        self._file_links[tag] = file_path

        def open_file(event, tag_name=tag):
            path = self._file_links.get(tag_name)
            if not path:
                return
            try:
                if sys.platform.startswith("win"):
                    os.startfile(path)  # type: ignore[attr-defined]
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["xdg-open", path])
            except Exception as e:
                messagebox.showerror("Open file", f"Could not open file:\n{e}")

        self.message_text.config(state=tk.NORMAL)
        self.message_text.insert(tk.END, label + "\n", (tag, "file_link_style"))
        self.message_text.tag_config("file_link_style", foreground="blue", underline=True)
        self.message_text.tag_bind(tag, "<Button-1>", open_file)
        self.message_text.see(tk.END)
        self.message_text.config(state=tk.DISABLED)
