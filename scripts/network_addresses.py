"""Discover private IPv4 LAN candidates; discovery never proves peer reachability."""

import ipaddress
import json
import platform
import re
import socket
import subprocess

PRIVATE_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
    )
)
PROBE_DESTINATION = "192.0.2.1"  # Routing lookup only; no UDP datagram is transmitted.
EXCLUDED = re.compile(
    r"docker|wsl|loopback|hyper-v|vethernet|virtualbox|vmware|vpn|wireguard|"
    r"tailscale|zerotier|anyconnect|fortinet|nordlynx|tap-windows|"
    r"^(?:lo\d*|utun\d*|tun\d*|tap\d*|wg\d*|veth\w*|virbr\w*|"
    r"vmnet\w*|vboxnet\w*|br-.+|awdl\d*|llw\d*|gif\d*|stf\d*|zt\w+)$",
    re.IGNORECASE,
)
WINDOWS_COMMAND = """
Get-NetIPConfiguration | Where-Object { $_.NetAdapter.Status -eq 'Up' } |
ForEach-Object {
    [PSCustomObject]@{
        name = $_.InterfaceAlias
        description = $_.InterfaceDescription
        status = $_.NetAdapter.Status
        virtual = $_.NetAdapter.Virtual
        addresses = @($_.IPv4Address.IPAddress)
    }
} | ConvertTo-Json -Depth 3 -Compress
""".strip()


def _command(arguments):
    try:
        result = subprocess.run(
            arguments,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if platform.system() == "Windows"
            else 0,
        )
        return result.stdout.lstrip("\ufeff")
    except (OSError, subprocess.SubprocessError):
        return None


def _json(arguments):
    raw = _command(arguments)
    if raw is None:
        return None
    try:
        value = json.loads(raw) if raw.strip() else []
        return [value] if isinstance(value, dict) else value if isinstance(value, list) else None
    except ValueError:
        return None


def _inventory(system):
    if system == "Windows":
        rows = _json(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", WINDOWS_COMMAND]
        )
        return (
            None
            if rows is None
            else [
                {**row, "up": str(row.get("status", "")).lower() == "up"}
                for row in rows
                if isinstance(row, dict)
            ]
        )
    if system == "Linux":
        rows = _json(["ip", "-j", "-4", "addr", "show", "up"])
        return (
            None
            if rows is None
            else [
                {
                    "name": row.get("ifname", ""),
                    "up": "UP" in row.get("flags", []) and row.get("operstate") != "DOWN",
                    "addresses": [
                        address.get("local")
                        for address in row.get("addr_info", [])
                        if address.get("family") == "inet"
                    ],
                }
                for row in rows
                if isinstance(row, dict)
            ]
        )
    if system == "Darwin":
        raw = _command(["ifconfig"])
        if raw is None:
            return None
        return [
            {
                "name": match[1],
                "up": bool(re.search(r"\bUP\b", match[2])) and "status: inactive" not in match[2],
                "addresses": re.findall(r"\binet\s+(\d+\.\d+\.\d+\.\d+)", match[2]),
            }
            for match in re.finditer(r"(?m)^(\S+):([^\n]*(?:\n[ \t]+[^\n]*)*)", raw)
        ]
    return None


def _private(value):
    try:
        address = ipaddress.IPv4Address(value)
        return str(address) if any(address in network for network in PRIVATE_NETWORKS) else None
    except (ipaddress.AddressValueError, TypeError):
        return None


def _route_address(system):
    if system == "Linux":
        rows = _json(["ip", "-j", "-4", "route", "get", PROBE_DESTINATION])
        if rows and isinstance(rows[0], dict):
            address = _private(rows[0].get("prefsrc") or rows[0].get("src"))
            if address:
                return address
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.settimeout(0.2)
            probe.connect((PROBE_DESTINATION, 9))
            return _private(probe.getsockname()[0])
    except OSError:
        return None


def discover_addresses() -> list[str]:
    """Return deduplicated RFC1918 IPv4 candidates, active-route address first.

    Available OS inventory is authoritative about disconnected/virtual adapters.
    Only when that inventory is unavailable do hostname and kernel-route fallbacks
    provide candidates whose adapter type could not be established.
    """
    system = platform.system()
    inventory, candidates = _inventory(system), set()
    active = _route_address(system)
    if inventory is not None:
        for row in inventory:
            excluded = row.get("virtual") is True or any(
                EXCLUDED.search(str(row.get(key, ""))) for key in ("name", "description")
            )
            if not row.get("up") or excluded:
                continue
            values = row.get("addresses", [])
            for value in [values] if isinstance(values, str) else values or []:
                if address := _private(value):
                    candidates.add(address)
    else:
        if active:
            candidates.add(active)
        try:
            resolved = socket.getaddrinfo(
                socket.gethostname(), None, socket.AF_INET, socket.SOCK_DGRAM
            )
            candidates.update(address for row in resolved if (address := _private(row[4][0])))
        except OSError:
            pass
    return sorted(
        candidates, key=lambda value: (value != active, int(ipaddress.IPv4Address(value)))
    )
