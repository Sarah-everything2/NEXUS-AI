"""Central intelligence cycle for multi-coin mining."""

import time

from integrations.xmrig import (
    network_discovery,
    price_feed,
    performance_monitor,
    hardware_monitor,
    coin_selector,
)


def collect_opportunities():
    report = {
        "timestamp": time.time(),
        "status": "INCOMPLETE",
        "opportunities": [],
        "errors": [],
    }

    try:
        network_discovery.discover()
        networks = network_discovery.get_networks()
        if not networks:
            raise RuntimeError("No fresh network data")
    except Exception as exc:
        report["errors"].append("network:" + type(exc).__name__)
        return report

    try:
        price_feed.refresh()
        prices = price_feed.get_prices()
        if not prices:
            raise RuntimeError("No fresh coin prices")
    except Exception as exc:
        report["errors"].append("prices:" + type(exc).__name__)
        return report

    try:
        performance = performance_monitor.collect()
    except Exception as exc:
        report["errors"].append("performance:" + type(exc).__name__)
        return report

    try:
        hardware = hardware_monitor.collect()
        if not hardware.get("telemetry_complete"):
            raise RuntimeError("Incomplete hardware telemetry")
    except Exception as exc:
        report["errors"].append("hardware:" + type(exc).__name__)
        return report

    report["opportunities"] = (
        coin_selector.build_measured_opportunities(
            networks,
            prices,
            performance,
            hardware,
        )
    )
    report["status"] = (
        "READY" if report["opportunities"] else "NO_VALID_OPPORTUNITIES"
    )
    report["hardware"] = hardware
    report["performance"] = performance
    return report


def run_cycle(electricity_price_per_kwh=0):
    from integrations.xmrig.autopilot import run_cycle as run_autopilot

    intelligence = collect_opportunities()

    if intelligence["status"] != "READY":
        return {
            "status": "BLOCKED",
            "intelligence": intelligence,
            "execution_authorized": False,
        }

    result = run_autopilot(
        opportunities=intelligence["opportunities"],
        electricity_price_per_kwh=electricity_price_per_kwh,
        hardware=intelligence["hardware"],
    )

    return {
        "status": result.get("status", "COMPLETED"),
        "intelligence": intelligence,
        "autopilot": result,
    }
