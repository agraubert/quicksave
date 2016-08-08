import argparse
import os
import sys
from shutil import copyfile, rmtree
from hashlib import sha256

try:
    from .qs_database import Database as db
except ImportError:
    sys.path.append(os.path.dirname(__file__))
    from qs_database import Database as db

_SPECIAL_FILE = ['~trash', '~last']
_SPECIAL_STATE = ['~stash', '~trash']
_CURRENT_DATABASE = None
configfile = os.path.join(os.path.expanduser('~'), '.quicksave_config')

def check_is_directory(argument):
    fullpath = os.path.abspath(argument)
    if os.path.isfile(fullpath):
        raise argparse.ArgumentTypeError("Path \"%s\" must be a directory"%argument)
    os.makedirs(fullpath, exist_ok=True)
    return fullpath

def read_write_file_exists(argument):
    fullpath = os.path.abspath(argument)
    if not os.path.isfile(fullpath):
        raise argparse.ArgumentTypeError("Path \"%s\" must be a file"%argument)
    return open(fullpath, 'a+b')

def initdb():
    global _CURRENT_DATABASE
    database_path = ''
    msg = "No database loaded.  Please run '$ quicksave init' to create or load a database"
    if os.path.isfile(configfile):
        reader = open(configfile)
        database_path = reader.read().strip()
        reader.close()
        if database_path != "<N/A>":
            try:
                _CURRENT_DATABASE = db(database_path)
            except FileNotFoundError:
                print("Bad database path:", database_path)
                msg = "Unable to open the database.  It may have been deleted, or the config file may have been manually edited. Run '$ quicksave init <databse path>' to resolve"
            except:
                sys.exit("The database is corrupted.  Use '$ quicksave init <database path>' and initialize a new database")
    if not _CURRENT_DATABASE:
        writer = open(configfile, mode='w')
        writer.write("<N/A>\n")
        writer.close()
        sys.exit(msg)
    return database_path

def command_init(args):
    writer = open(configfile, mode='w')
    writer.write(args.database_path+'\n')
    writer.close()

def command_register(args):
    initdb()
    filepath = os.path.abspath(args.filename.name)
    if filepath in _CURRENT_DATABASE.file_keys and not args.ignore_filepath:
        sys.exit("Unable to register: Filepath is registered to file key %s (use --ignore-filepath to override this behavior)"%(
            _CURRENT_DATABASE.file_keys[filepath][0]
        ))
    (key, folder) = _CURRENT_DATABASE.register_fk(filepath)
    _CURRENT_DATABASE.register_fa(key, '~last', True)
    if key in _SPECIAL_FILE:
        sys.exit("Unable to register: The provided filename overwrites a reserved file key (%s)"%key)
    file_aliases = []
    if len(args.file_alias):
        for user_alias in args.file_alias:
            if user_alias in _SPECIAL_FILE:
                sys.exit("Unable to register: Cannot create a file alias which overwrites a reserved file key (%s)"%user_alias)
            if _CURRENT_DATABASE.register_fa(key, user_alias):
                file_aliases.append(''+user_alias)
        if not len(file_aliases):
            sys.exit("Unable to register: None of the provided aliases were available")
    if filepath not in _SPECIAL_FILE and _CURRENT_DATABASE.register_fa(key, filepath):
        file_aliases.append(filepath)
    if os.path.basename(filepath) not in _SPECIAL_FILE and _CURRENT_DATABASE.register_fa(key, os.path.basename(filepath)):
        file_aliases.append(os.path.basename(filepath))
    (statekey, datafile) = _CURRENT_DATABASE.register_sk(key, os.path.relpath(filepath))
    hasher = sha256()
    chunk = args.filename.read(4096)
    while len(chunk):
        hasher.update(chunk)
        chunk = args.filename.read(4096)
    args.filename.close()
    hashalias = hasher.hexdigest()
    _CURRENT_DATABASE.register_sa(key, statekey, hashalias)
    state_aliases = []
    if key+":"+hashalias[:7] in _CURRENT_DATABASE.state_keys:
        del _CURRENT_DATABASE.state_keys[key+":"+hashalias[:7]]
    else:
        _CURRENT_DATABASE.register_sa(key, statekey, hashalias[:7])
        state_aliases.append(hashalias[:7])
    if len(args.aliases):
        for user_alias in args.aliases:
            if user_alias in _SPECIAL_STATE:
                sys.exit("Unable to register: Cannot create a state alias which overwrites a reserved state key (%s)" % user_alias)
            if _CURRENT_DATABASE.register_sa(key, statekey, user_alias):
                state_aliases.append(''+user_alias)
        if not len(state_aliases):
            sys.exit("Unable to save: None of the provided aliases were available")
    _CURRENT_DATABASE.save()
    print("Registered new file key:", key)
    print("Aliases for this file key:", file_aliases)
    print("Initial state key:", statekey)
    print("Aliases for this state key:", state_aliases)

