#!/usr/bin/env python
# -*- coding: utf-8 -*-
# © 2016 ACSONE SA/NV
# License AGPLv3 (http://www.gnu.org/licenses/agpl-3.0-standalone.html)

import setuptools

setuptools.setup(
    name='buildbot-utils',
    version='1.0.0b1',
    description='A library to help test odoo with buildbot',
    long_description='\n'.join((
        open('README.rst').read(),
    )),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: '
            'GNU Affero General Public License v3 or later (AGPLv3+)',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 2.7',
        'Topic :: Utilities',
        'Topic :: System :: Shells',
    ],
    license='AGPLv3+',
    author='ACSONE SA/NV',
    author_email='info@acsone.eu',
    url='http://github.com/acsone/buildot-utils',
    packages=[
        'buildbot_utils',
    ],
    install_requires=[
    ],
    test_suite='tests',
    entry_points={
        'console_scripts': [
            "test_odoo_server="
            "buildbot_utils.test_odoo_server:main",
        ],
    },
)
