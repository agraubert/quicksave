import os
import csv
import argparse
import sys
from hashlib import sha256
from .qs_database import Database as db
_SPECIAL_FILE = ['~trash', '~last']
_SPECIAL_STATE = ['~stash', '~trash']
_CURRENT_DATABASE = None
_FLAGS = {}
configfile = os.path.join(os.path.expanduser('~'), '.quicksave_config')

def _fetch_db(do_print, init=True):
    if init:
        initdb(do_print)
    return _CURRENT_DATABASE

def _do_print(PRINT_ENABLED, *args, **kwargs):
    if PRINT_ENABLED:
        print(*args, **kwargs)

def _checkflag(flagname, default):
    if flagname in _CURRENT_DATABASE.flags:
        return _CURRENT_DATABASE.flags[flagname]
    if flagname in _FLAGS:
        return _FLAGS[flagname]
    return default

def _loadflags(raw_reader):
    reader = csv.reader(raw_reader, delimiter='\t')
    for line in reader:
        _FLAGS[line[0]] = line[1]
    raw_reader.close()

def _fetch_flags(do_print, init=True):
    if init:
        initdb(do_print)
    return _FLAGS

def check_is_directory(argument):
    fullpath = os.path.abspath(argument)
    if os.path.isfile(fullpath):
        raise argparse.ArgumentTypeError("Path \"%s\" must be a directory"%argument)
    if not os.path.isdir(fullpath):
        os.makedirs(fullpath)
    return fullpath

def initdb(do_print):
    global _CURRENT_DATABASE
    database_path = ''
    msg = "No database loaded.  Please run '$ quicksave init' to create or load a database"
    if os.path.isfile(configfile):
        reader = open(configfile)
        database_path = reader.readline().strip()
        if database_path != "<N/A>":
            try:
                _CURRENT_DATABASE = db(database_path)
                _loadflags(reader)
            except FileNotFoundError:
                do_print("Bad database path:", database_path)
                msg = "Unable to open the database.  It may have been deleted, or the config file may have been manually edited. Run '$ quicksave init <databse path>' to resolve"
            except:
                sys.exit("The database is corrupted.  Use '$ quicksave init <database path>' and initialize a new database")
    if not _CURRENT_DATABASE:
        writer = open(configfile, mode='w')
        writer.write("<N/A>\n")
        writer.close()
        sys.exit(msg)
    return database_path

def gethash(reader):
    hasher = sha256()
    chunk = reader.read(4096)
    while len(chunk):
        hasher.update(chunk)
        chunk = reader.read(4096)
    return hasher.hexdigest()

def fetchstate(hashalias, filekey):
    if filekey+":"+hashalias in _CURRENT_DATABASE.state_keys:
        return _CURRENT_DATABASE.resolve_key(filekey+":"+hashalias, False)
    return None
