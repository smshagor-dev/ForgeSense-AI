from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "generate_sensor_contract.py"
CONTRACT = ROOT / "hardware" / "profiles" / "sensor_contract_v1.json"
CXX = ROOT / "firmware" / "components" / "forgesense_protocol" / "include" / "forgesense_sensor_contract_generated.h"
VHDL = ROOT / "fpga" / "rtl" / "sensing" / "sensor_contract_pkg.vhd"


def _module():
    spec = importlib.util.spec_from_file_location("sensor_contract_generator", GENERATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_sensor_contract_is_reproducible():
    module = _module()
    data = module.load(CONTRACT)
    assert CXX.read_text() == module.cxx(data)
    assert VHDL.read_text() == module.vhdl(data)
    assert data["channels"]["temperature"]["minimum"] == -400
    assert data["channels"]["vibration"]["stale_after_ms"] == 500
