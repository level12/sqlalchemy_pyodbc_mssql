sqlalchemy_pyodbc_mssql Readme
==========================================

.. image:: https://circleci.com/gh/level12/sqlalchemy_pyodbc_mssql.svg?&style=shield
    :target: https://circleci.com/gh/level12/sqlalchemy_pyodbc_mssql

.. image:: https://codecov.io/gh/level12/sqlalchemy_pyodbc_mssql/branch/master/graph/badge.svg
    :target: https://codecov.io/github/level12/sqlalchemy_pyodbc_mssql?branch=master

Overview
--------

PyODBC is Microsoft's recommended DBAPI layer for connecting a python application to MSSQL. However,
the layer is not MSSQL-specific, and so it has some limitations:

- parameterized queries with GROUP BY will not always work ([source](https://github.com/mkleehammer/pyodbc/issues/479))
- stored procedures (such as those called by the prepared statements in pyodbc) are limited to
  2100 parameters ([source](https://docs.microsoft.com/en-us/sql/sql-server/maximum-capacity-specifications-for-sql-server?view=sql-server-2017))

SQLAlchemy has a PyODBC dialect for MSSQL usage, but it also shares these limitations.

- for GROUP BY details, see https://github.com/sqlalchemy/sqlalchemy/issues/4540

[PyMSSQL](http://www.pymssql.org) exists as an alternative DBAPI layer and dialect for SQLAlchemy. Since it prepares queries
by rolling parameters into the query string itself (properly quoted, of course) rather than issuing
ODBC prepared statements, it does not share the above problems.

sqlalchemy_pyodbc_mssql extends the built-in SQLAlchemy PyODBC dialect in order to work around
these limits in a manner consistent with PyMSSQL's implementation.

Usage
-----

-  Installation
    - for usage in app: `pip install sqlalchemy_pyodbc_mssql`
    - to run tests: `pip install sqlalchemy_pyodbc_mssql[tests]`
-  Usage
    - see [SQLAlchemy instructions for PyODBC usage](https://docs.sqlalchemy.org/en/13/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pyodbc)
    - dialect name to use is `mssql+pyodbc_mssql`
        - examples:
            - `mssql+pyodbc_mssql://<username>:<password>@<dsnname>`
            - `mssql+pyodbc_mssql://<username>:<password>@<dbname>?driver=SQL+Server+Native+Client+11.0`
