import datetime as dt
from decimal import Decimal
from unittest import mock
from uuid import UUID

import pyodbc
import pytest
from sqlalchemy import Integer, String, bindparam, column, literal, select, table
from sqlalchemy.dialects import registry

from sqlalchemy_pyodbc_mssql.dialect import MAX_PARAMETERS, MssqlDialectPyodbcQuoted


@pytest.fixture
def dialect():
    return MssqlDialectPyodbcQuoted(paramstyle='qmark')


def test_dialect_registered():
    assert registry.load('mssql.pyodbc_mssql') is MssqlDialectPyodbcQuoted


@pytest.mark.parametrize(
    ('parameter', 'output'),
    [
        (None, 'NULL'),
        (True, '1'),
        (False, '0'),
        (5, '5'),
        (0.5, '0.5'),
        (Decimal('0.5'), '0.5'),
        (UUID('f9dad6af-eb1f-4d23-8b30-157eda50d8cd'), "'f9dad6af-eb1f-4d23-8b30-157eda50d8cd'"),
        ("foo'bar", "N'foo''bar'"),
        (bytearray([1, 2, 3]), '0x010203'),
        (b'foo\0bar', '0x666f6f00626172'),
        (dt.datetime(2018, 5, 31, 4, 5, 6, 7000), "'2018-05-31 04:05:06.007000'"),
        (dt.date(2018, 5, 31), "'2018-05-31'"),
        (dt.time(4, 5, 6, 7000), "'04:05:06.007000'"),
    ],
)
def test_quotes_fallback_parameter_types(dialect, parameter, output):
    assert dialect._quote_simple_value(parameter) == output


def test_normal_statement_remains_parameterized(dialect):
    source = table('things', column('value', Integer))
    compiled = select(source.c.value).where(source.c.value == 42).compile(dialect=dialect)

    assert '?' in str(compiled)
    assert compiled.params == {'value_1': 42}


def test_group_by_uses_sqlalchemy_postcompile_literals(dialect):
    source = table('things', column('value', String))
    grouped = literal('prefix-') + source.c.value
    statement = select(grouped, literal("O'Brien")).group_by(grouped)

    compiled = statement.compile(dialect=dialect, compile_kwargs={'render_postcompile': True})

    assert str(compiled).count('?') == 1
    assert "'prefix-'" in str(compiled)
    assert compiled.params == {'param_2': "O'Brien"}


def test_group_by_postcompile_values_are_safe_for_statement_cache(dialect):
    source = table('things', column('value', String))
    prefix = bindparam('prefix', type_=String)
    statement = select(prefix + source.c.value).group_by(prefix + source.c.value)
    compiled = statement.compile(dialect=dialect)

    first = compiled.construct_expanded_state({'prefix': 'first-'})
    second = compiled.construct_expanded_state({'prefix': 'second-'})

    assert "'first-'" in first.statement
    assert "'second-'" in second.statement
    assert '?' not in first.statement
    assert '?' not in second.statement


def test_nested_select_does_not_literalize_unrelated_binds(dialect):
    source = table('things', column('value', String))
    prefix = bindparam('prefix', 'group-')
    inner = select(bindparam('inner', 'inner-only')).scalar_subquery()
    statement = (
        select(prefix + source.c.value, inner)
        .where(source.c.value == bindparam('where_value', 'where-only'))
        .group_by(prefix + source.c.value)
    )

    compiled = statement.compile(dialect=dialect, compile_kwargs={'render_postcompile': True})

    assert str(compiled).count("'group-'") == 2
    assert str(compiled).count('?') == 2
    assert compiled.params == {'inner': 'inner-only', 'where_value': 'where-only'}


def test_expanding_bind_uses_sqlalchemy_postcompile_literals(dialect):
    source = table('things', column('value', Integer))
    statement = select(source.c.value).where(source.c.value.in_(range(MAX_PARAMETERS + 2)))

    compiled = statement.compile(dialect=dialect, compile_kwargs={'render_postcompile': True})

    assert '?' not in str(compiled)
    assert len(compiled.params) == 0
    assert str(MAX_PARAMETERS + 1) in str(compiled)


def test_large_nonexpanding_statement_uses_safe_fallback(dialect):
    cursor = mock.Mock(spec=pyodbc.Cursor)
    parameters = tuple(range(MAX_PARAMETERS + 1))
    placeholders = ', '.join('?' for _ in parameters)
    statement = (
        f'SELECT \'it\'\'s ?\', [question?]]name], "quoted?""name", {placeholders} '
        '/* outer ? /* inner ? */ end */ -- comment ?'
    )

    dialect.do_execute(cursor, statement, parameters)

    executed_statement, executed_parameters = cursor.execute.call_args.args
    assert executed_statement.startswith(
        'SELECT \'it\'\'s ?\', [question?]]name], "quoted?""name", 0, 1',
    )
    assert executed_statement.endswith(
        f'{MAX_PARAMETERS} /* outer ? /* inner ? */ end */ -- comment ?',
    )
    assert executed_parameters == ()


def test_fallback_refuses_unsupported_values(dialect):
    with pytest.raises(TypeError, match='Cannot safely render'):
        dialect._quote_simple_value(object())


@pytest.mark.parametrize(
    'value',
    [float('inf'), float('-inf'), float('nan'), Decimal('Infinity'), Decimal('NaN')],
)
def test_fallback_refuses_non_finite_numbers(dialect, value):
    with pytest.raises(ValueError, match='non-finite'):
        dialect._quote_simple_value(value)
