#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import codecs
from setuptools import setup


def read(fname):
    file_path = os.path.join(os.path.dirname(__file__), fname)
    return codecs.open(file_path, encoding='utf-8').read()


setup(
    name='pytest-salt-containers',
    version='0.2.3',
    author='Mihai Dinca',
    author_email='dincamihai@gmail.com',
    maintainer='Mihai Dinca',
    maintainer_email='dincamihai@gmail.com',
    license='MIT',
    url='https://github.com/dincamihai/pytest-salt-containers',
    description='A Pytest plugin that builds and creates docker containers',
    long_description=read('README.rst'),
    packages=['saltcontainers'],
    install_requires=[
        'pytest>=2.9.1',
        'docker-py==1.8.0',
        'fake-factory',
        'factory-boy',
        'PyYAML',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Pytest',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Testing',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: MIT License',
    ],
    entry_points={
        'pytest11': [
            'containers = saltcontainers.plugin',
        ],
    },
)
