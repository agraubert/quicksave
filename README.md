# quicksave
[![PyPI](https://img.shields.io/pypi/v/quicksave.svg)](https://pypi.python.org/pypi/quicksave)
[![Build Status](https://travis-ci.org/agraubert/quicksave.svg?branch=master)](https://travis-ci.org/agraubert/quicksave)
[![Coverage Status](https://coveralls.io/repos/github/agraubert/quicksave/badge.svg?branch=master)](https://coveralls.io/github/agraubert/quicksave?branch=master)

A (very) simple file versioning system

__Version:__ 1.3.0

Detailed documentation on the available commands can be found on the [quicksave wiki](https://github.com/agraubert/quicksave/wiki)

#### Getting started:
The first thing you'll need to do is create a new database:
```
$ quicksave init <path>
```
That will setup the new database so it's ready to use.

After that, you're good to go.  You can `register` new files so they're tracked by quicksave, `save` new states of registered files, and `revert` to previously saved states.  There are several other commands which modify the database itself, but I'm only covering those three listed commands in this guide (and none of their various options).  For detailed documentation on all of the available commands, check out the [wiki page](https://github.com/agraubert/quicksave/wiki).

To track (AKA register) a new file in quicksave use:
```
$ quicksave register <filepath>
```

Which will copy the initial state of the file, and provide the names of the file and state keys you'll need use this file. For a brief description of file and state keys, see [this note](https://github.com/agraubert/quicksave/wiki#a-note-on-file-and-state-keys) on the wiki.

To then save a new state of the file, use the save command:
```
$ quicksave save <filepath>
```

Quicksave will use the the absolute path and the base file name derived from _filepath_ to automatically decide which file key to use.

Lastly, to get the file back into a previously saved state, use the revert command:
```
$ quicksave revert <filepath> <state>
```

Again, quicksave will attempt to determine which file key to use based on the absolute path and the file name.  Quicksave will lookup the provided _state_ key and revert the file.
