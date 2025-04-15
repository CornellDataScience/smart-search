create-env:
	python3.11 -m venv venv
	venv/bin/pip install -r requirements.txt

activate-env:
	@echo "To activate the virtual environment, run:"
	@echo "source venv/bin/activate"
