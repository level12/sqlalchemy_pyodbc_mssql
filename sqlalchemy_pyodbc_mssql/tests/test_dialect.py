import datetime
from decimal import Decimal
from unittest import mock
from uuid import UUID

import pyodbc
import pytest
from sqlalchemy import table, column, Integer, String, select, sql

from sqlalchemy_pyodbc_mssql import dialect


class TestDialect:
    __dialect__ = dialect.MssqlDialect_pyodbc_quoted()

    def get_cursor(self):
        return mock.Mock(spec=pyodbc.Cursor)

    def test_dialect_registered(self):
        from sqlalchemy.dialects import registry
        assert registry.load('mssql.pyodbc_mssql') is dialect.MssqlDialect_pyodbc_quoted

    @pytest.mark.parametrize('parameter, output', [
        (None, 'NULL'),
        (True, '1'),
        (False, '0'),
        (5, '5'),
        (0.5, '0.5'),
        (Decimal('0.5'), '0.5'),
        (UUID('f9dad6af-eb1f-4d23-8b30-157eda50d8cd'), 'N\'f9dad6af-eb1f-4d23-8b30-157eda50d8cd\''),
        ('foobar', 'N\'foobar\''),
        (bytearray([1, 2, 3]), '0x010203'),
        (b'foo', '\'foo\''),
        (b'foo\0bar', '0x666f6f00626172'),
        (datetime.datetime(2018, 5, 31, 4, 5, 6, 7000), '{ts \'2018-05-31 04:05:06.007\'}'),
        (datetime.date(2018, 5, 31), '{d \'2018-05-31\'}'),
        ((1, ), '1'),
    ])
    def test_quotes_parameter_types(self, parameter, output):
        assert self.__dialect__._quote_simple_value(parameter) == output

    def test_uses_custom_compiler(self):
        table1 = table(
            "mytable",
            column("myid", Integer),
            column("name", String),
            column("description", String),
        )

        q = select(
            [table1.c.myid, sql.literal('bar').label('c1')],
            order_by=[table1.c.name + '-']
        ).alias("foo")
        crit = q.c.myid == table1.c.myid
        compiled = select(["*"], crit).compile(dialect=self.__dialect__)

        assert compiled.construct_params() == {'param_1': 'bar'}

    def test_translates_notgivenbase(self):
        from blazeform.util import NotGivenBase
        cursor = self.get_cursor()
        self.__dialect__.do_execute(cursor, 'foo', (NotGivenBase(), ))

        cursor.execute.assert_called_once_with('foo', [None])

    def test_translates_single_element_tuple(self):
        cursor = self.get_cursor()
        self.__dialect__.do_execute(cursor, 'foo', ((42, ), ))

        cursor.execute.assert_called_once_with('foo', [42])

    def test_substitutes_params_for_group_by(self):
        cursor = self.get_cursor()
        sql = 'SELECT foo + ? FROM bar GROUP BY foo + ?'
        sql_check = 'SELECT foo + 9 FROM bar GROUP BY foo + 10'
        params = (9, 10)
        self.__dialect__.do_execute(cursor, sql, params)

        cursor.execute.assert_called_once_with(sql_check, [])

    def test_too_many_parameters(self):
        cursor = self.get_cursor()

        sql = 'SELECT {} FROM bar'.format(','.join(['?' for _ in range(2100)]))
        params = [1 for _ in range(2100)]
        self.__dialect__.do_execute(cursor, sql, params)

        cursor.execute.assert_called_once_with(sql, params)
        cursor.reset_mock()

        sql = 'SELECT {} FROM bar'.format(','.join(['?' for _ in range(2101)]))
        sql_check = 'SELECT {} FROM bar'.format(','.join(['1' for _ in range(2101)]))
        params = [1 for _ in range(2101)]
        self.__dialect__.do_execute(cursor, sql_check, [])

    @mock.patch('sqlalchemy_pyodbc_mssql.dialect.log', autospec=True, spec_set=True)
    def test_error_10004_logging(self, m_log):
        cursor = self.get_cursor()
        m_execute = mock.Mock()
        m_execute.side_effect = pyodbc.OperationalError()

        with mock.patch.object(cursor, 'execute', m_execute):
            sql = 'SELECT count(*) AS count_1'
            params = (1, 2, 3)
            with pytest.raises(pyodbc.OperationalError):
                self.__dialect__.do_execute(cursor, sql, params)

        m_log.error.assert_called_once_with(
            'pyodbc OperationalError. Full statement: SELECT count(*) AS count_1'
            '\n Params: (1, 2, 3)'
        )
