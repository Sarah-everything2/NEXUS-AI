from integrations.xmrig import client
from tools.approval import approve_tool_call


def xmrig_status():
    return client.status()


def xmrig_health():
    return client.health()


def xmrig_logs(lines=30):
    return client.logs(lines)


def xmrig_configure_pool(url, wallet, algorithm, password="x", tls=False):
    args = {"pool": url, "wallet_provided": bool(wallet), "algorithm": algorithm, "tls": bool(tls)}
    if not approve_tool_call("xmrig_configure_pool", args):
        return "Pool configuration cancelled."
    return client.configure_pool(url, wallet, algorithm, password, tls)


def xmrig_start():
    if not approve_tool_call("xmrig_start", {}):
        return "Mining start cancelled."
    from integrations.xmrig.mining_intelligence import run_cycle
    return run_cycle()


def xmrig_stop():
    return client.stop()


def xmrig_recovery_check():
    return client.recovery_check()