def command_save(args):
    initdb()
    infer = not bool(args.file_key)
    if infer:
        filepath = os.path.abspath(args.filename.name)
        if filepath in _CURRENT_DATABASE.file_keys:
            args.file_key = _CURRENT_DATABASE.resolve_key(filepath, True)
        elif os.path.basename(filepath) in _CURRENT_DATABASE.file_keys:
            args.file_key = _CURRENT_DATABASE.resolve_key(os.path.basename(filepath), True)
        else:
            sys.exit("Unable to save: Could not infer the file key.  Please set one explicitly with the -k option")
    if args.file_key not in _CURRENT_DATABASE.file_keys:
        sys.exit("Unable to save: The requested file key does not exist in this database (%s)" %(args.file_key))
    hasher = sha256()
    chunk = args.filename.read(4096)
    while len(chunk):
        hasher.update(chunk)
        chunk = args.filename.read(4096)
    args.filename.close()
    hashalias = hasher.hexdigest()
    if args.file_key+":"+hashalias in _CURRENT_DATABASE.state_keys and not args.allow_duplicate:
        # print("The state of the current file matches a previously registered state for this file key.  Use the '--allow-duplicate' flag if you would like to create a new state anyways")
        sys.exit("Unable to save: Duplicate of %s (use --allow-duplicate to override this behavior, or '$ quicksave alias' to create aliases)"%(
            _CURRENT_DATABASE.resolve_key(_CURRENT_DATABASE.state_keys[args.file_key+":"+hashalias][0], False).replace(args.file_key+":", '', 1)
        ))
    (key, datafile) = _CURRENT_DATABASE.register_sk(args.file_key, os.path.abspath(args.filename.name))
    _CURRENT_DATABASE.register_fa(args.file_key, '~last', True)
    aliases = []
    if len(args.aliases):
        for user_alias in args.aliases:
            if user_alias in _SPECIAL_STATE:
                sys.exit("Unable to save: Cannot create an alias which overwrites a reserved state key (%s)" % user_alias)
            if _CURRENT_DATABASE.register_sa(args.file_key, key, user_alias, args.force):
                aliases.append(''+user_alias)
        if not len(aliases):
            sys.exit("Unable to save: None of the provided aliases were available")
    if args.file_key+":"+hashalias[:7] in _CURRENT_DATABASE.state_keys:
        del _CURRENT_DATABASE.state_keys[args.file_key+":"+hashalias[:7]]
    elif args.file_key+":"+hashalias not in _CURRENT_DATABASE.state_keys:
        _CURRENT_DATABASE.register_sa(args.file_key, key, hashalias[:7], args.force)
        aliases.append(hashalias[:7])
    _CURRENT_DATABASE.register_sa(args.file_key, key, hashalias)
    _CURRENT_DATABASE.save()
    if infer:
        print("Inferred file key:", args.file_key)
    print("New state key:", key)
    print("Aliases for this key:", aliases)

def command_revert(args):
    initdb()
    infer = not bool(args.file_key)
    did_stash = False
    if infer:
        filepath = os.path.abspath(args.filename.name)
        if filepath in _CURRENT_DATABASE.file_keys:
            args.file_key = _CURRENT_DATABASE.resolve_key(filepath, True)
        elif os.path.basename(filepath) in _CURRENT_DATABASE.file_keys:
            args.file_key = _CURRENT_DATABASE.resolve_key(os.path.basename(filepath), True)
        else:
            sys.exit("Unable to revert: Could not infer the file key.  Please set one explicitly with the -k option")
    if args.file_key not in _CURRENT_DATABASE.file_keys:
        sys.exit("Unable to revert: The requested file key does not exist in this database (%s)" %(args.file_key))
    if args.file_key+":"+args.state not in _CURRENT_DATABASE.state_keys:
        sys.exit("Unable to revert: The requested state (%s) does not exist for this file key (%s)" %(args.state, args.file_key))
    args.file_key = _CURRENT_DATABASE.resolve_key(args.file_key, True)
    _CURRENT_DATABASE.register_fa(args.file_key, '~last', True)
    if args.stash and not args.state == '~stash':
        did_stash = True
        if args.file_key+":~stash" in _CURRENT_DATABASE.state_keys:
            oldfile = _CURRENT_DATABASE.state_keys[args.file_key+":~stash"][2]
            if oldfile in _CURRENT_DATABASE.file_keys[args.file_key][2]:
                _CURRENT_DATABASE.file_keys[args.file_key][2].remove(oldfile)
            del _CURRENT_DATABASE.state_keys[args.file_key+":~stash"]
        hasher = sha256()
        chunk = args.filename.read(4096)
        while len(chunk):
            hasher.update(chunk)
            chunk = args.filename.read(4096)
        hashalias = hasher.hexdigest()
        if args.file_key+":"+hashalias in _CURRENT_DATABASE.state_keys:
            _CURRENT_DATABASE.register_sa(args.file_key, hashalias, '~stash', True)
        else:
            _CURRENT_DATABASE.register_sk(args.file_key, os.path.abspath(args.filename.name), '~stash')
    args.filename.close()
    authoritative_key = _CURRENT_DATABASE.resolve_key(args.file_key+":"+args.state, False)
    statefile = _CURRENT_DATABASE.state_keys[authoritative_key][2]
    copyfile(os.path.join(_CURRENT_DATABASE.file_keys[args.file_key][1], statefile), args.filename.name)
    if infer:
        print("Inferred file key:", args.file_key)
    print("State key reverted to:", authoritative_key.replace(args.file_key+":", '', 1))
    if did_stash:
        print("Old state saved to: ~stash")
    _CURRENT_DATABASE.register_fa(args.file_key, '~last', True)
    _CURRENT_DATABASE.save()

