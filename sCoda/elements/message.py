import enum


class MessageType(enum.Enum):
    meta = "meta"
    control_change = "control_change"
    note_on = "note_on"
    note_off = "note_off"
    wait = "wait"


class MetaMessageType(enum.Enum):
    time_signature = "time_signature"


class Message:
    """
    Class representing a musical message.
    """

    def __init__(self) -> None:
        super().__init__()
        self._message_type = None
        self._note = None
        self._velocity = None
        self._control = None
        self._value = None
        self._numerator = None
        self._denominator = None
