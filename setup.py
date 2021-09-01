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
setup(extras_require=extras_require)
