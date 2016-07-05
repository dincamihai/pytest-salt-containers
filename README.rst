pytest-salt-containers
===================================

A Pytest plugin that makes it easy to write integration tests for salt

----

This `Pytest`_ plugin was generated with `Cookiecutter`_ along with `@hackebrot`_'s `Cookiecutter-pytest-plugin`_ template.


Installation
------------

You can install "pytest-salt-containers" via `pip`_ from `PyPI`_::

    $ pip install pytest-salt-containers


Usage
-----

How to write tests and how they work
************************************

Writing a "test.ping" test

For this we need a salt master and a minion.
We can do that by creating a new file in the `tests` folder:

.. compound::

    ./tests/test_example.py::

        def test_ping_minion(master, minion):
        pass

This uses `master` and `minion` fixtures defined in `tests/conftest.py`.

_Note: The fixtures defined in `conftest.py` (or in the current file) are automatically discovered by `py.test`_

The fixtures rely on [fatory-boy](https://pypi.python.org/pypi/factory_boy/) factories defined in `tests/factories.py`.
The factories take care of running `sast-master` and `salt-minion` in separate docker containers (it is also possible to run them in the same container).

With this, we have a running salt-master and a salt-minion.

To make master accept minion, I have created a convenient fixture called `minion_key_accepted`
Let's modify the test above to use it.

.. compound::

    ./tests/test_example.py::

        def test_ping_minion(master, minion, minion_key_accepted):
             pass

To run `salt <minion-id> test.ping` on master and assert minion replied, do this:

.. compound::

    ./tests/test_example.py::

        def test_ping_minion(master, minion, minion_key_accepted):
             assert master.salt(minion['id'], "test.ping")[minion['id']] is True

This might fail sometimes because the command might be run before .
In order to avoid that, I have created a `retry` helper that raises an exception if the command was not successful within `config.TIME_LIMIT`. So we need to change the test like this:

.. compound::

    ./tests/test_example.py::

        from utils import retry


        def test_ping_minion(master, minion, minion_key_accepted):

            def ping():                                                                 
                return master.salt(minion['id'], "test.ping")[minion['id']]             
                                                                                       
            assert retry(ping)       

Contributing
------------
Contributions are very welcome. Tests can be run with `tox`_, please ensure
the coverage at least stays the same before you submit a pull request.

License
-------

Distributed under the terms of the `MIT`_ license, "pytest-salt-containers" is free and open source software


Issues
------

If you encounter any problems, please `file an issue`_ along with a detailed description.

.. _`Cookiecutter`: https://github.com/audreyr/cookiecutter
.. _`@hackebrot`: https://github.com/hackebrot
.. _`MIT`: http://opensource.org/licenses/MIT
.. _`BSD-3`: http://opensource.org/licenses/BSD-3-Clause
.. _`GNU GPL v3.0`: http://www.gnu.org/licenses/gpl-3.0.txt
.. _`Apache Software License 2.0`: http://www.apache.org/licenses/LICENSE-2.0
.. _`cookiecutter-pytest-plugin`: https://github.com/pytest-dev/cookiecutter-pytest-plugin
.. _`file an issue`: https://github.com/dincamihai/pytest-salt-containers/issues
.. _`pytest`: https://github.com/pytest-dev/pytest
.. _`tox`: https://tox.readthedocs.io/en/latest/
.. _`pip`: https://pypi.python.org/pypi/pip/
.. _`PyPI`: https://pypi.python.org/pypi
