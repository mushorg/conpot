import multiprocessing
from ez_setup import use_setuptools
use_setuptools()
from setuptools import setup, find_packages
import conpot

setup(
    name='Conpot',
    version=conpot.__version__,
    packages=find_packages(exclude=['*.pyc']),
    scripts=['bin/conpot'],
    url="http://conpot.org",
    license='GPL 2',
    author="MushMush Foundation",
    author_email="glastopf@public.honeynet.org",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 2 :: Only",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python",
        "Topic :: Security",
    ],
    package_data={
        "": ["*.txt", "*.rst"],
        "conpot": ["conpot.cfg", "tests/data/*"],
    },
    keywords="ICS SCADA honeypot",
    include_package_data=True,
    long_description=open('README.md').read(),
    description="""Conpot is an ICS honeypot with the goal to collect intelligence about the motives
    and methods of adversaries targeting industrial control systems""",
    test_suite='nose.collector',
    tests_require="nose",
    dependency_links=[
        "https://github.com/rep/hpfeeds/archive/master.zip#egg=hpfeeds",
    ],
    install_requires=open('requirements.txt').read().splitlines(),
)
