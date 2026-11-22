"""Read-only YouTube tools for the NEXUS tool manager."""
from integrations.youtube.manager import status, channel, publishing_controls


def youtube_status():
    return status()


def youtube_channel():
    return channel()


def youtube_controls():
    return publishing_controls()
