#!/usr/bin/env python3

from setuptools import setup, find_packages


setup(
    name='lanzou-gui',
    version='0.3.2',
    description='Lanzou Cloud GUI',
    license="MIT",
    author='rachpt',
    author_email='rachpt@126.com',
    packages=find_packages(),
    package_data={
        '': []
    },
    python_requires=">=3.8",
    url='https://github.com/rachpt/lanzou-gui',
    keywords=['lanzou', 'lanzoucloud', 'gui', 'application', 'PyQt5', 'Python 3'],
    classifiers=(
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3 :: Only',
        'Environment :: X11 Applications :: Qt',
        'Topic :: Internet',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS',
    ),
    install_requires=[
        'PyQt5',
        'PyQtWebEngine',
        'requests',
        'requests_toolbelt',
    ],
)
