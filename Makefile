PYTHONPATH := simulator:ml:protocol/python:telemetry
CXXFLAGS := -std=c++20 -Wall -Wextra -Werror -pedantic
PROTO_INC := -Ifirmware/components/forgesense_protocol/include
INFER_INC := -Ifirmware/components/forgesense_inference/include
EVENT_INC := -Ifirmware/components/forgesense_events/include
TELEM_INC := -Ifirmware/components/forgesense_telemetry/include

.PHONY: test demo closed-loop validate dashboard model model-export sensor-contract firmware-host

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
