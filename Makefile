PYTHONPATH := simulator:ml:protocol/python

.PHONY: test demo closed-loop model firmware-host

test:
	PYTHONPATH=$(PYTHONPATH) python -m pytest

demo:
	PYTHONPATH=$(PYTHONPATH) python tools/run_virtual_demo.py

closed-loop:
	PYTHONPATH=$(PYTHONPATH) python tools/run_closed_loop.py

model:
	PYTHONPATH=simulator:ml python -m forgesense_ml.train --out build/model.json

firmware-host:
	mkdir -p build
	g++ -std=c++20 -Wall -Wextra -Werror -Ifirmware/components/forgesense_protocol/include firmware/components/forgesense_protocol/forgesense_protocol.cpp firmware/tests/protocol_test.cpp -o build/firmware_protocol_test
	./build/firmware_protocol_test
	g++ -std=c++20 -Wall -Wextra -Werror -Ifirmware/components/forgesense_protocol/include firmware/components/forgesense_protocol/forgesense_protocol.cpp firmware/components/forgesense_protocol/forgesense_stream.cpp firmware/tests/stream_test.cpp -o build/firmware_stream_test
	./build/firmware_stream_test
