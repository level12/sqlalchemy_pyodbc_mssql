import datetime as dt
from decimal import Decimal
import os
import uuid

import pytest
from sqlalchemy import Column, MetaData, String, Table, func, literal, literal_column, select
from sqlalchemy.engine import create_engine, make_url
from sqlalchemy.exc import DBAPIError

from sqlalchemy_pyodbc_mssql.dialect import MAX_PARAMETERS


pytestmark = pytest.mark.live_sql_server


@pytest.fixture(scope='module')
def engine():
    url = os.environ.get('MSSQL_TEST_URL')
    if not url:
        pytest.skip('MSSQL_TEST_URL is not configured')

    current = create_engine(url)
    try:
        with current.connect() as connection:
            connection.exec_driver_sql('SELECT 1')
    except DBAPIError as exc:
        current.dispose()
        pytest.fail(f'MSSQL_TEST_URL is configured but SQL Server is unavailable: {exc}')
    yield current
    current.dispose()


@pytest.fixture(scope='module')
def builtin_engine(engine):
    url = make_url(os.environ['MSSQL_TEST_URL']).set(drivername='mssql+pyodbc')
    builtin = create_engine(url)
    yield builtin
    builtin.dispose()


def test_parameterized_group_by_works_around_builtin_failure(engine, builtin_engine):
    metadata = MetaData()
    source = Table(
        f'dialect_grouping_{uuid.uuid4().hex}',
        metadata,
        Column('part_number', String(20), nullable=False),
    )
    metadata.create_all(engine)
    try:
        with engine.begin() as connection:
            connection.execute(
                source.insert(),
                [{'part_number': 'ABC123'}, {'part_number': 'XYZ123'}],
            )

        suffix = literal('-') + func.right(source.c.part_number, literal(3))
        statement = select(suffix, func.count()).group_by(suffix).order_by(suffix)

        with builtin_engine.connect() as connection, pytest.raises(DBAPIError):
            connection.execute(statement).all()

        with engine.connect() as connection:
            assert connection.execute(statement).all() == [('-123', 2)]
    finally:
        metadata.drop_all(engine)


def test_expanding_query_at_fallback_boundary(engine, builtin_engine):
    values = list(range(MAX_PARAMETERS + 1))
    statement = select(literal_column('1')).where(literal_column('1').in_(values))

    with builtin_engine.connect() as connection, pytest.raises(DBAPIError):
        connection.execute(statement).scalar_one()

    with engine.connect() as connection:
        assert connection.execute(statement).scalar_one() == 1


def _normalize_uuid(value):
    return uuid.UUID(str(value))


def _normalize_binary(value):
    return bytes(value)


@pytest.mark.parametrize(
    ('value', 'sql_type', 'expected', 'normalize'),
    [
        pytest.param(None, 'int', None, None, id='null'),
        pytest.param(True, 'bit', True, None, id='true'),
        pytest.param(False, 'bit', False, None, id='false'),
        pytest.param(-9223372036854775807, 'bigint', -9223372036854775807, None, id='integer'),
        pytest.param(12345.125, 'float', 12345.125, None, id='float'),
        pytest.param(
            Decimal('1234567890.123456'),
            'decimal(24, 6)',
            Decimal('1234567890.123456'),
            None,
            id='decimal',
        ),
        pytest.param(
            uuid.UUID('f9dad6af-eb1f-4d23-8b30-157eda50d8cd'),
            'uniqueidentifier',
            uuid.UUID('f9dad6af-eb1f-4d23-8b30-157eda50d8cd'),
            _normalize_uuid,
            id='uuid',
        ),
        pytest.param(
            "snowman ☃ and quote ' ok",
            'nvarchar(100)',
            "snowman ☃ and quote ' ok",
            None,
            id='unicode-string',
        ),
        pytest.param(b'foo\0bar', 'varbinary(max)', b'foo\0bar', _normalize_binary, id='bytes'),
        pytest.param(
            bytearray([0, 1, 2, 255]),
            'varbinary(max)',
            b'\x00\x01\x02\xff',
            _normalize_binary,
            id='bytearray',
        ),
        pytest.param(
            memoryview(b'memory'),
            'varbinary(max)',
            b'memory',
            _normalize_binary,
            id='memoryview',
        ),
        pytest.param(
            dt.datetime(2026, 11, 18, 13, 14, 15, 123456),
            'datetime2(6)',
            dt.datetime(2026, 11, 18, 13, 14, 15, 123456),
            None,
            id='datetime',
        ),
        pytest.param(dt.date(2026, 11, 18), 'date', dt.date(2026, 11, 18), None, id='date'),
        pytest.param(
            dt.time(13, 14, 15, 123456),
            'time(6)',
            dt.time(13, 14, 15, 123456),
            None,
            id='time',
        ),
    ],
)
def test_fallback_quoting_types_execute_on_sql_server(engine, value, sql_type, expected, normalize):
    # One value plus 2,099 predicate parameters exercises the fallback at its
    # exact 2,100-parameter boundary. The CAST makes SQL Server validate the
    # generated literal against the intended destination type.
    predicate_parameters = [1] * MAX_PARAMETERS
    placeholders = ', '.join('?' for _ in predicate_parameters)
    statement = f'SELECT CAST(? AS {sql_type}) WHERE 1 IN ({placeholders})'

    with engine.connect() as connection:
        actual = connection.exec_driver_sql(
            statement,
            (value, *predicate_parameters),
        ).scalar_one()

    if normalize is not None:
        actual = normalize(actual)
    assert actual == expected
