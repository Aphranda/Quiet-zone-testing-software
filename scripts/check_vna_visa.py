from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quiet_zone_tester.presentation.modules.connection.connection_view_model import ConnectionViewModel


def candidate_resources(resource_name: str, fallback_port: int = 5025) -> list[str]:
    resource_name = resource_name.strip()
    candidates = [resource_name]
    match = re.match(r"^(TCPIP\d*)::([^:]+)::inst\d+::INSTR$", resource_name, flags=re.IGNORECASE)
    if match:
        prefix, host = match.groups()
        candidates.append(f"{prefix}::{host}::{fallback_port}::SOCKET")
        candidates.append(f"{prefix}::{host}::hislip0::INSTR")
    return list(dict.fromkeys(candidates))


def query_idn(resource_name: str, timeout_ms: int) -> str:
    import pyvisa

    rm = pyvisa.ResourceManager()
    resource = rm.open_resource(resource_name)
    try:
        resource.timeout = timeout_ms
        resource.read_termination = "\n"
        resource.write_termination = "\n"
        return str(resource.query("*IDN?")).strip()
    finally:
        resource.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="List and verify VNA VISA resources.")
    parser.add_argument("--model", default="N5245B", help="VNA model filter, e.g. E5080B or N5245B.")
    parser.add_argument("--resource", action="append", default=[], help="Explicit VISA resource to inspect/test.")
    parser.add_argument("--idn", action="store_true", help="Open each candidate resource and query *IDN?.")
    parser.add_argument("--timeout-ms", type=int, default=5000, help="VISA query timeout in milliseconds.")
    args = parser.parse_args()

    view_model = ConnectionViewModel()
    try:
        resources = view_model.enumerate_visa_resources()
    except Exception as exc:  # noqa: BLE001 - diagnostic script should keep going with --resource.
        print(f"VISA enumeration failed: {exc}")
        resources = []
    resources = list(dict.fromkeys([*resources, *args.resource]))
    filtered = view_model.filter_visa_resources_by_model(resources, args.model)
    if args.resource:
        explicit = [resource for resource in args.resource if resource not in filtered]
        filtered = [*filtered, *explicit]

    print(f"Model filter: {args.model}")
    print(f"All VISA resources ({len(resources)}):")
    for resource in resources:
        print(f"  - {resource}")

    print(f"\nMatched VNA resources ({len(filtered)}):")
    for resource in filtered:
        parsed = view_model.host_port_from_visa_resource(resource)
        if parsed is None:
            print(f"  - {resource}")
        else:
            host, port = parsed
            print(f"  - {resource}  -> host={host}, port={port}")

        candidates = candidate_resources(resource, fallback_port=parsed[1] if parsed else 5025)
        if len(candidates) > 1:
            print("    candidates:")
            for candidate in candidates:
                print(f"      {candidate}")

        if args.idn:
            for candidate in candidates:
                try:
                    idn = query_idn(candidate, args.timeout_ms)
                except Exception as exc:  # noqa: BLE001 - diagnostic script should show backend error.
                    print(f"    IDN {candidate}: FAILED: {exc}")
                else:
                    print(f"    IDN {candidate}: {idn}")
                    break

    if not filtered:
        print("\nNo VISA resources matched this model. Check NI-MAX resource name or try --model 5245B.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
