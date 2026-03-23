"""Phase 0 feasibility probe for QtBluetooth SDP discovery.

Flow:
1. Scan nearby Bluetooth devices.
2. Let the user select one device.
3. Run SDP service discovery and print discovered UUIDs.
"""

from __future__ import annotations

import argparse
import platform
import sys
from dataclasses import dataclass

from PySide6.QtBluetooth import (
	QBluetoothAddress,
	QBluetoothDeviceDiscoveryAgent,
	QBluetoothServiceDiscoveryAgent,
)
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer


@dataclass
class DeviceRecord:
	name: str
	address: str
	qt_address: QBluetoothAddress


def safe_quit(loop: QEventLoop) -> None:
	if loop.isRunning():
		loop.quit()


def stop_if_active(agent) -> None:
	if agent.isActive():
		agent.stop()


def connect_error_signal(agent, callback) -> None:
	if hasattr(agent, "errorOccurred"):
		agent.errorOccurred.connect(callback)
	else:
		agent.error.connect(callback)


def get_error_string(agent, fallback: str) -> str:
	return agent.errorString() if hasattr(agent, "errorString") and agent.errorString() else fallback


def normalize_uuid(raw: str) -> str:
	return raw.strip().lower().strip("{}")


def ensure_qt_app() -> QCoreApplication:
	app = QCoreApplication.instance()
	if app is not None:
		return app
	return QCoreApplication(sys.argv)


def format_device_name(name: str) -> str:
	return name if name else "Unknown"


def is_empty_address(address: str) -> bool:
	cleaned = address.replace(":", "").replace("-", "").strip().lower()
	return cleaned in {"", "0", "000000000000"}


def discover_devices(scan_timeout: int) -> list[DeviceRecord]:
	_ = ensure_qt_app()
	loop = QEventLoop()

	agent = QBluetoothDeviceDiscoveryAgent()
	discovered: dict[str, DeviceRecord] = {}
	error_text = ""

	def on_device_found(device_info) -> None:
		addr_obj = device_info.address()
		addr_text = addr_obj.toString()
		if is_empty_address(addr_text):
			# Some platforms may hide MAC addresses. Skip unsupported entries
			# for this SDP probe because service discovery needs an address.
			return
		key = addr_text.upper()
		if key in discovered:
			return
		discovered[key] = DeviceRecord(
			name=format_device_name(device_info.name()),
			address=addr_text,
			qt_address=addr_obj,
		)

	def on_error(*_args) -> None:
		nonlocal error_text
		error_text = get_error_string(agent, "Unknown device discovery error")
		safe_quit(loop)

	def on_finished() -> None:
		safe_quit(loop)

	agent.deviceDiscovered.connect(on_device_found)
	connect_error_signal(agent, on_error)
	agent.finished.connect(on_finished)
	agent.canceled.connect(on_finished)

	timer = QTimer()
	timer.setSingleShot(True)

	def on_timeout() -> None:
		stop_if_active(agent)
		safe_quit(loop)

	timer.timeout.connect(on_timeout)
	timer.start(max(1, scan_timeout) * 1000)

	print(f"[INFO] Scanning for devices for up to {scan_timeout} seconds...")
	agent.start()
	loop.exec()

	if error_text:
		print(f"[WARN] Device discovery error: {error_text}")

	return sorted(discovered.values(), key=lambda d: (d.name.lower(), d.address))


def pick_device(devices: list[DeviceRecord]) -> DeviceRecord | None:
	if not devices:
		return None

	print("\nDiscovered devices:")
	for idx, dev in enumerate(devices, start=1):
		print(f"  {idx}. {dev.name} [{dev.address}]")

	while True:
		raw = input("\nSelect device number to run SDP query (q to quit): ").strip()
		if raw.lower() in {"q", "quit", "exit"}:
			return None
		if not raw.isdigit():
			print("[WARN] Enter a valid number or q.")
			continue
		choice = int(raw)
		if 1 <= choice <= len(devices):
			return devices[choice - 1]
		print("[WARN] Selection out of range.")


def discover_sdp_services(device: DeviceRecord, service_timeout: int) -> tuple[set[str], str | None]:
	_ = ensure_qt_app()
	loop = QEventLoop()
	agent = QBluetoothServiceDiscoveryAgent()

	uuids: set[str] = set()
	error_text: str | None = None

	def on_service_found(service_info) -> None:
		service_uuid = service_info.serviceUuid()
		if service_uuid is not None and not service_uuid.isNull():
			uuids.add(normalize_uuid(service_uuid.toString()))

		for class_uuid in service_info.serviceClassUuids():
			if class_uuid is not None and not class_uuid.isNull():
				uuids.add(normalize_uuid(class_uuid.toString()))

	def on_error(*_args) -> None:
		nonlocal error_text
		error_text = get_error_string(agent, "Unknown SDP discovery error")
		safe_quit(loop)

	def on_finished() -> None:
		safe_quit(loop)

	agent.serviceDiscovered.connect(on_service_found)
	connect_error_signal(agent, on_error)
	agent.finished.connect(on_finished)
	agent.canceled.connect(on_finished)

	timer = QTimer()
	timer.setSingleShot(True)

	def on_timeout() -> None:
		nonlocal error_text
		error_text = "SDP discovery timed out"
		stop_if_active(agent)
		safe_quit(loop)

	timer.timeout.connect(on_timeout)
	timer.start(max(1, service_timeout) * 1000)

	agent.setRemoteAddress(device.qt_address)
	print(f"\n[INFO] Running SDP query for {device.name} [{device.address}]...")
	agent.start(QBluetoothServiceDiscoveryAgent.DiscoveryMode.FullDiscovery)
	loop.exec()

	return uuids, error_text


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Phase 0 QtBluetooth SDP feasibility probe"
	)
	parser.add_argument(
		"--scan-timeout",
		type=int,
		default=8,
		help="device scan timeout in seconds (default: 8)",
	)
	parser.add_argument(
		"--service-timeout",
		type=int,
		default=10,
		help="SDP service discovery timeout in seconds (default: 10)",
	)
	return parser.parse_args()


def main() -> int:
	args = parse_args()
	ensure_qt_app()

	print("QtBluetooth SDP Phase 0 Probe")
	print(f"[INFO] Platform: {platform.system()} {platform.release()}")

	devices = discover_devices(scan_timeout=args.scan_timeout)
	if not devices:
		print("[INFO] No discoverable devices found.")
		return 0

	selected = pick_device(devices)
	if selected is None:
		print("[INFO] Exiting without SDP query.")
		return 0

	uuids, err = discover_sdp_services(selected, service_timeout=args.service_timeout)
	if err:
		print(f"[WARN] SDP query finished with issue: {err}")

	print("\nDiscovered service UUIDs:")
	if not uuids:
		print("  (none)")
	else:
		for value in sorted(uuids):
			print(f"  - {value}")

	if err:
		return 1
	return 0 if uuids else 2


if __name__ == "__main__":
	raise SystemExit(main())
