import nox
from nox_uv import session


nox.options.default_venv_backend = 'uv'
nox.options.reuse_existing_virtualenvs = True


# nox -l
# nox -v -s "tests-3.12(rich='15.0')"
# nox -v --parallel 5 --allow-parallel -p 3.12 3.14

PYTHON_VERSIONS = ['3.11', '3.12', '3.13', '3.14', '3.15']


@session(python=PYTHON_VERSIONS, uv_extras=['all'], uv_groups=['tests'])
def tests(session: nox.Session):
    # session.install('setuptools', 'wheel')
    session.run('pytest', *session.posargs)


@session(python=PYTHON_VERSIONS, uv_extras=['all'], uv_groups=['sca'])
def lint(session: nox.Session):
    if not session.posargs:
        session.run('ruff', 'check', '.')
    else:
        session.run('ruff', 'check', *session.posargs)


@session(python=PYTHON_VERSIONS, uv_extras=['all'], uv_groups=['sca', 'tests'])
def typecheck(session: nox.Session):
    if not session.posargs:
        session.run('mypy', '.')
    else:
        session.run('mypy', *session.posargs)


@session(python=PYTHON_VERSIONS, uv_extras=['all'], uv_groups=['sca'])
def seccheck(session: nox.Session):
    if not session.posargs:
        session.run('bandit', '-c', 'pyproject.toml', '-r', '.')
    else:
        session.run('bandit', '-c', 'pyproject.toml', *session.posargs)
