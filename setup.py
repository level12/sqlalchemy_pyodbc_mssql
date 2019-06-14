import os.path as osp

from setuptools import setup, find_packages

cdir = osp.abspath(osp.dirname(__file__))
README = open(osp.join(cdir, 'readme.rst')).read()
CHANGELOG = open(osp.join(cdir, 'changelog.rst')).read()

version_fpath = osp.join(cdir, 'sqlalchemy_pyodbc_mssql', 'version.py')
version_globals = {}
with open(version_fpath) as fo:
    exec(fo.read(), version_globals)

setup(
    name='sqlalchemy_pyodbc_mssql',
    version=version_globals['VERSION'],
    description='SA dialect for MSSQL using PyODBC which handles MSSQL-specific limitations',
    long_description='\n\n'.join((README, CHANGELOG)),
    author='Matt Lewellyn',
    author_email='matt.lewellyn@level12.io',
    url='https://github.com/level12/sqlalchemy_pyodbc_mssql',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ],
    packages=find_packages(exclude=[]),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'pyodbc',
        'sqlalchemy >= 1.3.3',
    ],
    extras_require={
        'test': [
            'blazeform',
            'flake8',
            'pytest',
            'pytest-cov',
            'tox',
        ],
    },
    entry_points="""
        [sqlalchemy.dialects]
        mssql.pyodbc_mssql = sqlalchemy_pyodbc_mssql.dialect:MssqlDialect_pyodbc_quoted
    """,
)
