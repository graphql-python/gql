import sys
from setuptools import setup, find_packages

install_requires = [
    'six>=1.10.0',
    'graphql-core~=1.1',
    'promise>=0.4.0'
]

if sys.version_info < (3, 5):
    install_requires.append('futures')

setup(
    name='pygql',
    version='0.1.2',
    description='GraphQL client for Python',
    long_description=open('README.rst').read(),
    url='https://github.com/itolosa/pygql',
    author='Ignacio Tolosa',
    author_email='ignacio@perejil.cl',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    keywords='api graphql protocol rest relay gql client',
    packages=find_packages(include=["pygql*"]),
    install_requires=install_requires,
    tests_require=['pytest>=2.7.2', 'mock'],
)
