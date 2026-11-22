import argparse
import time
from integrations.xmrig import client


def monitor(interval=60):
    print("NEXUS XMRig Monitor Started")
    print("Interval:", interval, "seconds")
    print("Automatic mining/restarts: DISABLED")

    while True:
        try:
            health = client.health()
            recovery = client.recovery_check()

            print({
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "mining": health.get("status"),
                "available_ram_gb": health.get("available_ram_gb"),
                "recovery": recovery.get("status")
            })

        except Exception as exc:
            print("MONITOR ERROR:", str(exc))

        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    if args.once:
        print("STATUS:", client.status())
        print("HEALTH:", client.health())
        print("RECOVERY:", client.recovery_check())
    else:
        monitor(max(10, args.interval))
