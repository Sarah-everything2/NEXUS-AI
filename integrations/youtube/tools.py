"""YouTube tools with mandatory human approval."""
from integrations.youtube.manager import status, channel, publishing_controls
from integrations.youtube.upload import upload_video
from tools.approval import approve_tool_call


def youtube_status():
    return status()


def youtube_channel():
    return channel()


def youtube_controls():
    return publishing_controls()


def youtube_upload(**kwargs):
    arguments = dict(kwargs)
    arguments.pop("approved", None)

    if not isinstance(arguments.get("made_for_kids"), bool):
        raise ValueError("Explicit made_for_kids declaration required.")

    if not approve_tool_call("youtube_upload", arguments):
        return "YouTube upload cancelled. Permission denied."

    return upload_video(**arguments, approved=True)

def youtube_upload_autonomous(**kwargs):
    """Autonomous YouTube uploads restricted to private visibility."""
    from integrations.youtube.upload import upload_video_autonomous

    kwargs.pop("approved", None)
    kwargs.pop("privacy_status", None)
    return upload_video_autonomous(**kwargs)
