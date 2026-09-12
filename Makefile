PYTHONPATH := simulator:ml:protocol/python:telemetry:commissioning
CXXFLAGS := -std=c++20 -Wall -Wextra -Werror -pedantic
PROTO_INC := -Ifirmware/components/forgesense_protocol/include
INFER_INC := -Ifirmware/components/forgesense_inference/include
EVENT_INC := -Ifirmware/components/forgesense_events/include
TELEM_INC := -Ifirmware/components/forgesense_telemetry/include
SENSING_INC := -Ifirmware/components/forgesense_sensing/include
MAINT_INC := -Ifirmware/esp32_calibration_maintenance/main

.PHONY: test demo closed-loop validate dashboard model model-export sensor-contract phy-sim circuit-check hardware-check sensor-device-check sensor-behavior-check tang-pin-check bringup-check commissioning-check calibration-check calibration-diagnostic-check calibration-assembler-check calibration-campaign-check calibration-bundle-verification-check calibration-source-change-check calibration-provisioning-check maintenance-provisioning-check signed-maintenance-authorization-check calibration-recovery-check calibration-audit-ledger-check maintenance-authority-transition-check bench-record-validate gowin-build smoke-build calibration-build firmware-host

test:
	PYTHONPATH=$(PYTHONPATH) python -m pytest

demo:
	PYTHONPATH=$(PYTHONPATH) python tools/run_virtual_demo.py

closed-loop:
	PYTHONPATH=$(PYTHONPATH) python tools/run_closed_loop.py

validate:
	PYTHONPATH=$(PYTHONPATH) python tools/run_validation_matrix.py

dashboard:
	PYTHONPATH=$(PYTHONPATH) python tools/run_dashboard.py

model:
	PYTHONPATH=$(PYTHONPATH) python -m forgesense_ml.train --out build/model.json

model-export:
	PYTHONPATH=$(PYTHONPATH) python tools/export_reference_model.py --out firmware/components/forgesense_inference/include/forgesense_reference_model_generated.h

sensor-contract:
	python tools/generate_sensor_contract.py hardware/profiles/sensor_contract_v1.json --cxx firmware/components/forgesense_protocol/include/forgesense_sensor_contract_generated.h --vhdl fpga/rtl/sensing/sensor_contract_pkg.vhd

phy-sim:
	python tools/simulate_sensor_phy.py

circuit-check:
	python tools/check_reference_circuits.py

sensor-device-check:
	python tools/check_sensor_device_drivers.py

sensor-behavior-check:
	python tools/check_sensor_behavioral_verification.py

tang-pin-check:
	python tools/check_tang_nano_9k_pinmap.py

bringup-check:
	python tools/check_physical_bringup.py

commissioning-check:
	mkdir -p build
	PYTHONPATH=$(PYTHONPATH) python -m pytest tests/test_commissioning.py
	python tools/check_commissioning_contract.py
	g++ $(CXXFLAGS) $(PROTO_INC) firmware/components/forgesense_protocol/forgesense_protocol.cpp firmware/tests/commissioning_status_test.cpp -o build/commissioning_status_test
	./build/commissioning_status_test

calibration-check:
	PYTHONPATH=$(PYTHONPATH) python -m pytest tests/test_calibration_capture.py tests/test_calibration_review.py
	python tools/check_calibration_capture.py
	python tools/check_calibration_review.py

calibration-diagnostic-check:
	PYTHONPATH=$(PYTHONPATH) python -m pytest tests/test_calibration_diagnostics.py
	python tools/check_calibration_diagnostics.py

calibration-assembler-check:
	PYTHONPATH=$(PYTHONPATH) python -m pytest tests/test_calibration_capture_assembler.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_calibration_assembler.py

calibration-campaign-check:
	PYTHONPATH=$(PYTHONPATH) python -m pytest tests/test_calibration_campaign.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_calibration_campaign.py

calibration-bundle-verification-check:
	PYTHONPATH=$(PYTHONPATH) python -m pytest tests/test_calibration_bundle_verification.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_calibration_bundle_verification.py

calibration-source-change-check:
	PYTHONPATH=$(PYTHONPATH) python -m pytest tests/test_calibration_source_change.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_calibration_source_change.py

calibration-provisioning-check:
	mkdir -p build
	PYTHONPATH=$(PYTHONPATH) python -m pytest tests/test_calibration_provisioning.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_calibration_provisioning.py
	g++ $(CXXFLAGS) $(SENSING_INC) firmware/components/forgesense_sensing/forgesense_calibration.cpp firmware/components/forgesense_sensing/forgesense_calibration_provisioning.cpp firmware/tests/calibration_provisioning_test.cpp -o build/calibration_provisioning_test
	./build/calibration_provisioning_test

maintenance-provisioning-check:
	mkdir -p build
	PYTHONPATH=$(PYTHONPATH) python -m pytest tests/test_maintenance_provisioning.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_maintenance_provisioning.py
	g++ $(CXXFLAGS) $(MAINT_INC) firmware/esp32_calibration_maintenance/main/maintenance_protocol.cpp firmware/tests/maintenance_protocol_test.cpp -o build/maintenance_protocol_test
	./build/maintenance_protocol_test

