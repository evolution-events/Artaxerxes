[![Build Status](https://travis-ci.org/evolution-events/Artaxerxes.svg?branch=master)](https://travis-ci.org/evolution-events/Artaxerxes)

Initial setup
=============
To create enter the virtual environment (can be used later as well):

        make shell

To install dependencies and create the initial environment:

        make setup

To create an initial user:

        ./manage.py createsuperuser

Later, you can update the environment (install new dependencies when
Pipfile/Pipfile.lock changed, or run new migrations):

        make refresh

Before committing / pushing
===========================
To check your code complies to the formatting guidelines and passes
tests, run:

        make check
