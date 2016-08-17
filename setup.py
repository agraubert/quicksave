from setuptools import setup
import os.path
import re

long_desc = "A (very) simple file versioning system"


if not os.path.isfile("README.rst"):
    import pypandoc
    pypandoc.convert_file("README.md", 'rst', outputfile="README.rst")
reader = open("README.rst", mode='r')
long_desc = reader.read()
version = re.search(r'\*\*Version:\*\* ([0-9\.a-zA-Z]*)', long_desc).group(1)
reader.close()

setup(
    name="quicksave",
    version=version,
    packages=[
        "quicksave"
    ],
    entry_points={
        "console_scripts":[
            "quicksave = quicksave.__main__:main",
        ]
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',

        'Topic :: Utilities',

        'License :: OSI Approved :: MIT License',

        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: Implementation :: PyPy"
    ],

    author = "Aaron Graubert",
    author_email = "captianjroot@live.com",
    description = "A (very) simple file versioning system",
    long_description = long_desc,
    license = "MIT",
    keywords = "version control",
    url = "https://github.com/agraubert/quicksave",   #
)