def command_alias(args):
    initdb()
    msg = ""
    if not ((args.d and args.target) or args.filekey): #working with file keys
        if args.d:
            if args.link not in _CURRENT_DATABASE.file_keys:
                sys.exit("Unable to delete alias: The provided file alias does not exist (%s)"%args.link)
            result = _CURRENT_DATABASE.file_keys[args.link]
            if not result[0]:
                sys.exit("Unable to delete alias: The provided alias was a file key (%s).  Use '$ quicksave delete-key <file key>' to delete file keys"%(args.link))
            del _CURRENT_DATABASE.file_keys[args.link]
            _CURRENT_DATABASE.register_fa(result[0], '~last', True)
            msg = "Deleted file alias: %s"%args.link
        elif args.target:
            if args.target not in _CURRENT_DATABASE.file_keys:
                sys.exit("Unable to create alias: The provided target key does not exist (%s)"%args.target)
            if args.link in _CURRENT_DATABASE.file_keys and not _CURRENT_DATABASE.file_keys[args.link][0]:
                sys.exit("Unable to create alias: The provided alias name is already in use by a file key (%s)"%args.link)
            if args.link in _SPECIAL_FILE:
                sys.exit("Unable to create alias: The requested alias overwrites a reserved file key (%s)"%args.link)
            authoritative_key = _CURRENT_DATABASE.resolve_key(args.target, True)
            _CURRENT_DATABASE.register_fa(authoritative_key, args.link, True)
            _CURRENT_DATABASE.register_fa(authoritative_key, '~last', True)
            msg = "Registered file alias: %s --> %s"%(args.link, authoritative_key)
    else:
        if args.d:
            if not args.target:
                sys.exit("Unable to delete alias: A file key must be provided as the second argument")
            if args.target not in _CURRENT_DATABASE.file_keys:
                sys.exit("Unable to delete alias: The provided file key does not exist (%s)"%args.target)
            if args.filekey:
                sys.exit("Unable to delete alias: Unexpected argument: %s"%args.filekey)
            filekey = _CURRENT_DATABASE.resolve_key(args.target, True)
            if filekey+":"+args.link not in _CURRENT_DATABASE.state_keys:
                sys.exit("Unable to delete alias: The provided state alias does not exist (%s)"%args.link)
            result = _CURRENT_DATABASE.state_keys[filekey+":"+args.link]
            if not result[0]:
                sys.exit("Unable to delete alias: The provided alias was a state key (%s).  Use '$ quicksave delete-key <file key> <state key>' to delete state keys"%(args.link))
            del _CURRENT_DATABASE.state_keys[filekey+":"+args.link]
            msg = "Deleted state alias: %s from file key %s"%(args.link, filekey)
            _CURRENT_DATABASE.register_fa(filekey, '~last', True)
        else:
            if not args.filekey:
                sys.exit("Unable to create state alias: A file key or alias was not provided")
            elif args.filekey not in _CURRENT_DATABASE.file_keys:
                sys.exit("Unable to create alias: The provided file key does not exist (%s)"%args.filekey)
            filekey = _CURRENT_DATABASE.resolve_key(args.filekey, True)
            if filekey+":"+args.target not in _CURRENT_DATABASE.state_keys:
                sys.exit("Unable to create alias: The provided state key does not exist (%s)"%args.target)
            if args.link in _SPECIAL_STATE:
                sys.exit("Unable to create alias: The requested alias overwrites a reserved state key (%s)"%args.link)
            statekey = _CURRENT_DATABASE.resolve_key(filekey+":"+args.target, False)
            if filekey+":"+args.link in _CURRENT_DATABASE.state_keys and not _CURRENT_DATABASE.state_keys[filekey+":"+args.link][0]:
                sys.exit("Unable to create alias: The provided alias name is already in use by a state key (%s)"%args.link)
            _CURRENT_DATABASE.register_sa(filekey, statekey.replace(filekey+":", '', 1), args.link, True)
            _CURRENT_DATABASE.register_fa(filekey, '~last', True)
            msg = "Registered state alias: %s --> %s under file key: %s"%(args.link, statekey.replace(filekey+":", '', 1), filekey)
    print(msg)
    _CURRENT_DATABASE.save()



def command_list(args):
    initdb()
    if not args.filekey:
        print("Showing all file keys", "and aliases" if args.aliases else '')
        print()
        for key in _CURRENT_DATABASE.file_keys:
            isfile = _CURRENT_DATABASE.file_keys[key][0]
            if not isfile:
                print('File Key: ' if args.aliases else '', key, sep='')
            elif args.aliases:
                print("File Alias:", key, "(Alias of: %s)"%isfile)
    else:
        if args.filekey not in _CURRENT_DATABASE.file_keys:
            sys.exit("Unable to list: The requested file key does not exist in this database (%s)" %(args.filekey))
        print("Showing all state keys", " and aliases" if args.aliases else '', " for file key ", args.filekey, sep='')
        print()
        args.filekey = _CURRENT_DATABASE.resolve_key(args.filekey, True)
        for key in _CURRENT_DATABASE.state_keys:
            if _CURRENT_DATABASE.state_keys[key][1] == args.filekey:
                isfile = _CURRENT_DATABASE.state_keys[key][0]
                display_key = key.replace(args.filekey+":", '', 1)
                if not isfile:
                    print("State Key: " if args.aliases else '', display_key, sep='')
                elif args.aliases:
                    print("State Alias:", display_key, "(Alias of: %s)"%isfile.replace(args.filekey+":", '', 1))

