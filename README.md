Initial setup
=============
Unless otherwise specified, run these from the root directory after
cloning this repository.

 - Create a virtual environment using `pipenv`:

        pipenv --three

 - Activate the virtual environment (should be used whenever working
   with this repository later as well):

        pipenv shell

 - Install all dependencies (can later be used to upate to newer package
   versions committed to Pipfile.lock as well):

        pipenv sync

 - Create an initial database (can later be used to upgrade the database
   as well).

        ./manage.py migrate

 - Create an initial super user:

        ./manage.py createsuperuser

 - Run a development server:

        ./manage.py runserver
