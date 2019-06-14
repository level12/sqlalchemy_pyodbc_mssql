import binascii
import datetime
import decimal
import itertools
import logging
import uuid

try:
    from blazeform.util import NotGivenBase
except ImportError:
    NotGivenBase = None
import pyodbc
from sqlalchemy.dialects.mssql.pyodbc import MSDialect_pyodbc

log = logging.getLogger(__name__)


class MssqlDialect_pyodbc_quoted(MSDialect_pyodbc):
    @staticmethod  # noqa: C901
    def _quote_simple_value(value):
        """ Mainly from pymssql quoting, without the encoded output """

        if value is None:
            return 'NULL'

        if isinstance(value, bool):
            return '1' if value else '0'

        if isinstance(value, float):
            return repr(value)

        if isinstance(value, (int, decimal.Decimal)):
            return str(value)

        if isinstance(value, uuid.UUID):
            return MssqlDialect_pyodbc_quoted._quote_simple_value(str(value))

        if isinstance(value, str):
            return ("N'" + value.replace("'", "''") + "'")

        if isinstance(value, bytearray):
            return '0x' + binascii.hexlify(bytes(value)).decode()

        if isinstance(value, bytes):
            # see if it can be decoded as ascii if there are no null bytes
            if b'\0' not in value:
                try:
                    value.decode('ascii')
                    return "'" + value.replace(b"'", b"''").decode() + "'"
                except UnicodeDecodeError:
                    pass

            # Python 3: handle bytes
            # @todo - Marc - hack hack hack
            if isinstance(value, bytes):
                return (b'0x' + binascii.hexlify(value)).decode()

            # will still be string type if there was a null byte in it or if the
            # decoding failed.  In this case, just send it as hex.
            if isinstance(value, str):
                return '0x' + value.encode('hex')

        if isinstance(value, datetime.datetime):
            return "{ts '%04d-%02d-%02d %02d:%02d:%02d.%03d'}" % (
                value.year, value.month, value.day,
                value.hour, value.minute, value.second,
                value.microsecond / 1000)

        if isinstance(value, datetime.date):
            return "{d '%04d-%02d-%02d'}" % (value.year, value.month, value.day)

        if isinstance(value, tuple) and len(value) == 1:
            # Sometimes a result of a query will be provided as a filter to another query, but
            # the object passed may not be scalar. pymssql does some flattening on this, and
            # we should too.
            return MssqlDialect_pyodbc_quoted._quote_simple_value(value[0])

        return None

    @staticmethod
    def translate_custom_parameters(params):
        def translate(param):
            if type(param) == NotGivenBase:
                # This type comes from blazeform and is a representation of a null value
                return None
            if isinstance(param, tuple):
                # Sometimes a result of a query will be provided as a filter to another query, but
                # the object passed may not be scalar. pymssql does some flattening on this, and
                # we should too.
                return param[0]
            return param
        return [translate(param) for param in params]

    def roll_parameters_into_statement(self, statement, parameters):
        # transform here and pass on to cursor
        quoted_params = [self._quote_simple_value(param) for param in parameters]
        statement_list = statement.split('?')
        # Most efficient method I found for getting the lists put together. Assumes that
        # the number of parameters actually matches the number of ? placeholders.
        return ''.join([
            x for x in itertools.chain.from_iterable(
                itertools.zip_longest(statement_list, quoted_params)) if x
        ])

    def do_execute(self, cursor, statement, parameters, context=None):
        if (
            # maximum of 2100 parameters in a stored procedure
            # https://docs.microsoft.com/en-us/sql/sql-server/maximum-capacity-specifications-for-sql-server?view=sql-server-2017  # noqa
            len(parameters) > 2100
            # GROUP BY parameter mismatch issue
            # https://github.com/sqlalchemy/sqlalchemy/issues/4540
            or ('GROUP BY' in statement and parameters)
        ):
            statement = self.roll_parameters_into_statement(statement, parameters)
            # no need for parameters at this point, since they're all baked into the query
            parameters = tuple()

        try:
            cursor.execute(statement, self.translate_custom_parameters(parameters))
        except pyodbc.OperationalError:
            log.error('pyodbc OperationalError. Full statement: {}\n Params: {}'.format(
                statement, parameters
            ))
            raise
