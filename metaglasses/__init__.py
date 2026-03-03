"""
metaglasses — Python SDK for Ray-Ban Meta Smart Glasses (Generation 2)

Quick start::

    from metaglasses import Glasses

    glasses = Glasses()
    glasses.connect()
    print(glasses.status())
    glasses.disconnect()
"""

from .glasses import Glasses, GlassesConnectionError, GlassesNotConnectedError
from .media import MediaManager, Photo, Video
from .voice import VoiceCommandHandler
from .ai import MetaAIClient

__version__ = "0.1.0"
__all__ = [
    "Glasses",
    "GlassesConnectionError",
    "GlassesNotConnectedError",
    "MediaManager",
    "Photo",
    "Video",
    "VoiceCommandHandler",
    "MetaAIClient",
]
