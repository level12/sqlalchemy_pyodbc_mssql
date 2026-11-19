# sqlalchemy_pyodbc_mssql

[![nox](https://github.com/level12/sqlalchemy_pyodbc_mssql/actions/workflows/nox.yaml/badge.svg)](https://github.com/level12/sqlalchemy_pyodbc_mssql/actions/workflows/nox.yaml)
[![codecov](https://codecov.io/gh/level12/sqlalchemy_pyodbc_mssql/branch/master/graph/badge.svg)](https://codecov.io/gh/level12/sqlalchemy_pyodbc_mssql)

SQLAlchemy's SQL Server pyodbc dialect with focused workarounds for two SQL
Server/ODBC limitations:

- Repeated positional parameters in a `SELECT` expression and its `GROUP BY`
  expression are treated as different values by SQL Server.
- SQL Server limits a statement to 2,100 parameters.

The dialect leaves ordinary statements parameterized. It uses SQLAlchemy's
type-aware post-compile literal rendering for grouped expressions and expanding
parameters. A conservative fallback handles statements containing more than
2,099 individual parameters.


## Usage

Install the package and use `mssql+pyodbc_mssql` in place of
`mssql+pyodbc`:

```shell
pip install sqlalchemy_pyodbc_mssql
```

```text
mssql+pyodbc_mssql://user:password@server/database?driver=ODBC+Driver+18+for+SQL+Server
```

See SQLAlchemy's [Microsoft SQL Server documentation][sqlalchemy-mssql] for
pyodbc connection options.

[sqlalchemy-mssql]: https://docs.sqlalchemy.org/en/20/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pyodbc


## Dev


### Copier Template

Project structure and tooling mostly derives from
[Coppy](https://github.com/level12/coppy). See its documentation for context and
additional instructions.

This project can be updated from the upstream repo, see
[Updating a Project](https://github.com/level12/coppy?tab=readme-ov-file#template-updates).


### Project Setup

From zero to hero (passing tests that is):

1. Ensure [host dependencies](https://github.com/level12/coppy/wiki/Mise) are installed

2. Start docker service dependencies (if applicable):

   `docker compose up -d`

3. Sync [project](https://docs.astral.sh/uv/concepts/projects/) virtualenv w/ lock file:

   `uv sync`

4. Configure prek:

   `prek install`

5. Run tests:

   `nox`

The fast tests run without SQL Server. Live contract tests run when
`MSSQL_TEST_URL` is set. For ODBC Driver 18 and the supplied Compose service:

```shell
export MSSQL_TEST_URL='mssql+pyodbc_mssql://sa:SqlServer12!@127.0.0.1:1433/tempdb?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes'
nox -s pytest
```

CI uses Microsoft's official SQL Server 2022 image and probes readiness with
`sqlcmd` before starting the Python 3.12, 3.13, and 3.14 test sessions.


### Versions

Versions are date based. A `version` task shows and bumps versions:

```shell

  # Show current version
  mise run version show

  # Bump version based on date, tag, and push:
  mise run version bump

  # See other options
  mise run version -- --help
```