def command_delete(args):
    initdb()
    if not args.filekey:
        #when deleting a file key:
        #   - Remove the data folder for the current ~trash entry
        #   - Remove any file aliases to ~trash
        #   - Remove all state keys and aliases under ~trash
        #   - Unregister all file aliases
        #   - Update all state keys and aliases to point to ~trash:<key>
        if args.target not in _CURRENT_DATABASE.file_keys:
            sys.exit("Unable to delete key: The provided file key does not exist in this database (%s)"%args.target)
        if _CURRENT_DATABASE.file_keys[args.target][0]:
            sys.exit("Unable to delete key: The provided file key was an alias.  Use '$ quicksave alias -d <file alias>' to delete")
        if args.target == '~trash':
            sys.exit("Unable to directly delete ~trash keys.  Use '$ quicksave clean -t' to clean all ~trash keys")
        if args.save and '~trash' in _CURRENT_DATABASE.file_keys:
            rmtree(os.path.join(
                os.path.abspath(_CURRENT_DATABASE.base_dir),
                _CURRENT_DATABASE.file_keys['~trash'][1]
            ))
            if args.clean_aliases:
                for key in [key for key in _CURRENT_DATABASE.file_keys if _CURRENT_DATABASE.file_keys[key][0]=='~trash']:
                    del _CURRENT_DATABASE.file_keys[key]
            for key in [key for key in _CURRENT_DATABASE.state_keys if key.startswith('~trash')]:
                del _CURRENT_DATABASE.state_keys[key]
            del _CURRENT_DATABASE.file_keys['~trash']
        for key in [key for key in _CURRENT_DATABASE.file_keys if _CURRENT_DATABASE.file_keys[key][0]==args.target]:
            del _CURRENT_DATABASE.file_keys[key]
        for key in [key for key in _CURRENT_DATABASE.state_keys if key.startswith(args.target+":")]:
            if args.save:
                entry = [item for item in _CURRENT_DATABASE.state_keys[key]]
                entry[1] = entry[1].replace(args.target, '~trash', 1)
                if entry[0]:
                    entry[0] = entry[0].replace(args.target, '~trash', 1)
                _CURRENT_DATABASE.state_keys[key.replace(args.target, '~trash', 1)] = [item for item in entry]
            del _CURRENT_DATABASE.state_keys[key]
        if args.save:
            _CURRENT_DATABASE.file_keys['~trash'] = [item for item in _CURRENT_DATABASE.file_keys[args.target]]
        else:
            rmtree(os.path.join(
                os.path.abspath(_CURRENT_DATABASE.base_dir),
                _CURRENT_DATABASE.file_keys[args.target][1]
            ))
        del _CURRENT_DATABASE.file_keys[args.target]
        _CURRENT_DATABASE.save()
        print("Deleted file key: %s"%args.target)
        if args.save:
            print("File data saved to ~trash")

    else:
        #when deleting a state key:
        #   - Remove the datafile (and entry in the parent file key) for the current ~trash entry
        #   - Remove any state aliases to ~trash (-c)
        #   - Unregister all state aliases
        if args.filekey not in _CURRENT_DATABASE.file_keys:
            sys.exit("Unable to delete key: The provided file key does not exist in this database (%s)"%args.filekey)
        authoritative_key = _CURRENT_DATABASE.resolve_key(args.filekey, True)
        if authoritative_key+":"+args.target not in _CURRENT_DATABASE.state_keys:
            sys.exit("Unable to delete key: The provided state key does not exist in this database (%s)"%args.target)
        if _CURRENT_DATABASE.state_keys[authoritative_key+":"+args.target][0]:
            sys.exit("Unable to delete key: The provided state key was an alias.  Use '$ quicksave alias -d <state alias> <file key>' to delete a state alias")
        if args.target == '~trash':
            sys.exit("Unable to directly delete ~trash keys.  Use '$ quicksave clean -t' to clean all ~trash keys")
        if args.save and authoritative_key+":~trash" in _CURRENT_DATABASE.state_keys:
            os.remove(os.path.join(
                os.path.abspath(_CURRENT_DATABASE.base_dir),
                _CURRENT_DATABASE.file_keys[authoritative_key][1],
                _CURRENT_DATABASE.state_keys[authoritative_key+":~trash"][2]
            ))
            _CURRENT_DATABASE.file_keys[authoritative_key][2].remove(
                _CURRENT_DATABASE.state_keys[authoritative_key+":~trash"][2]
            )
            if args.clean_aliases:
                for key in [key for key in _CURRENT_DATABASE.state_keys if _CURRENT_DATABASE.state_keys[key][0]==authoritative_key+":~trash"]:
                    del _CURRENT_DATABASE.state_keys[key]
            del _CURRENT_DATABASE.state_keys[authoritative_key+":~trash"]
        for key in [key for key in _CURRENT_DATABASE.state_keys if _CURRENT_DATABASE.state_keys[key][0]==authoritative_key+":"+args.target]:
            del _CURRENT_DATABASE.state_keys[key]
        if args.save:
            _CURRENT_DATABASE.state_keys[authoritative_key+":~trash"] = [item for item in _CURRENT_DATABASE.state_keys[authoritative_key+":"+args.target]]
        else:
            os.remove(os.path.join(
                os.path.abspath(_CURRENT_DATABASE.base_dir),
                _CURRENT_DATABASE.file_keys[authoritative_key][1],
                _CURRENT_DATABASE.state_keys[authoritative_key+":"+args.target][2]
            ))
            _CURRENT_DATABASE.file_keys[authoritative_key][2].remove(
                _CURRENT_DATABASE.state_keys[authoritative_key+":"+args.target][2]
            )
        del _CURRENT_DATABASE.state_keys[authoritative_key+":"+args.target]
        _CURRENT_DATABASE.register_fa(authoritative_key, '~last', True)
        _CURRENT_DATABASE.save()
        print("Deleted state key: %s (File key: %s)"%(args.target, authoritative_key))
        if args.save:
            print("State data saved to ~trash")


