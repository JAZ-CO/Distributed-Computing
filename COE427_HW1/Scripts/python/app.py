import logging
import os
import time
import gui
import dds_app



class MainApp:
    """Main application, simple bridging between the the DDS chat application and the GUI."""

    def __init__(self):
        "Initialise the GUI and DDS application, and bind the handlers."
        
        # Initialise GUI and bindings
        self.gui_handlers = gui.Handlers()
        self.gui_handlers.join = self.join
        self.gui_handlers.update_user = self.update_user
        self.gui_handlers.leave = self.leave
        self.gui_handlers.list_users = self.list_users
        self.gui_handlers.send_message = self.send
        self.gui_handlers.send_file = self.send_file
        self.gui = gui.GuiApp(self.gui_handlers)
        
        # DDS App and bindings
        self.dds_user = None
        self.dds_handlers = dds_app.Handlers()
        self.dds_handlers.users_joined = self.joined
        self.dds_handlers.users_dropped = self.left
        self.dds_handlers.message_received = self.received
        self.dds_handlers.file_received = self.received_file
        self.dds_app = None

        # Start the GUI
        self.gui.start()

        # If the GUI is closed, clean-up
        self.leave()
    

    def join(self, user, group, name, last_name):
        """Join the chat with the provided details."""

        self.dds_user = dds_app.ChatUser(username=user, group=group, firstName=name, lastName=last_name)
        self.dds_app = dds_app.DDSApp(self.dds_user, self.dds_handlers)
    

    def update_user(self, group):
        """Update the user group."""

        # Early exit if not set up previously
        if not self.dds_app:
            return

        # Update the user group in the DDS application
        self.dds_app.user_update_group(group=group)
    

    def leave(self):
        """Leave the chat and clean up the DDS application."""

        # Early exit if not set up previously
        if not self.dds_app:
            return

        self.dds_app.user_leave()
    
    
    def list_users(self):
        """List all users in the chat."""

        # Early exit if not set up previously
        if not self.dds_app:
            return

        user_samples = self.dds_app.user_list()
        users = [[s.username, s.group, s.firstName, s.lastName] for s in user_samples]
        return users
    

    def joined(self, user_samples):
        """User joined the chat, update the GUI."""
        
        users = [[s.username, s.group, s.firstName, s.lastName] for s in user_samples]
        for user in users:
            self.gui.user_joined(*user)
    

    def left(self, user_samples):
        """User left the chat, update the GUI."""

        for user in user_samples:
            if user.username == self.dds_user.username:
                continue
            self.gui.user_left(user.username)
    

    def send(self, destination, message):
        """Send a message to the provided destination (user or group)."""

        # Early exit if not set up previously
        if not self.dds_app:
            return

        self.dds_app.message_send(destination=destination, message=message)

    def send_file(self, destination, file_path):
        """Called by GUI when user chooses a file to send."""
        if not self.dds_app:
            return
        self.dds_app.file_send(destination, file_path)

    def received_file(self, file_samples):
        """FileMessage(s) received from DDS; only show those meant for this user/group."""

        if not self.dds_user:
            return

        my_user = self.dds_user.username
        my_group = self.dds_user.group

        downloads_dir = os.path.join(os.path.dirname(__file__), "downloads")
        os.makedirs(downloads_dir, exist_ok=True)

        for s in file_samples:
            # Destination string
            dest = s.toUser or s.toGroup

            # Skip files not meant for me or my group (and that I didn't send)
            if dest and dest not in (my_user, my_group) and s.fromUser != my_user:
                continue

            # Save the file locally
            data_bytes = bytes(s.data)
            ts = int(time.time() * 1000)
            safe_name = f"{s.fromUser}_{ts}_{s.fileName}"
            dest_path = os.path.join(downloads_dir, safe_name)

            try:
                with open(dest_path, "wb") as f:
                    f.write(data_bytes)
            except Exception as e:
                logging.exception(f"Failed to save received file {s.fileName}: {e}")
                continue

            # Tell the GUI to display it (inline image or clickable link)
            self.gui.file_received(s.fromUser, dest, dest_path, s.mimeType)


    def received(self, message_samples):
        """A message was received from DDS; only show those meant for this user/group."""

        if not self.dds_user:
            return

        my_user = self.dds_user.username
        my_group = self.dds_user.group

        for s in message_samples:
            # Destination string – in this app toUser and toGroup carry the same value
            dest = s.toUser or s.toGroup

            # If the destination is something else (other user / other group)
            # and I'm not the sender, skip it.
            if dest and dest not in (my_user, my_group) and s.fromUser != my_user:
                continue

            # At this point, the message is:
            #  - to me (DM), or
            #  - to my group, or
            #  - sent by me.
            self.gui.message_received(s.fromUser, dest, s.message)






def test():
    app = MainApp()
    app.join("testuser", "services", "", "")
    return app


def main():
    app = MainApp()
    return app



if __name__ =="__main__":
    app = main()