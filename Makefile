.PHONY: all codegen crdgen modelgen docgen test lint
all: codegen test lint

codegen: crdgen modelgen

crdgen:
	python ./scripts/crdgen.py

modelgen:
	python ./scripts/modelgen.py

test:
	pytest --rootdir ./operator -v

lint:
	black ./operator
