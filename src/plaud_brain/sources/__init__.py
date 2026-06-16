"""Audio sources: where recordings come from (cloud, USB)."""

from plaud_brain.sources.base import AudioSource
from plaud_brain.sources.cloud import CloudSource
from plaud_brain.sources.usb import UsbSource

__all__ = ["AudioSource", "CloudSource", "UsbSource"]
