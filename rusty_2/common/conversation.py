"""Conversation management with observer pattern support."""

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from .messages import message_from_dict


@runtime_checkable
class ConversationObserver(Protocol):
    """
    Protocol for objects that observe conversation updates.
    
    Observers are notified whenever a new message is appended to a conversation.
    """
    
    def update(self, message: dict) -> None:
        """
        Called when a new message is added to the conversation.
        
        Args:
            message: The message dictionary that was added
        """
        ...


class Conversation:
    """
    Manages an ordered list of chat messages with observer support.
    
    This class maintains a conversation transcript as a list of messages
    and notifies registered observers when new messages are added.
    """
    
    def __init__(self, messages: list[dict] | None = None):
        """
        Initialize a new conversation.
        
        Args:
            messages: Optional initial list of messages
        """
        self._messages: list[dict] = []
        self._observers: list[ConversationObserver] = []
        
        if messages:
            for msg in messages:
                self.append(msg)
    
    def append(self, *messages: dict) -> None:
        """
        Append one or more messages to the conversation.
        
        Messages are added in order and all registered observers
        are notified for each message.
        
        Args:
            *messages: One or more message dictionaries to append
            
        Raises:
            ValueError: If any message is invalid
        """
        for message in messages:
            # Validate and normalize message structure
            normalized_message = message_from_dict(message)
            
            self._messages.append(normalized_message)
            
            # Notify all observers
            for observer in self._observers:
                try:
                    observer.update(normalized_message)
                except Exception:
                    # Don't let observer errors break the append operation
                    pass
    
    @property
    def messages(self) -> list[dict]:
        """
        Get a read-only copy of the conversation messages.
        
        Returns:
            list[dict]: A copy of the messages list
        """
        return self._messages.copy()
    
    def register_observer(self, observer: ConversationObserver) -> None:
        """
        Register an observer to be notified of new messages.
        
        Args:
            observer: An object implementing the ConversationObserver protocol
        """
        if observer not in self._observers:
            self._observers.append(observer)
    
    def unregister_observer(self, observer: ConversationObserver) -> None:
        """
        Unregister an observer from receiving notifications.
        
        Args:
            observer: The observer to remove
        """
        if observer in self._observers:
            self._observers.remove(observer)
    
    def to_json(self) -> str:
        """
        Serialize the conversation to a JSON string.
        
        Returns:
            str: JSON representation of the conversation
        """
        return json.dumps(self._messages, indent=2, ensure_ascii=False)
    
    def to_bytes(self) -> bytes:
        """
        Serialize the conversation to bytes.
        
        Returns:
            bytes: UTF-8 encoded JSON representation
        """
        return self.to_json().encode("utf-8")
    
    def save(self, path: str | Path) -> None:
        """
        Save the conversation to a file.
        
        Args:
            path: File path where to save the conversation
        """
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(self.to_json(), encoding="utf-8")
    
    @classmethod
    def from_json(cls, text: str) -> "Conversation":
        """
        Create a Conversation from a JSON string.
        
        Args:
            text: JSON string containing message list
            
        Returns:
            Conversation: New conversation instance with loaded messages
            
        Raises:
            json.JSONDecodeError: If the JSON is invalid
        """
        messages = json.loads(text)
        if not isinstance(messages, list):
            raise ValueError("JSON must contain a list of messages")
        return cls(messages=messages)
    
    @classmethod
    def load(cls, path: str | Path) -> "Conversation":
        """
        Load a Conversation from a file.
        
        Args:
            path: File path to load from
            
        Returns:
            Conversation: New conversation instance with loaded messages
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            json.JSONDecodeError: If the file contains invalid JSON
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Conversation file not found: {file_path}")
        
        text = file_path.read_text(encoding="utf-8")
        return cls.from_json(text)

