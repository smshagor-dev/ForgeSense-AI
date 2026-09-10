PYTHONPATH := simulator:ml:protocol/python

.PHONY: test demo model

test:
	PYTHONPATH=$(PYTHONPATH) python -m pytest

demo:
	PYTHONPATH=$(PYTHONPATH) python tools/run_virtual_demo.py

model:
	PYTHONPATH=simulator:ml python -m forgesense_ml.train --out build/model.json
