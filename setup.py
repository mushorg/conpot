from distribute_setup import use_setuptools
use_setuptools()

from setuptools import setup, find_packages

setup(
    name='Conpot',
    version='0.1.0',
    packages=find_packages(exclude=['templates', 'docs']),
    scripts = ['conpot_ics_server.py', 'config.py.dist'],
    url='http://conpot.org',
    license='GPL 2',
    author='Glastopf Project',
    author_email='glastopf@public.honeynet.org',
    long_description=open('README.md').read(),
    test_suite='nose.collector',
    install_requires=open('requirements.txt').read().splitlines(),
)