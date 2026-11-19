Changelog
=========

0.20261119.1 released 2026-11-19
--------------------------------

- modernize packaging and development tooling with Coppy, uv, Nox, prek, and
  GitHub Actions
- support and test Python 3.12 through 3.15 with current SQLAlchemy and pyodbc
- use SQLAlchemy's type-aware literal rendering for affected ``GROUP BY`` and
  expanding parameters while leaving unrelated binds parameterized
- add live contract tests against SQL Server 2022 and ODBC Driver 18 for both
  workarounds and every supported fallback literal type


0.1.1 released 2022-10-24
-------------------------

- resolve cache warning from SQLAlchemy 1.4 (480007f_)

.. _480007f: https://github.com/level12/sqlalchemy_pyodbc_mssql/commit/480007f


0.1.0 released 2019-06-17
-------------------------

- initial release
