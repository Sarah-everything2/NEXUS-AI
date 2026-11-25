"""Read-only X account tools for NEXUS AI."""

from integrations.x_platform.client import NexusXClient
from integrations.x_platform.secure_storage import token_status


def x_status():
    return token_status()


def x_account():
    client = NexusXClient()
    try:
        return client.verify_account()
    finally:
        client.close()


def x_analytics():
    client = NexusXClient()
    try:
        result = client.client.get_me(
            user_fields=["public_metrics"],
            user_auth=False,
        )
        if not result.data:
            return {"ok": False, "error": "Unable to retrieve X account metrics."}

        return {
            "ok": True,
            "username": result.data.username,
            "metrics": result.data.public_metrics or {},
            "scope": "Public account metrics only",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        client.close()


def x_search_trends(query, max_results=20):
    client = NexusXClient()
    try:
        return client.search_recent(query, max_results)
    finally:
        client.close()


def x_account_timeline(max_results=20):
    client = NexusXClient()
    try:
        return client.account_timeline(max_results)
    finally:
        client.close()


from tools.approval import approve_tool_call


def x_post(text):
    approved = approve_tool_call("x_post", {"text": text})
    if not approved:
        return {"ok": False, "published": False, "error": "Approval denied."}

    client = NexusXClient()
    try:
        return client.post_text(text, approved=True)
    finally:
        client.close()


def x_thread(posts):
    approved = approve_tool_call("x_thread", {"posts": posts})
    if not approved:
        return {"ok": False, "published": False, "error": "Approval denied."}

    client = NexusXClient()
    try:
        return client.post_thread(posts, approved=True)
    finally:
        client.close()
