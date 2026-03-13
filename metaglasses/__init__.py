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
from .apps import App, AppRunner
from .apps.pricing import PricingApp
from .apps.research import ResearchApp
from .apps.outreach import OutreachApp, OutreachItem
from .apps.livestream import LivestreamApp, Platform, StreamSession
from .apps.recorder import RecorderApp, Clip
from .apps.factory import QuickApp, quick_app
from .bridge import MobileBridge

__version__ = "0.2.0"
__all__ = [
    # Core
    "Glasses",
    "GlassesConnectionError",
    "GlassesNotConnectedError",
    "MediaManager",
    "Photo",
    "Video",
    "VoiceCommandHandler",
    "MetaAIClient",
    # Apps framework
    "App",
    "AppRunner",
    # Built-in apps
    "PricingApp",
    "ResearchApp",
    "OutreachApp",
    "OutreachItem",
    "LivestreamApp",
    "Platform",
    "StreamSession",
    "RecorderApp",
    "Clip",
    # Rapid app factory
    "QuickApp",
    "quick_app",
    # Mobile bridge
    "MobileBridge",
]
