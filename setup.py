from distribute_setup import use_setuptools
use_setuptools()

from setuptools import setup, find_packages

setup(
    name='Conpot',
    version='0.1.0',
    packages=find_packages(),
    entry_points = {
        'console_scripts': [
            'conpot = conpot.conpot_ics_server:main',
        ]
    },
    package_data = {
        '': ['*.txt', '*.rst'],
        'conpot': ['*.xml'],
    },
    url='http://conpot.org',
    license='GPL 2',
    author='Glastopf Project',
    author_email='glastopf@public.honeynet.org',
    long_description=open('README.md').read(),
    test_suite='nose.collector',
    install_requires=open('requirements.txt').read().splitlines(),
    dependency_links = [
        "git+git://github.com/rep/hpfeeds.git"
        "git+git://github.com/glastopf/modbus-tk.git"
    ],
)