import rti.connextdds as dds

from chat import ChatUser, ChatMessage

import os
import threading
from typing import Callable, List
import logging

from dataclasses import field
from typing import Union, Sequence, Optional
import rti.idl as idl
import rti.rpc as rpc
from enum import IntEnum
from persistence import MessageStore
import sys
import os
from abc import ABC

import gui

MAX_NAME_SIZE = 128

MAX_MSG_SIZE = 512

class Handlers:
    users_joined: Callable[[List[ChatUser]], None] = lambda *_: logging.warning("Not implemented")
    users_dropped: Callable[[List[ChatUser]], None] = lambda *_: logging.warning("Not implemented")
    message_received: Callable[[List[ChatMessage]], None] = lambda *_: logging.warning("Not implemented")



class DDSApp:
    """DDS application for chat messaging, to be driven from the application code."""

    TOPIC_NAME_USER = "userInfo"
    TOPIC_NAME_MSG = "message"
    QOS_PROVIDER_XML = os.path.join(os.path.dirname(__file__), "chat_qos.xml")
    QOS_LIBRARY = "Chat_Library"
    QOS_PROFILE_USER = "ChatUser_Profile"
    QOS_PROFILE_MSG = "ChatMessage_Profile"

    def __init__(self, user : ChatUser, handlers=Handlers(), auto_join=True, domain_id=0):
        """Public API: create the DDS application with the provided user and handlers."""
        
        self.user = user

        # App-level log for SEARCH (shared with no-RTI): chat.db
        self.store = MessageStore('chat.db')

        self.message = ChatMessage()
        self.message.fromUser = self.user.username
        
        self.handlers = handlers

        self.participant = None

        self.participant = dds.DomainParticipant(domain_id)

        # QoS provider using custom xml file
        self.qos_provider = dds.QosProvider(self.QOS_PROVIDER_XML)

        self.stop_condition = dds.GuardCondition()

        # ChatUser
        self.topic_user = dds.Topic(self.participant, self.TOPIC_NAME_USER, ChatUser)
        qos_profile_user_str = f"{self.QOS_LIBRARY}::{self.QOS_PROFILE_USER}"
        self.writer_user = dds.DataWriter(self.topic_user, qos=self.qos_provider.datawriter_qos_from_profile(qos_profile_user_str))
        self.reader_user = dds.DataReader(self.topic_user, qos=self.qos_provider.datareader_qos_from_profile(qos_profile_user_str))
        self.readcond_user = dds.ReadCondition(self.reader_user, 
                                                dds.DataState(dds.SampleState.NOT_READ, 
                                                              dds.ViewState.ANY, 
                                                              dds.InstanceState.ANY) )
        self.waitset_user = dds.WaitSet()
        self.waitset_user.attach_condition(self.stop_condition)
        self.waitset_user.attach_condition(self.readcond_user)

        self.thread_user = threading.Thread(target=self._user_monitor, daemon=True)
        self.thread_user.start()

        # ChatMessage
        self.topic_msg = dds.Topic(self.participant, self.TOPIC_NAME_MSG, ChatMessage)
        qos_profile_msg_str = f"{self.QOS_LIBRARY}::{self.QOS_PROFILE_MSG}"

        self.pub_msg = dds.Publisher(self.participant)
        self._set_partition(self.pub_msg, self.user.group)
        self.writer_msg = dds.DataWriter(self.pub_msg, self.topic_msg, qos=self.qos_provider.datawriter_qos_from_profile(qos_profile_msg_str))

        self.sub_msg = dds.Subscriber(self.participant)
        self._set_partition(self.sub_msg, self.user.group)
        
        filter_expression = "toUser = %0 OR toGroup = %1"
        filter_parameters = [f"'{self.user.username}'", f"'{self.user.group}'"]
        self.reader_cft = dds.ContentFilteredTopic(
            self.topic_msg,
            "FilterByUsernameOrGroup",
            dds.Filter(filter_expression, filter_parameters)
        )
        self.reader_msg = dds.DataReader(self.sub_msg, self.reader_cft, qos=self.qos_provider.datareader_qos_from_profile(qos_profile_msg_str))

        self.readcond_msg = dds.ReadCondition(self.reader_msg, dds.DataState())
        self.waitset_msg = dds.WaitSet()
        self.waitset_msg.attach_condition(self.stop_condition)
        self.waitset_msg.attach_condition(self.readcond_msg)

        self.thread_msg = threading.Thread(target=self._message_monitor, daemon=True)
        self.thread_msg.start()

        # Publish our user as joining the domain
        if auto_join:
            self.user_join()
    

    def user_join(self):
        """Public API: write the user topic with our details."""

        self.writer_user.write(self.user)
    

    def user_update_group(self, group):
        """Public API: update the User group and the partition for the Message topic."""

        self.user.group = group

        # Unregister or dispose of the old instance
        old_instance_handle = self.writer_msg.lookup_instance(self.message)
        if old_instance_handle:
            self.writer_msg.dispose_instance(old_instance_handle)
            self.writer_msg.unregister_instance(old_instance_handle)

        # Update the partition for the Message topic
        self._set_partition(self.pub_msg, self.user.group)
        self._set_partition(self.sub_msg, self.user.group)

        # Update the filter parameters for the ContentFilteredTopic
        self.reader_cft.filter_parameters = [f"'{self.user.username}'", f"'{self.user.group}'"]
        
        # Re-register the user with the new group
        self.writer_user.write(self.user)


    def user_list(self):
        """Public API: return the list of user samples in the reader queue."""

        return self.reader_user.read_data()


    def message_send(self, destination, message):
        """Public API: write the Message topic with our + provided details."""

        self.message.toUser = destination
        self.message.toGroup = destination
        self.message.message = message
        self.writer_msg.write(self.message)
        # Log to chat.db for search parity with no-RTI
        try:
            fn = getattr(self.user, 'firstName', '') or ''
            ln = getattr(self.user, 'lastName', '') or ''
            self.store.save(direction='out', from_user=self.user.username,
                            first_name=fn, last_name=ln,
                            grp=self.user.group, text=message)
        except Exception as e:
            logging.debug(f'chat.db save(out) failed: {e}')
    

    def user_leave(self):
        """Public API: graceful exit when leaving the chat and deleting the application."""

        # Early exit if already closed
        if self.participant.closed:
            return
        
        # Send unregister for own user
        instance_handle = self.writer_user.lookup_instance(self.user)
        self.writer_user.unregister_instance(instance_handle)

        # Trigger guard condition so waitset threads can finish
        self.stop_condition.trigger_value = True
        # Wait until waitset threads are fully done
        self.thread_user.join()
        self.thread_msg.join()
        # Detach any remaining conditions
        self.waitset_user.detach_all()
        self.waitset_msg.detach_all()
        # Close entities and participant 
        self.participant.close_contained_entities()
        self.participant.close()
    

    def _set_partition(self, pubsub, partition_name):
        """Private API: helper method - set partition name for a Publisher or Subscriber."""

        qos = pubsub.qos
        qos.partition.name = [partition_name]
        pubsub.qos = qos
    

    def _user_monitor(self):
        """Private API: dedicated thread target for subscribing to updates on the user topic."""

        while True:
            active_conditions = self.waitset_user.wait(dds.Duration(1))

            for cond in active_conditions:
                if cond == self.stop_condition:
                    return

                if cond == self.readcond_user:
                    # Read any new users that we have not seen before and run the installed handler
                    state = dds.DataState(dds.SampleState.NOT_READ, dds.ViewState.ANY, dds.InstanceState.ALIVE)
                    new_samples = self.reader_user.select().state(state).read_data()
                    if new_samples:
                        self.handlers.users_joined(new_samples)

                    # Take any users that have unregistered (dropped) to remove them from the user_list and run the installed handler
                    dropped_samples = self.reader_user.select().state(dds.InstanceState.NOT_ALIVE_MASK).take_data()
                    if dropped_samples:
                        self.handlers.users_dropped(dropped_samples)


    def _message_monitor(self):
        """Private API: dedicated thread target for updates on the ChatMessage topic."""

        while True:
            active_conditions = self.waitset_msg.wait(dds.Duration(1))

            for cond in active_conditions:
                if cond == self.stop_condition:
                    return

                if cond == self.readcond_msg:
                    # Take any new messages that we have not seen before
                    samples = self.reader_msg.take_data()
                    # Mirror into chat.db for search (no-RTI parity)
                    try:
                        for s in samples:
                            fn = ''
                            ln = ''
                            txt = getattr(s, 'message', '')
                            grp = getattr(s, 'toGroup', '') or self.user.group
                            frm = getattr(s, 'fromUser', '')
                            if txt and grp and frm:
                                self.store.save(direction='in', from_user=frm,
                                                first_name=fn, last_name=ln,
                                                grp=grp, text=txt)
                    except Exception as e:
                        logging.debug(f'chat.db save(in) failed: {e}')
                    # Run the installed handler to report back the samples
                    self.handlers.message_received(samples)