def command_lookup(args):
    initdb()
    if not (args.filekey or args.target in _CURRENT_DATABASE.file_keys):
        sys.exit("Unable to lookup: The requested file key does not exist in this database (%s)" %(
            args.filekey if args.filekey else args.target
        ))
    if args.filekey:
        if args.filekey not in _CURRENT_DATABASE.file_keys:
            sys.exit("Unable to lookup: The requested file key does not exist in this database (%s)"%args.filekey)
        args.filekey = _CURRENT_DATABASE.resolve_key(args.filekey, True)
    if args.filekey and args.filekey+":"+args.target not in _CURRENT_DATABASE.state_keys:
        sys.exit("Unable to lookup: The requested state (%s) does not exist for this file key (%s)" %(args.target, args.filekey))
    keyheader = args.filekey+":" if args.filekey else ''
    result = _CURRENT_DATABASE.resolve_key(keyheader+args.target, not args.filekey)
    if keyheader:
        result = result.replace(args.filekey+":", '', 1)
    print(args.target, '-->', result)


def command_recover(args):
    try:
        from .qs_database import make_key
    except SystemError:
        from qs_database import make_key
    initdb()
    if '~trash' not in _CURRENT_DATABASE.file_keys:
        sys.exit("Unable to recover: There is no data stored in the ~trash file key")
    entry = [item for item in _CURRENT_DATABASE.file_keys['~trash']]
    filekey = make_key(os.path.basename(entry[1])[:5]+"_FK", _CURRENT_DATABASE.file_keys)
    _CURRENT_DATABASE.file_keys[filekey] = [item for item in entry]
    aliases = []
    for key in [key for key in _CURRENT_DATABASE.file_keys if _CURRENT_DATABASE.file_keys[key][0]=='~trash']:
        _CURRENT_DATABASE.file_keys[key][1] = filekey
        aliases.append(key)
    if len(args.aliases):
        for user_alias in args.aliases:
            if user_alias in _SPECIAL_FILE:
                sys.exit("Unable to recover: Cannot create a file alias which overwrites a reserved file key (%s)"%user_alias)
            if _CURRENT_DATABASE.register_fa(filekey, user_alias):
                aliases.append(''+user_alias)
        if not len(aliases):
            sys.exit("Unable to recover: None of the provided aliases were available")
    for key in [key for key in _CURRENT_DATABASE.state_keys if key.startswith("~trash:")]:
        entry = [item for item in _CURRENT_DATABASE.state_keys[key]]
        entry[1] = entry[1].replace('~trash', filekey, 1)
        if entry[0]:
            entry[0] = entry[0].replace('~trash', filekey, 1)
        _CURRENT_DATABASE.state_keys[key.replace('~trash', filekey, 1)] = [item for item in entry]
        del _CURRENT_DATABASE.state_keys[key]
    del _CURRENT_DATABASE.file_keys['~trash']
    _CURRENT_DATABASE.register_fa(filekey, '~last', True)
    _CURRENT_DATABASE.save()
    print("Recovered file key:", filekey)
    print("Aliases for this file key:", aliases)

