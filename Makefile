.PHONY: clean-pyc init test

VIRTUALENV_DIR = .pyenv
PIP = $(VIRTUALENV_DIR)/bin/pip
PYTHON = $(VIRTUALENV_DIR)/bin/python2
PYTEST = $(VIRTUALENV_DIR)/bin/pytest
export VIRTUALENV_DIR


clean-pyc:
	find . -name '*.pyc' -delete
	find . -name '*.pyo' -delete

init:
	if [ -d "$(VIRTUALENV_DIR)" ]; then rm -rf $(VIRTUALENV_DIR); fi

	virtualenv $(VIRTUALENV_DIR)
	sudo setcap cap_net_raw+ep .pyenv/bin/python2
	$(PIP) install --upgrade setuptools
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	$(PIP) install -e .

test:
	$(PYTEST) --cov pingem --cov-report term --cov-report html
