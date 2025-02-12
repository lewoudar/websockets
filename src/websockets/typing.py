from __future__ import annotations

import logging
from typing import List, NewType, Optional, Tuple, Union


__all__ = [
    "Data",
    "LoggerLike",
    "Origin",
    "Subprotocol",
    "ExtensionName",
    "ExtensionParameter",
]


# Public types used in the signature of public APIs

Data = Union[str, bytes]
Data.__doc__ = """
Types supported in a WebSocket message:

- :class:`str` for text messages;
- :class:`bytes` for binary messages.
"""


LoggerLike = Union[logging.Logger, logging.LoggerAdapter]
LoggerLike.__doc__ = """Types accepted where :class:`~logging.Logger` is expected."""


Origin = NewType("Origin", str)
Origin.__doc__ = """Value of a Origin header."""


Subprotocol = NewType("Subprotocol", str)
Subprotocol.__doc__ = """Subprotocol in a Sec-WebSocket-Protocol header."""


ExtensionName = NewType("ExtensionName", str)
ExtensionName.__doc__ = """Name of a WebSocket extension."""


ExtensionParameter = Tuple[str, Optional[str]]
ExtensionParameter.__doc__ = """Parameter of a WebSocket extension."""


# Private types

ExtensionHeader = Tuple[ExtensionName, List[ExtensionParameter]]
ExtensionHeader.__doc__ = """Extension in a Sec-WebSocket-Extensions header."""


ConnectionOption = NewType("ConnectionOption", str)
ConnectionOption.__doc__ = """Connection option in a Connection header."""


UpgradeProtocol = NewType("UpgradeProtocol", str)
UpgradeProtocol.__doc__ = """Upgrade protocol in an Upgrade header."""
