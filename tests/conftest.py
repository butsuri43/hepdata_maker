import pytest
import os
import pathlib
import distutils.dir_util


# fixture 'datadir' copied directly from:
# https://github.com/scikit-hep/pyhf/blob/master/tests/test_export.py
@pytest.fixture(scope='function')
def datadir(tmpdir, request):
    """
    Fixture responsible for searching a folder with the same name of test
    module and, if available, moving all contents to a temporary directory so
    tests can use them freely.
    """
    # this gets the module name (e.g. /path/to/pyhf/tests/test_schema.py)
    # and then gets the directory by removing the suffix (e.g. /path/to/pyhf/tests/test_schema)
    test_dir = pathlib.Path(request.module.__file__).with_suffix('')

    if test_dir.is_dir():
        distutils.dir_util.copy_tree(test_dir, tmpdir.strpath)
        # shutil is nicer, but doesn't work: https://bugs.python.org/issue20849
        # shutil.copytree(test_dir, tmpdir)

    return tmpdir