def command_clean(args):
    initdb()
    didop = False
    msg = ''
    if args.trash:
        didop = True
        for key in [key for key in _CURRENT_DATABASE.file_keys if _CURRENT_DATABASE.file_keys[key][0] == '~trash']:
            del _CURRENT_DATABASE.file_keys[key]
        for key in [key for key in _CURRENT_DATABASE.state_keys]:
            if key.startswith("~trash:"): #this state key belongs to the trash file key
                del _CURRENT_DATABASE.state_keys[key]
            elif key.endswith(":~trash"): #this is a trash state key, but it belongs to a regular key
                datafile = _CURRENT_DATABASE.state_keys[key][2]
                _CURRENT_DATABASE.file_keys[_CURRENT_DATABASE.state_keys[key][1]][2].remove(datafile)
                os.remove(os.path.join(
                    os.path.abspath(_CURRENT_DATABASE.base_dir),
                    _CURRENT_DATABASE.file_keys[_CURRENT_DATABASE.state_keys[key][1]][1],
                    datafile
                ))
                del _CURRENT_DATABASE.state_keys[key]
            else:
                entry = [item for item in _CURRENT_DATABASE.state_keys[key]]
                if entry[0] and entry[0].count('~trash'):
                    del _CURRENT_DATABASE.state_keys[key]
        msg+="Cleaned all ~trash state keys, and their aliases.\n"
        if '~trash' in _CURRENT_DATABASE.file_keys:
            rmtree(os.path.join(
                os.path.abspath(_CURRENT_DATABASE.base_dir),
                _CURRENT_DATABASE.file_keys['~trash'][1]
            ))
            del _CURRENT_DATABASE.file_keys['~trash']
            msg+="Cleaned the ~trash file key and its aliases.\n"
    if args.deduplicate:
        didop = True
        duplicates = {} #file key -> hash -> original state key
        forward = {} #duplicate state key -> original state key
        for key in sorted([key for key in _CURRENT_DATABASE.state_keys if not _CURRENT_DATABASE.state_keys[key][0]]):
            entry = [item for item in _CURRENT_DATABASE.state_keys[key]]
            reader = open(os.path.join(
                os.path.abspath(_CURRENT_DATABASE.base_dir),
                _CURRENT_DATABASE.file_keys[entry[1]][1],
                entry[2]
            ), mode='rb')
            hasher = sha256()
            chunk = reader.read(4096)
            while len(chunk):
                hasher.update(chunk)
                chunk = reader.read(4096)
            hashsum = hasher.hexdigest()
            reader.close()
            if entry[1] not in duplicates:
                duplicates[entry[1]] = {}
            if hashsum not in duplicates[entry[1]]:
                duplicates[entry[1]][hashsum] = ''+key
            else:
                forward[''+key] = duplicates[entry[1]][hashsum]
                entry = [item for item in _CURRENT_DATABASE.state_keys[key]]
                try:
                    os.remove(os.path.join(
                        os.path.abspath(_CURRENT_DATABASE.base_dir),
                        _CURRENT_DATABASE.file_keys[entry[1]][1],
                        entry[2]
                    ))
                except FileNotFoundError:
                    pass
                _CURRENT_DATABASE.file_keys[entry[1]][2].remove(entry[2])
                del _CURRENT_DATABASE.state_keys[key]
        didforward = 0
        for key in [key for key in _CURRENT_DATABASE.state_keys if _CURRENT_DATABASE.state_keys[key][0]]:
            if _CURRENT_DATABASE.state_keys[key][0] in forward: #this is a state alias which should be forwarded
                _CURRENT_DATABASE.state_keys[key][0] = forward[_CURRENT_DATABASE.state_keys[key][0]]
                didforward += 1
        for filekey in duplicates:
            for hashkey in duplicates[filekey]:
                if filekey+":"+hashkey not in _CURRENT_DATABASE.state_keys:
                    _CURRENT_DATABASE.register_sa(filekey, duplicates[filekey][hashkey].replace(filekey+":", '', 1), hashkey)
                if filekey+":"+hashkey[:7] not in _CURRENT_DATABASE.state_keys:
                    _CURRENT_DATABASE.register_sa(filekey, duplicates[filekey][hashkey].replace(filekey+":", '', 1), hashkey[:7])
        msg+="Removed the following duplicate state keys: "+str([key for key in forward])+\
        " and forwarded "+str(didforward)+" aliases\n"
    if not didop:
        sys.exit("No operations were enabled for clean.  Set at least one of the flags when using '$ quicksave clean'")
    _CURRENT_DATABASE.save()
    print(msg[:-1])

def command_help(args, helper):
    if not args.subcommand:
        helper['__main__']()
        print("\nUse '$ quicksave help <subcommand>' for help with a specific subcommand")
    elif args.subcommand =='__main__' or args.subcommand not in helper:
        sys.exit("Unknown subcommand name: %s"%args.subcommand)
    else:
        helper[args.subcommand]()

