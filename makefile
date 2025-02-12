.PHONY: install lint test build run clean


# install
install:
	@echo "Installing dependencies..."
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -e .


# lint
lint:
	@echo "Running lint checks..."
	pip install flake8
	flake8 --max-line-length 150 .


# test
test:
	@echo "Running tests..."
	pip install pytest
	pytest --maxfail=1 --disable-warnings -q


# build
build:
	@echo "Building package..."
	pip install build
	python -m build


# run
run:
	@echo "Starting Streamlit app..."
	streamlit run tableau_report_gen/app.py --server.port=8501 --server.address=0.0.0.0


# clean
clean:
	@echo "Cleaning up..."
	rm -rf build dist *.egg-info __pycache__ .pytest_cache
