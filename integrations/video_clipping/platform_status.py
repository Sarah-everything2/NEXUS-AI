from integrations.video_clipping.platform_adapters import account_readiness

def get_video_platform_status():
    return {
        name: account_readiness(name)
        for name in ("youtube", "tiktok", "instagram_reels")
    }
