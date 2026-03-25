# bluetooth-sdp-crawler

Phase 0 QtBluetooth SDP feasibility probe for Bluetooth Classic service discovery.

This CLI tool:
1. Scans nearby Bluetooth devices.
2. Prompts you to select one discovered device.
3. Runs SDP service discovery against that device.
4. Prints discovered service UUIDs.

## Requirements

- Python 3.10+
- A Bluetooth adapter enabled on your machine
- PySide6 with QtBluetooth bindings

Install Python dependency:

```bash
pip install -r requirements.txt
```

## Run

```bash
python bt-sdp-crawler.py
```

Optional arguments:

- `--scan-timeout <seconds>`: max time for device scan (default: `30`)
- `--service-timeout <seconds>`: max time for SDP query (default: `30`)

Example:

```bash
python bt-sdp-crawler.py --scan-timeout 20 --service-timeout 15
```

## What The Script Prints

- Platform information at startup
- Informational and warning messages during discovery
- A numbered list of discovered devices as `name [address]`
- Final list of normalized (lowercase, brace-stripped) service UUIDs

If no UUIDs are found, it prints `(none)`.

## Interactive Selection

After scan completes, enter:

- A device number to run SDP query on that device
- `q`, `quit`, or `exit` to stop without querying

## Exit Codes

- `0`: successful run with at least one UUID found, or user exits intentionally
- `1`: SDP query completed with an error/timeout condition
- `2`: SDP query completed without errors but found no UUIDs

## Notes And Limitations

- Devices with hidden/empty Bluetooth addresses are skipped because SDP discovery requires an address.
- Discovery and SDP operations are timeout-bounded using Qt event loops.
- Platform/backend Bluetooth support can vary; behavior depends on local OS stack, drivers, and permissions.