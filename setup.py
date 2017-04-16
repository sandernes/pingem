#!/usr/bin/env python

import setuptools

with open('README.rst') as f:
    readme = f.read()

setuptools.setup(
    name='pingem',
    version='0.1.dev0',
    description='Ping multiple hosts in parallel',
    long_description=readme,
    license='MIT',
    url='https://github.com/sandernes/pingem',
    author='Sander Ernes',
    author_email='sander.ernes@gmail.com',

    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Networking :: Monitoring',
    ],

    packages=setuptools.find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    install_requires=[
        'pyev',
    ],
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    zip_safe=True,
)
