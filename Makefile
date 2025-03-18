
create-env: 
	python3.11.5 -m venv venv
	source venv/bin/activate
	pip install -r requirements.txt

activate-env: 
	source venv/bin/activate