def main(args_input=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        "quicksave",
        description="A very simple file versioning system.  Useful for quickly "+
        " maintaining a few versions of a file without setting up a full version control repository",
    )
    subparsers = parser.add_subparsers()
    helper = {'__main__':parser.print_help}

    init_parser = subparsers.add_parser(
        'init', aliases=['load-db'],
        description="Initializes the quicksave database at the specified path.\n"+
        "If the path does not exist, then create an empty database.\n"+
        "If the path does exist, attempt to load an existing database"
    )
    init_parser.set_defaults(func=command_init)
    helper['init'] = init_parser.print_help
    helper['load-db'] = init_parser.print_help
    init_parser.add_argument(
        'database_path',
        type=check_is_directory,
        help="The database path to initialize.  If it exists, then load the database.  If not, then create a new one"
    )

    register_parser = subparsers.add_parser(
        'register',
        description="Registers a new file for versioning.  Different versions of a single\n"+
        "file are grouped together by a few file keys which distinguish the set from other files.\n"+
        "A new unique file key will be automatically generated, but this key can also be aliased by\n"+
        "the original absolute filepath of the file, the original filename, and any user provided aliases.\n"+
        "Note that the following file keys are reserved for special use: "+str(_SPECIAL_FILE)+".\n"+
        "Returns the file key and list of aliases for the new set of versions, and the initial state key for the starting version"
    )
    register_parser.set_defaults(func=command_register)
    helper['register'] = register_parser.print_help
    register_parser.add_argument(
        'filename',
        type=argparse.FileType('rb'),
        help="The file to save.  The filename and path will be used as aliases for the new file key\n"+
        "if they are not already aliases for a different file key"
    )
    register_parser.add_argument(
        'aliases',
        nargs='*',
        help="A list of user-defined aliases for the automatically generated state key.  Quotes must be used to surround any aliases containing spaces.\n"+
        "Aliases must be unique within the database.  Non-unique aliases are ignored, but if any aliases are provided,\n"+
        "at least one must be unique or the operation will be canceled.",
        default = []
    )
    register_parser.add_argument(
        '--ignore-filepath',
        action='store_true',
        help="Normally, register will halt if the file being registered matches the filepath of an existing file key.\n"+
        "If --ignore-filepath is set, it will allow the file to be registered anyways"
    )
    register_parser.add_argument(
        '-a', '--file-alias',
        action='append',
        help="Set an alias for the automatically generated file key.  This option may be provided multiple times to define multiple aliases.\n"+
        "Aliases must be unique within the database.  Non-unique aliases are ignored, but if any aliases are provided,\n"+
        "at least one must be unique or the operation will be canceled.",
        default=[]
    )

    save_parser = subparsers.add_parser(
        'save',
        description="Saves the current state of the file to the set of versions for this file.\n"+
        "Quicksave will attempt to infer the file key if one is not provided explicitly.\n"+
        "A new unique state key will be automatically generated, but this key can also be aliased by\n"+
        "the sha-256 hash of the file contents (and just the first 7 characters iff that is unique under this file key)\n"+
        "and any user defined aliases. The following state keys are reserved for special use: "+str(_SPECIAL_STATE)+".\n"+
        "Returns the file key (iff it was inferred), the new state key, and a list of aliases"
    )
    save_parser.set_defaults(func=command_save)
    helper['save'] = save_parser.print_help
    save_parser.add_argument(
        'filename',
        type=argparse.FileType('rb'),
        help="The file to save.  Iff the filename differs from the original filename for the file key,\n"+
        "it will be added as an alias to the new state key."
    )
    save_parser.add_argument(
        '-k', '--file-key',
        help="The file key linked to the set of states to save this file in.\n"+
        "If the file key is not specified it will be inferred by the full filepath or the filename (in that order).\n"+
        "If neither the filepath nor the filename match any file key aliases in this database,\n"+
        "quicksave will require the user to provide this option.",
        default=None
    )
    save_parser.add_argument(
        'aliases',
        nargs='*',
        help="A list of user-defined aliases for the current state.  Quotes must be used to surround any aliases containing spaces.\n"+
        "Aliases must be unique under this file key.  Non-unique aliases are ignored, but if any aliases are provided,\n"+
        "at least one must be unique or the operation will be canceled."
    )
    save_parser.add_argument(
        '-f', '--force',
        action='store_true',
        help="Overwrite any existing state aliases.  The automatically generated state key will always be unique\n"+
        "but the 7 character sha-256 prefix and any user aliases will overwrite existing state aliaes."
    )
    save_parser.add_argument(
        '--allow-duplicate',
        action='store_true',
        help='Save the state even if an identical state exists.'
    )

    revert_parser = subparsers.add_parser(
        'revert',
        description="Reverts the specified file to the state specified by the provided state key or alias.\n"+
        "Quicksave will attempt to infer the file key if one is not provided explicitly.\n"+
        "Returns the file key iff it was inferred and the authoritative state key reverted to"
    )
    revert_parser.set_defaults(func=command_revert)
    helper['revert'] = revert_parser.print_help
    revert_parser.add_argument(
        'filename',
        type=argparse.FileType('rb'),#read_write_file_exists,
        help="The file to revert"
    )
    revert_parser.add_argument(
        '-k', '--file-key',
        help="The file key which contains the state being reverted to.\n"+
        "If the file key is not specified it will be inferred by the full filepath or the filename (in that order).\n"+
        "If neither the filepath nor the filename match any file key aliases in this database,\n"+
        "quicksave will require the user to provide this option.",
        default=None
    )
    revert_parser.add_argument(
        'state',
        help="The state key or alias to revert to."
    )
    revert_parser.add_argument(
        '--no-stash',
        action='store_false',
        help="Do not save the state under the ~stash state key before reverting.\n"+
        "This is the default if reverting to ~stash, but stashing is enabled in all other cases.\n"
        "If the file's full sha-256 hash is currently registered as a state alias,\n"+
        "then ~stash will simply alias this file's true state key.\n"+
        "Otherwise, the full state will be saved under ~stash.\n"
        "The ~stash state key should not be used for permanent storage as it may be frequently overwritten.\n"+
        "To save the current ~stash state permanently, use \n"+
        "'$ quicksave revert <filename> ~stash' then\n"+
        "'$ quicksave save <filename>'",
        dest='stash'
    )

    alias_parser = subparsers.add_parser(
        'alias',
        description="Create, override, or delete an alias for a file or state key.\n"+
        "The action taken by this command depends on the specific command syntax:\n"+
        "'$ quicksave <link> <target>' creates or overwrites the file key alias <link> to point to the file key (or alias) <target>.\n"+
        "'$ quicksave -d <link>' deletes the file key alias <link>.  Cannot delete file keys (only aliases).\n"+
        "'$ quicksave <link> <target> <filekey>' creates or overwrites the state key alias <link> to point to the state key (or alias) <target> under the file key <file>.\n"+
        "'$ quicksave -d <link> <filekey>' delets the state key alias <link> under the file key <filekey>.  Cannot delete state keys (only aliases).\n"+
        "To delete authoritative file or state keys, use '$ quicksave delete-key <file key> [state key]'"
    )
    alias_parser.set_defaults(func=command_alias)
    helper['alias'] = alias_parser.print_help
    alias_parser.add_argument(
        "link",
        help="The alias to create, overwrite, or delete."
    )
    alias_parser.add_argument(
        'target',
        nargs='?',
        help="The target alias or key that <link> should point to",
        default=None
    )
    alias_parser.add_argument(
        'filekey',
        nargs='?',
        help="The file key (or alias) containing the desired state key (or alias) <target>",
        default=None
    )
    alias_parser.add_argument(
        '-d',
        action='store_true',
        help='Deletes the provided file or state alias'
    )

    list_parser = subparsers.add_parser(
        'list',
        description="Lists all file keys in this database, or all state keys under a provided file key (or alias)"
    )
    list_parser.set_defaults(func=command_list)
    helper['list'] = list_parser.print_help
    list_parser.add_argument(
        'filekey',
        nargs='?',
        help="If provided, list all state keys under this file key or alias",
        default=None
    )
    list_parser.add_argument(
        '-a', '--aliases',
        action='store_true',
        help='Display key aliases in addition to just keys'
    )

    delete_parser = subparsers.add_parser(
        'delete-key',
        description="Deletes a file or state key, and all its aliases"
    )
    delete_parser.set_defaults(func=command_delete)
    helper['delete-key'] = delete_parser.print_help
    delete_parser.add_argument(
        'filekey',
        nargs='?',
        help="If provided, delete the state key <target> from within this file key (or alias)",
        default=None
    )
    delete_parser.add_argument(
        'target',
        help="The target file or state key to delete.\n"+
        "Iff <filekey> is provided, then <target> is taken to be a state key, otherwise it is taken to be a file key.\n"+
        "This *MUST* be an authoritative key, and not an alias.  Aliases can be deleted using the 'alias' command"
    )
    delete_parser.add_argument(
        '--no-save',
        action='store_false',
        help="By default, the most recently deleted file or state key is saved under the ~trash key\n"+
        "(which is a reserved file key as well as a reserved state key under all file keys).\n"+
        "Using the --no-save option disables this behavior, however the deleted key will be immediately and irrecoverably lost.\n"+
        "~trash should not be used for permanent storage as it may be overwritten frequently.\n"+
        "To recover the ~trash *FILE* key, use '$ quicksave recover'.\n"+
        "To recover the ~trash *STATE* key, use\n"+
        "'$ quicksave revert <filename> ~trash' then\n"+
        "'$ quicksave save <filename>'.  Note that old aliases of the deleted state key will not be recovered, and must be set manually",
        dest='save'
    )
    delete_parser.add_argument(
        '-c', '--clean-aliases',
        action='store_true',
        help="If saving a deleted key to ~trash (ie: this option only applies if "+
        "the --no-save option is NOT provided) remove all file aliases that have "+
        "been made to point to ~trash"
    )

    lookup_parser = subparsers.add_parser(
        'lookup',
        description="Returns the authoritative file or state key for a given alias"
    )
    lookup_parser.set_defaults(func=command_lookup)
    helper['lookup'] = lookup_parser.print_help
    lookup_parser.add_argument(
        'filekey',
        nargs='?',
        help="If provided, lookup the state alias <target> from within this file key (or alias)",
        default=None
    )
    lookup_parser.add_argument(
        'target',
        help="The target file or state alias to lookup.\n"+
        "Iff <filekey> is provided, then <target> is taken to be a state alias, otherwise it is taken to be a file alias."
    )

    recover_parser = subparsers.add_parser(
        'recover',
        description="Recovers the most recently deleted file key.\n"+
        "The recovered data will be saved under a uniquely generated key, but a list of aliases may also be provided.\n"+
        "Old aliases of the deleted key are not recovered, and must be set manually.\n"+
        "Aliases applied to the ~trash key *WILL* be migrated over to the recovered key.\n"
        "Returns the new file key and list of aliases for the key"
    )
    recover_parser.set_defaults(func=command_recover)
    helper['recover'] = recover_parser.print_help
    recover_parser.add_argument(
        'aliases',
        nargs="*",
        help="A list of user-defined aliases for the recovered key.  Quotes must be used to surround any aliases containing spaces.\n"+
        "Aliases must be unique within the database.  Non-unique aliases are ignored, but if any aliases are provided,\n"+
        "at least one must be unique or the operation will be canceled.",
        default = []
    )

    show_parser = subparsers.add_parser(
        'show',
        description="Shows the current database path"
    )
    show_parser.set_defaults(func = lambda _:print(initdb()))
    helper['show'] = show_parser.print_help

    clean_parser = subparsers.add_parser(
        'clean',
        description="Cleans the database to reduce used space.\n"+
        "If no flags are set, this is a no-op. Each flag enables a different stage of cleaning"
    )
    clean_parser.set_defaults(func=command_clean)
    helper['clean'] = clean_parser.print_help
    clean_parser.add_argument(
        '-t', '--trash',
        action='store_true',
        help="Cleans the ~trash file key, and the ~trash state keys for all file keys.\n"+
        "When a file or state key is deleted, the ~trash key points to that data, and the previous key is freed.\n"+
        "The ~trash key is deleted by deleting a new key (overwriting ~trash), or manually using delete-key or clean"
    )
    clean_parser.add_argument(
        '-d', '--deduplicate',
        action='store_true',
        help="Scans the database for state keys which store identical states of "+
        "a file under the same file key. Removes all but one state key from each "+
        "set of duplicates, and updates all aliases of the deleted keys to point "+
        "to the remaining state key."
    )

    help_parser = subparsers.add_parser(
        'help',
        description="Displays help about quicksave and its subcommands"
    )
    help_parser.set_defaults(func=lambda args:command_help(args, helper))
    helper['help'] = help_parser.print_help
    help_parser.add_argument(
        'subcommand',
        nargs='?',
        help="The subcommand whose help message should be displayed",
        default = None
    )

    args = parser.parse_args(args_input)
    if 'func' not in dir(args):
        parser.print_help()
        sys.exit(2)
    args.func(args)


if __name__ == '__main__':
    # print("No previous database registered in config file.  Please run '$ quicksave init'")
    main()
