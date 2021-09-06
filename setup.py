from setuptools import setup
extras_require={}
extras_require['docs'] = sorted(
    set(
        [
            'sphinx-click',
            'sphinx-copybutton',
            'autoclasstoc',
        ]
    )
)
version = {}
with open("src/hepdata_maker/version.py") as fp:
    exec(fp.read(), version)
setup(
    extras_require=extras_require,
    version=version['__version__']
)
