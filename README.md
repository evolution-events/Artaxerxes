[![Build Status](https://travis-ci.org/evolution-events/Artaxerxes.svg?branch=master)](https://travis-ci.org/evolution-events/Artaxerxes)

Initial setup
=============
This project uses [poetry][] to manage its dependencies. Before
starting, make sure that Poetry is installed. The project itself uses a
shell-script based installer, but it is probably better to just install
it using pip:

	pip3 install poetry

Using `pip3` is typically right to use python3 on Linux, on systems with
just python3 installed, you might need to use `pip` instead.

[poetry]: https://poetry.eustace.io/

Poetry will create a virtualenv automatcally in the background. To do so
and enter it, run:

	poetry shell

(or `make shell` as a shortcut)

Then, inside this shell, install dependencies using

	poetry install

This uses the version from the `poetry.lock` file, recreating exactly the
environment used to commit that file. This command can also be used
later, after puling an updated `poetry.lock` file.

To create a database, run django's `migrate` command:

        ./manage.py migrate

Install dependencies and setting up the database can also be done use
`make setup` as a shortcut.

To get started, either create a superuser with an otherwise empty
database:

        ./manage.py createsuperuser

Or load fixture data using:

	./manage.py loaddata fixtures/default.yaml

(the users loaded by this have password 'evolution')

Updating
========
Later, you can update the environment (install new dependencies when
poetry.lock changed, or run new migrations):

        make refresh

Alternatively, you can also run `poetry install` or `./manage.py migrate`
directly.

To actually update `poetry.lock` by installing new versions of
dependencies, use:

	`poetry update`

Production vs development
=========================
By default, `poetry` installs the development dependencies. To install
just production dependencies, add `--no-dev` to e.g. `poetry install`
and `poetry update`.

Before committing / pushing
===========================
To check your code complies to the formatting guidelines and passes
tests, run:

        make check
