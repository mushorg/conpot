from setuptools import setup, find_packages
import conpot

setup(
    name="conpot",
    version=conpot.__version__,
    packages=find_packages(exclude=["*.pyc"]),
    python_requires=">=3.6",
    scripts=["bin/conpot"],
    url="http://conpot.org",
    license="GPL 2",
    author="MushMush Foundation",
    author_email="glastopf@public.honeynet.org",
    classifiers=[
        "Development Status :: 6 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python",
        "Topic :: Security",
    ],
    package_data={
        "": ["*.txt", "*.rst"],
        "conpot": ["conpot.cfg", "tests/data/*"],
    },
    keywords="ICS SCADA honeypot",
    include_package_data=True,
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    description="""Conpot is an ICS honeypot with the goal to collect intelligence about the motives and methods of adversaries targeting industrial control systems""",
    install_requires=open("requirements.txt").read().splitlines(),
)
