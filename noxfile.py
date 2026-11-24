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