signed-maintenance-authorization-check:
	PYTHONPATH=$(PYTHONPATH) python -m pytest tests/test_signed_maintenance_authorization.py
	PYTHONPATH=$(PYTHONPATH) python tools/validate_signed_provisioning_policy.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_signed_maintenance_authorization.py

calibration-recovery-check:
	PYTHONPATH=$(PYTHONPATH) python -m pytest tests/test_calibration_recovery.py
	PYTHONPATH=$(PYTHONPATH) python tools/validate_signed_provisioning_policy.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_calibration_recovery.py

calibration-audit-ledger-check:
	PYTHONPATH=$(PYTHONPATH) python -m pytest tests/test_calibration_audit_ledger.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_calibration_audit_ledger.py

maintenance-authority-transition-check:
	PYTHONPATH=$(PYTHONPATH) python -m pytest tests/test_maintenance_authority_transition.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_maintenance_authority_transition.py

bench-record-validate:
	@test -n "$(RECORD)" || (echo "Usage: make bench-record-validate RECORD=path/to/record.json"; exit 2)
	python tools/validate_bench_record.py "$(RECORD)"

gowin-build: tang-pin-check
	gw_sh fpga/scripts/tang_nano_9k_build.tcl

smoke-build: tang-pin-check bringup-check
	gw_sh fpga/scripts/tang_nano_9k_smoke_build.tcl

calibration-build: tang-pin-check calibration-diagnostic-check
	gw_sh fpga/scripts/tang_nano_9k_calibration_build.tcl

hardware-check:
	python tools/check_hardware_baseline.py
	python tools/check_reference_circuits.py
	python tools/check_sensor_device_drivers.py
	python tools/check_tang_nano_9k_pinmap.py
	python tools/check_physical_bringup.py
	python tools/check_commissioning_contract.py
	python tools/check_calibration_capture.py
	python tools/check_calibration_review.py
	python tools/check_calibration_diagnostics.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_calibration_assembler.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_calibration_campaign.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_calibration_bundle_verification.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_calibration_source_change.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_calibration_provisioning.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_maintenance_provisioning.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_signed_maintenance_authorization.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_calibration_recovery.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_calibration_audit_ledger.py
	PYTHONPATH=$(PYTHONPATH) python tools/check_maintenance_authority_transition.py

firmware-host:
	mkdir -p build
	g++ $(CXXFLAGS) $(PROTO_INC) firmware/components/forgesense_protocol/forgesense_protocol.cpp firmware/tests/protocol_test.cpp -o build/firmware_protocol_test
	./build/firmware_protocol_test
	g++ $(CXXFLAGS) $(PROTO_INC) firmware/components/forgesense_protocol/forgesense_protocol.cpp firmware/components/forgesense_protocol/forgesense_stream.cpp firmware/tests/stream_test.cpp -o build/firmware_stream_test
	./build/firmware_stream_test
	g++ $(CXXFLAGS) $(PROTO_INC) $(INFER_INC) firmware/components/forgesense_protocol/forgesense_protocol.cpp firmware/components/forgesense_inference/forgesense_inference.cpp firmware/tests/inference_test.cpp -o build/firmware_inference_test
	./build/firmware_inference_test
	g++ $(CXXFLAGS) $(PROTO_INC) $(EVENT_INC) firmware/components/forgesense_events/forgesense_events.cpp firmware/tests/events_test.cpp -o build/firmware_events_test
	./build/firmware_events_test
	g++ $(CXXFLAGS) $(PROTO_INC) $(TELEM_INC) firmware/components/forgesense_telemetry/forgesense_telemetry.cpp firmware/tests/telemetry_test.cpp -o build/firmware_telemetry_test
	./build/firmware_telemetry_test
	g++ $(CXXFLAGS) $(PROTO_INC) firmware/tests/sensor_contract_test.cpp -o build/sensor_contract_test
	./build/sensor_contract_test
	g++ $(CXXFLAGS) $(SENSING_INC) firmware/components/forgesense_sensing/forgesense_sensing.cpp firmware/tests/sensing_test.cpp -o build/sensing_test
	./build/sensing_test
	g++ $(CXXFLAGS) $(SENSING_INC) firmware/components/forgesense_sensing/forgesense_sensing.cpp firmware/components/forgesense_sensing/forgesense_calibration.cpp firmware/tests/calibration_test.cpp -o build/calibration_test
	./build/calibration_test
	g++ $(CXXFLAGS) $(SENSING_INC) firmware/components/forgesense_sensing/forgesense_calibration.cpp firmware/components/forgesense_sensing/forgesense_calibration_provisioning.cpp firmware/tests/calibration_provisioning_test.cpp -o build/calibration_provisioning_test
	./build/calibration_provisioning_test
	g++ $(CXXFLAGS) $(MAINT_INC) firmware/esp32_calibration_maintenance/main/maintenance_protocol.cpp firmware/tests/maintenance_protocol_test.cpp -o build/maintenance_protocol_test
	./build/maintenance_protocol_test
	g++ $(CXXFLAGS) $(SENSING_INC) firmware/components/forgesense_sensing/forgesense_sensing.cpp firmware/components/forgesense_sensing/forgesense_calibration.cpp firmware/components/forgesense_sensing/forgesense_phy.cpp firmware/tests/phy_test.cpp -o build/phy_test
	./build/phy_test
