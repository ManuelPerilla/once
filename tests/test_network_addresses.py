"""LAN discovery uses local adapters and treats private addresses as candidates only."""

import json
import socket
import subprocess

import pytest

from scripts import network_addresses as network


def route(monkeypatch, address):
    monkeypatch.setattr(network, "_route_address", lambda system: address)


def test_windows_excludes_disconnected_and_virtual_adapters_and_prioritizes_route(monkeypatch):
    monkeypatch.setattr(network.platform, "system", lambda: "Windows")
    rows = [
        {
            "name": "Ethernet",
            "status": "Up",
            "addresses": ["192.168.50.8", "192.168.50.8", "169.254.3.2"],
        },
        {"name": "Wi-Fi", "status": "Disconnected", "addresses": ["192.168.1.20"]},
        {"name": "USB Ethernet", "status": "Up", "addresses": ["10.30.0.7"]},
        {"name": "vEthernet (WSL)", "status": "Up", "addresses": ["172.20.0.1"]},
        {
            "name": "Private connection",
            "description": "WireGuard Tunnel",
            "status": "Up",
            "addresses": ["10.8.0.2"],
        },
        {"name": "Adapter", "virtual": True, "status": "Up", "addresses": ["172.18.0.1"]},
    ]
    monkeypatch.setattr(network, "_command", lambda args: json.dumps(rows))
    route(monkeypatch, "192.168.50.8")
    assert network.discover_addresses() == ["192.168.50.8", "10.30.0.7"]


def test_linux_interface_inventory_and_routing_lookup(monkeypatch):
    monkeypatch.setattr(network.platform, "system", lambda: "Linux")
    observed = []
    rows = [
        {
            "ifname": name,
            "flags": ["UP"],
            "operstate": state,
            "addr_info": [{"family": "inet", "local": value} for value in addresses],
        }
        for name, state, addresses in [
            ("eth0", "UP", ["10.0.2.15"]),
            ("wlan0", "UP", ["192.168.0.15", "203.0.113.8"]),
            ("wlan1", "DOWN", ["192.168.10.12"]),
            ("docker0", "UP", ["172.17.0.1"]),
            ("tun0", "UNKNOWN", ["10.8.0.4"]),
        ]
    ]

    def command(args):
        observed.append(args)
        return (
            json.dumps([{"prefsrc": "192.168.0.15", "dev": "wlan0"}])
            if "route" in args
            else json.dumps(rows)
        )

    monkeypatch.setattr(network, "_command", command)
    assert network.discover_addresses() == ["192.168.0.15", "10.0.2.15"]
    assert ["ip", "-j", "-4", "route", "get", network.PROBE_DESTINATION] in observed


def test_macos_ifconfig_ignores_inactive_interfaces_and_tunnels(monkeypatch):
    monkeypatch.setattr(network.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        network,
        "_command",
        lambda args: (
            """
en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
    inet 192.168.2.9 netmask 0xffffff00 broadcast 192.168.2.255
    status: active
en1: flags=8863<UP,BROADCAST,RUNNING> mtu 1500
    inet 10.2.0.9 netmask 0xffffff00
    status: inactive
utun0: flags=8051<UP,POINTOPOINT,RUNNING,MULTICAST> mtu 1380
    inet 10.8.1.3 netmask 0xffffff00
"""
        ),
    )
    route(monkeypatch, "192.168.2.9")
    assert network.discover_addresses() == ["192.168.2.9"]


def test_missing_commands_fall_back_to_hostname_and_udp_route_without_sending(monkeypatch):
    monkeypatch.setattr(network.platform, "system", lambda: "Linux")
    monkeypatch.setattr(network, "_command", lambda args: None)
    calls = []

    class Probe:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def settimeout(self, seconds):
            assert seconds <= 1

        def connect(self, destination):
            calls.append(destination)

        def getsockname(self):
            return ("192.168.70.4", 45000)

    monkeypatch.setattr(network.socket, "socket", lambda *args: Probe())
    monkeypatch.setattr(network.socket, "gethostname", lambda: "once-machine")
    monkeypatch.setattr(
        network.socket,
        "getaddrinfo",
        lambda *args: [
            (socket.AF_INET, socket.SOCK_DGRAM, 17, "", (value, 0))
            for value in [
                "10.3.0.4",
                "192.168.70.4",
                "10.3.0.4",
                "127.0.0.1",
                "169.254.1.1",
                "8.8.8.8",
            ]
        ],
    )
    assert network.discover_addresses() == ["192.168.70.4", "10.3.0.4"]
    assert calls == [(network.PROBE_DESTINATION, 9)]


def test_known_vpn_route_does_not_return_via_fallback(monkeypatch):
    monkeypatch.setattr(network.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        network,
        "_command",
        lambda args: json.dumps(
            {
                "name": "VPN",
                "status": "Up",
                "addresses": ["10.8.0.2"],
            }
        ),
    )
    route(monkeypatch, "10.8.0.2")
    monkeypatch.setattr(
        network.socket,
        "getaddrinfo",
        lambda *args: pytest.fail("No fallback over authoritative inventory"),
    )
    assert network.discover_addresses() == []


@pytest.mark.parametrize("error", [FileNotFoundError(), subprocess.TimeoutExpired("ip", 5)])
def test_command_failures_are_tolerated(monkeypatch, error):
    def run(*args, **kwargs):
        assert kwargs["timeout"] == 5 and not kwargs.get("shell")
        raise error

    monkeypatch.setattr(network.subprocess, "run", run)
    assert network._command(["ip", "-j", "-4", "addr", "show", "up"]) is None


@pytest.mark.parametrize(
    "value",
    [
        "0.0.0.0",
        "127.0.0.1",
        "169.254.1.1",
        "224.0.0.1",
        "::1",
        "8.8.8.8",
        "192.0.2.1",
        "100.64.0.1",
        None,
        "garbage",
    ],
)
def test_only_rfc1918_addresses_are_candidates(value):
    assert network._private(value) is None
