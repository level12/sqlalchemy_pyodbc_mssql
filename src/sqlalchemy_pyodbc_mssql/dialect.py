import binascii
import datetime as dt
import decimal
import logging
import math
from typing import Any
import uuid

import pyodbc
from sqlalchemy.dialects.mssql.base import MSSQLCompiler
from sqlalchemy.dialects.mssql.pyodbc import MSDialect_pyodbc
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import BindParameter


log = logging.getLogger(__name__)

# SQL Server documents a 2,100 parameter limit. SQLAlchemy itself uses 2,099
# as the safe upper bound for its insertmanyvalues implementation.
MAX_PARAMETERS = 2099


class MssqlCompilerPyodbcQuoted(MSSQLCompiler):
    """Use SQLAlchemy's literal processors for known-problematic bind parameters."""

    _literal_group_by_bind_keys = frozenset()

    def visit_select(self, select_stmt, **kwargs):
        previous = self._literal_group_by_bind_keys
        group_by_bind_keys = {
            element.key
            for clause in select_stmt._group_by_clauses
            for element in visitors.iterate(clause)
            if isinstance(element, BindParameter)
        }
        self._literal_group_by_bind_keys = previous | group_by_bind_keys
        try:
            return super().visit_select(select_stmt, **kwargs)
        finally:
            self._literal_group_by_bind_keys = previous

    def visit_bindparam(self, bindparam, **kwargs):
        # Positional ODBC parameters repeated in SELECT and GROUP BY are distinct
        # expressions to SQL Server, even when they originated from the same
        # SQLAlchemy bind. Expanding parameters can also exceed SQL Server's
        # parameter limit. SQLAlchemy's post-compile literal rendering solves
        # both cases without parsing SQL or quoting values ourselves.
        if bindparam.key in self._literal_group_by_bind_keys or bindparam.expanding:
            kwargs['literal_execute'] = True
        return super().visit_bindparam(bindparam, **kwargs)


class MssqlDialectPyodbcQuoted(MSDialect_pyodbc):
    statement_compiler = MssqlCompilerPyodbcQuoted
    supports_statement_cache = True

    @staticmethod
    def _quote_simple_value(value: Any) -> str:
        """Render a processed DBAPI value as a SQL Server literal.

        This is a fallback for unusually large statements made from more than
        2,099 individual binds. Normal GROUP BY and expanding-IN parameters are
        rendered by SQLAlchemy's type-aware literal processors instead.
        """
        if value is None:
            return 'NULL'
        if isinstance(value, bool):
            return '1' if value else '0'
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError('SQL Server cannot render a non-finite float literal')
            return repr(value)
        if isinstance(value, decimal.Decimal):
            if not value.is_finite():
                raise ValueError('SQL Server cannot render a non-finite decimal literal')
            return str(value)
        if isinstance(value, uuid.UUID):
            return f"'{value}'"
        if isinstance(value, str):
            return "N'" + value.replace("'", "''") + "'"
        if isinstance(value, (bytes, bytearray, memoryview)):
            return '0x' + binascii.hexlify(bytes(value)).decode('ascii')
        if isinstance(value, dt.datetime):
            return f"'{value.isoformat(sep=' ')}'"
        if isinstance(value, dt.date):
            return f"'{value.isoformat()}'"
        if isinstance(value, dt.time):
            return f"'{value.isoformat()}'"
        raise TypeError(f'Cannot safely render parameter of type {type(value).__name__}')

    @classmethod
    def roll_parameters_into_statement(cls, statement, parameters):
        """Replace actual qmark placeholders while preserving SQL text."""
        quoted = iter(cls._quote_simple_value(value) for value in parameters)
        output: list[str] = []
        replaced = 0
        index = 0
        state = 'sql'
        block_depth = 0

        while index < len(statement):
            char = statement[index]
            following = statement[index + 1] if index + 1 < len(statement) else ''

            if state == 'sql':
                if char == "'":
                    state = 'single'
                elif char == '"':
                    state = 'double'
                elif char == '[':
                    state = 'bracket'
                elif char == '-' and following == '-':
                    state = 'line_comment'
                elif char == '/' and following == '*':
                    state = 'block_comment'
                    block_depth = 1
                elif char == '?':
                    try:
                        output.append(next(quoted))
                    except StopIteration as exc:
                        raise ValueError('More placeholders than parameters') from exc
                    replaced += 1
                    index += 1
                    continue
            elif state == 'single' and char == "'":
                if following == "'":
                    output.extend((char, following))
                    index += 2
                    continue
                state = 'sql'
            elif state == 'double' and char == '"':
                if following == '"':
                    output.extend((char, following))
                    index += 2
                    continue
                state = 'sql'
            elif state == 'bracket' and char == ']':
                if following == ']':
                    output.extend((char, following))
                    index += 2
                    continue
                state = 'sql'
            elif state == 'line_comment' and char in '\r\n':
                state = 'sql'
            elif state == 'block_comment':
                if char == '/' and following == '*':
                    block_depth += 1
                elif char == '*' and following == '/':
                    block_depth -= 1
                    if block_depth == 0:
                        state = 'sql'

            output.append(char)
            index += 1

        try:
            next(quoted)
        except StopIteration:
            return ''.join(output)
        raise ValueError(f'More parameters than placeholders ({replaced} replaced)')

    def do_execute(self, cursor, statement, parameters, context=None):
        if len(parameters) > MAX_PARAMETERS:
            statement = self.roll_parameters_into_statement(statement, parameters)
            parameters = ()

        try:
            cursor.execute(statement, parameters)
        except pyodbc.Error:
            log.exception(
                'pyodbc error executing statement: %s\nParameters: %r',
                statement,
                parameters,
            )
            raise


# Preserve the original public class name for existing applications.
MssqlDialect_pyodbc_quoted = MssqlDialectPyodbcQuoted
