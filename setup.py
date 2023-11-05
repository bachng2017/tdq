#!/usr/bin/env python
from setuptools import setup
from codecs import open
from os import path
import tdq._version

here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup (
    name='tdq',
    packages=['tdq'],
    version=tdq._version.__version__,
    license='Apache',
    install_requires=[
        "setuptools>=40.3.0",
    ],
    author='bachng',
    author_email='bachng@gmail.com',
    url='https://github.com/bachng2017/tdq',
    description='A Treasure Data query shell',
    long_description=long_description,
    long_description_content_type='text/markdown',
    keywords='python treasuredata shell sql',
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        'Programming Language :: Python :: 3.8',
    ],
    entry_points = {
        'console_scripts': ['tdq = tdq.shell:main'] },
    python_requires='>=3.8',
)
