LOCALPATH := ./
PYTHONPATH := $(LOCALPATH)/
PYTHON_BIN := $(VIRTUAL_ENV)/bin

DJANGO_TEST_SETTINGS_FILE := development
DJANGO_TEST_SETTINGS := arta.settings.$(DJANGO_TEST_SETTINGS_FILE)
DJANGO_TEST_POSTFIX := --settings=$(DJANGO_TEST_SETTINGS) --pythonpath=$(PYTHONPATH)


.PHONY: all clean coverage ensure_virtual_env flake8 flake lint \
		django_check check test test/dev test/prod migrate \
		setup refresh shell sort


all:
	@echo "Hello $(LOGNAME)! Welcome to django-project-skeleton"
	@echo ""
	@echo "  clean        Removes all temporary files"
	@echo "  check        Run all relevant pre-commit checks"
	@echo "  sort         Apply proper import sorting"
	@echo "  coverage     Runs the tests and shows code coverage"
	@echo "  flake8       Runs flake8 to check for PEP8 compliance"
	@echo "  django_check Runs django's check command"
	@echo "  migrate      Applies all migrations"
	@echo "  refresh      Update the development environment (after pulling in"
	@echo "                 changes), syncing dependencies, running migrations,"
	@echo "                 etc."
	@echo "  setup        Sets up a development environment by installing"
	@echo "                 necessary apps, running migrations, etc."
	@echo "  test         Runs the tests"
	@echo "  test/dev     Runs the tests with development settings"
	@echo "  test/prod    Runs the tests with production settings"
	@echo "  shell        Create a virtualenv (if needed) and run a shell"
	@echo "                 inside it. All other commands should be run"
	@echo "                 inside this shell"


# performs the tests and measures code coverage
coverage: ensure_virtual_env test
	$(PYTHON_BIN)/coverage html
	$(PYTHON_BIN)/coverage report


# deletes all temporary files created by Django
clean:
	@find . -iname "*.pyc" -delete
	@find . -iname "__pycache__" -delete
	@rm -rf .coverage coverage_html


# most of the commands can only be used inside of the virtual environment
ensure_virtual_env:
	@if [ -z $$VIRTUAL_ENV ]; then \
		echo "You don't have a virtualenv enabled."; \
		echo "Please enable the virtualenv first (make shell)!"; \
		exit 1; \
	fi

# Run all pre-commit checks
check: flake8 django_check test

# Fix import sorting
sort:
	isort .

# runs flake8 to check for PEP8 compliance
flake8: ensure_virtual_env
	$(PYTHON_BIN)/flake8 .

flake: flake8

lint: flake8

# runs some django checks for common problems
django_check: ensure_virtual_env
	@$(PYTHON_BIN)/coverage run $(PYTHON_BIN)/django-admin.py check $(DJANGO_TEST_POSTFIX)

# runs the tests
test: ensure_virtual_env
	@echo "Using setting file '$(DJANGO_TEST_SETTINGS_FILE)'..."
	@echo ""
	@$(PYTHON_BIN)/coverage run $(PYTHON_BIN)/django-admin.py test $(DJANGO_TEST_POSTFIX) --exclude-tag=benchmark

# runs the tests with development settings
test/dev:
	$(MAKE) test DJANGO_TEST_SETTINGS_FILE=development

# runs the tests with production settings
test/prod:
	$(MAKE) test DJANGO_TEST_SETTINGS_FILE=production

# migrates the installed apps
migrate: ensure_virtual_env
	$(CURDIR)/manage.py migrate

# sets up the development environment by installing required dependencies,
setup: ensure_virtual_env
	$(MAKE) refresh

# refreshes the project by updating dependencies and running migrations
refresh: ensure_virtual_env
	@poetry install
	$(MAKE) migrate

# runs a shell inside the virtualenv created by pipenv
shell:
	poetry shell

# run everything needed after an update in the production environment
deploy: ensure_virtual_env
	@poetry install --no-dev
	$(MAKE) migrate
	$(CURDIR)/manage.py collectstatic --no-input
	# Reload wsgi app, if configured like that
	touch arta/wsgi.py