@idl.struct(

    member_annotations = {
        'username': [idl.key, idl.bound(MAX_NAME_SIZE),],
        'group': [idl.bound(MAX_NAME_SIZE),],
        'firstName': [idl.bound(MAX_NAME_SIZE),],
        'lastName': [idl.bound(MAX_NAME_SIZE),],
    }
)
class ChatUser:
    username: str = ""
    group: str = ""
    firstName: Optional[str] = None
    lastName: Optional[str] = None

@idl.struct(

    member_annotations = {
        'fromUser': [idl.key, idl.bound(MAX_NAME_SIZE),],
        'toUser': [idl.key, idl.bound(MAX_NAME_SIZE),],
        'toGroup': [idl.key, idl.bound(MAX_NAME_SIZE),],
        'message': [idl.bound(MAX_MSG_SIZE),],
    }
)
class ChatMessage:
    fromUser: str = ""
    toUser: str = ""
    toGroup: str = ""
    message: str = ""

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
        self.gui = gui.GuiApp(self.gui_handlers)
        
        # DDS App and bindings
        self.dds_user = None
        self.dds_handlers = Handlers()
        self.dds_handlers.users_joined = self.joined
        self.dds_handlers.users_dropped = self.left
        self.dds_handlers.message_received = self.received
        self.dds_app = None

        # Start the GUI
        self.gui.start()

        # If the GUI is closed, clean-up
        self.leave()
    

    def join(self, user, group, name, last_name):
        """Join the chat with the provided details."""

        self.dds_user = ChatUser(username=user, group=group, firstName=name, lastName=last_name)
        self.dds_app = DDSApp(self.dds_user, self.dds_handlers)
    

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
    

    def received(self, message_samples):
        """A message was received, update the GUI."""

        # Note toUser and toGroup have the same data
        messages = [[s.fromUser, s.toUser, s.message] for s in message_samples]
        for msg in messages:
            self.gui.message_received(*msg)



def test():
    app = MainApp()
    app.join("testuser", "services", "", "")
    return app


def main():
    app = MainApp()
    return app



if __name__ =="__main__":
    app = main()