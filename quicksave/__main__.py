import argparse
import os
import sys
from shutil import copyfile
from hashlib import sha256

try:
    from .qs_database import Database as db
except SystemError:
    sys.path.append(os.path.dirname(__file__))
    from qs_database import Database as db

_SPECIAL_file = ['~trash', '~last']
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
    if key in _SPECIAL_file:
        sys.exit("Unable to register: The provided filename overwrites a reserved file key (%s)"%key)
    file_aliases = []
    if len(args.file_alias):
        for user_alias in args.file_alias:
            if user_alias in _SPECIAL_file:
                sys.exit("Unable to register: Cannot create a file alias which overwrites a reserved file key (%s)"%user_alias)
            if _CURRENT_DATABASE.register_fa(key, user_alias):
                file_aliases.append(''+user_alias)
        if not len(file_aliases):
            sys.exit("Unable to register: None of the provided aliases were available")
    if filepath not in _SPECIAL_file and _CURRENT_DATABASE.register_fa(key, filepath):
        file_aliases.append(filepath)
    if os.path.basename(filepath) not in _SPECIAL_file and _CURRENT_DATABASE.register_fa(key, os.path.basename(filepath)):
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
    (key, datafile) = _CURRENT_DATABASE.register_sk(args.file_key, os.path.abspath(args.filename.name))
    aliases = []
    if len(args.aliases):
        for user_alias in args.aliases:
            if user_alias in _SPECIAL_STATE:
                sys.exit("Unable to save: Cannot create an alias which overwrites a reserved state key (%s)" % user_alias)
            if _CURRENT_DATABASE.register_sa(args.file_key, key, user_alias, args.force):
                aliases.append(''+user_alias)
        if not len(aliases):
            sys.exit("Unable to save: None of the provided aliases were available")
    hasher = sha256()
    chunk = args.filename.read(4096)
    while len(chunk):
        hasher.update(chunk)
        chunk = args.filename.read(4096)
    args.filename.close()
    hashalias = hasher.hexdigest()
    if args.file_key+":"+hashalias[:7] in _CURRENT_DATABASE.state_keys:
        del _CURRENT_DATABASE.state_keys[args.file_key+":"+hashalias[:7]]
    elif args.file_key+":"+hashalias not in _CURRENT_DATABASE.state_keys:
        _CURRENT_DATABASE.register_sa(args.file_key, key, hashalias[:7], args.force)
        aliases.append(hashalias[:7])
    if args.file_key+":"+hashalias in _CURRENT_DATABASE.state_keys and not args.allow_duplicate:
        # print("The state of the current file matches a previously registered state for this file key.  Use the '--allow-duplicate' flag if you would like to create a new state anyways")
        sys.exit("Unable to save: Duplicate of %s (use --allow-duplicate to override this behavior, or '$ quicksave alias' to create aliases)"%(
            _CURRENT_DATABASE.resolve_key(_CURRENT_DATABASE.state_keys[args.file_key+":"+hashalias][0], False).replace(args.file_key+":", '', 1)
        ))
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
    args.file_key = _CURRENT_DATABASE.resolve_key(args.file_key, True)
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
    if args.file_key+":"+args.state not in _CURRENT_DATABASE.state_keys:
        sys.exit("Unable to revert: The requested state (%s) does not exist for this file key (%s)" %(args.state, args.file_key))
    args.filename.close()
    authoritative_key = _CURRENT_DATABASE.resolve_key(args.file_key+":"+args.state, False)
    statefile = _CURRENT_DATABASE.state_keys[authoritative_key][2]
    copyfile(os.path.join(_CURRENT_DATABASE.file_keys[args.file_key][1], statefile), args.filename.name)
    if infer:
        print("Inferred file key:", args.file_key)
    print("State key reverted to:", authoritative_key.replace(args.file_key+":", '', 1))
    if did_stash:
        _CURRENT_DATABASE.save()
        print("Old state saved to: ~stash")

def command_alias(args):
    sys.exit("This command is not yet ready")

def command_list(args):
    initdb()
    if not args.filekey:
        print("Showing all file keys", "and aliases" if args.aliases else '')
        print()
        for key in _CURRENT_DATABASE.file_keys:
            isfile = _CURRENT_DATABASE.file_keys[key][0]
            if not isfile:
                print('file Key: ' if args.aliases else '', key, sep='')
            elif args.aliases:
                print("file Alias:", key, "(Alias of: %s)"%isfile)
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
    sys.exit("This command is not yet ready")

def command_lookup(args):
    initdb()
    if not (args.filekey or args.target in _CURRENT_DATABASE.file_keys):
        sys.exit("Unable to lookup: The requested file key does not exist in this database (%s)" %(args.filekey))
    if args.filekey:
        args.filekey = _CURRENT_DATABASE.resolve_key(args.filekey, True)
    if args.filekey and args.filekey+":"+args.target not in _CURRENT_DATABASE.state_keys:
        sys.exit("Unable to lookup: The requested state (%s) does not exist for this file key (%s)" %(args.target, args.filekey))
    keyheader = args.filekey+":" if args.filekey else ''
    result = _CURRENT_DATABASE.resolve_key(keyheader+args.target, not args.filekey)
    if keyheader:
        result = result.replace(args.filekey+":", '', 1)
    print(args.target, '-->', result)


def command_recover(args):
    sys.exit("This command is not yet ready")


def main(args_input=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        "quicksave",
        description="A very simple file versioning system.  Useful for quickly "+
        " maintaining a few versions of a file without setting up a full version control repository",
    )
    subparsers = parser.add_subparsers()

    init_parser = subparsers.add_parser(
        'init', aliases=['load-db'],
        description="Initializes the quicksave database at the specified path.\n"+
        "If the path does not exist, then create an empty database.\n"+
        "If the path does exist, attempt to load an existing database"
    )
    init_parser.set_defaults(func=command_init)
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
        "Note that the following file keys are reserved for special use: "+str(_SPECIAL_file)+".\n"+
        "Returns the file key and list of aliases for the new set of versions, and the initial state key for the starting version"
    )
    register_parser.set_defaults(func=command_register)
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
        "at least one must be unique or the operation will be canceled."
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
        help="By default, deleted file or state keys are saved under the ~trash key\n"+
        "(which is a reserved file key and a reserved state key under all file keys).\n"+
        "~trash should not be used for permanent storage as it may be overwritten frequently.\n"+
        "To recover the ~trash *file* key, use '$ quicksave recover [aliases...]'.\n"+
        "To recover the ~trash *STATE* key, use\n"+
        "'$ quicksave revert <filename> ~trash' then\n"+
        "'$ quicksave save <filename>'.  Note that old aliases of the deleted state key will not be recovered, and must be set manually",
        dest='save'
    )

    lookup_parser = subparsers.add_parser(
        'lookup',
        description="Returns the authoritative file or state key for a given alias"
    )
    lookup_parser.set_defaults(func=command_lookup)
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
        "Returns the new file key and list of aliases, if provided"
    )
    recover_parser.set_defaults(func=command_recover)
    recover_parser.add_argument(
        'aliases',
        nargs="+",
        help="A list of user-defined aliases for the recovered key.  Quotes must be used to surround any aliases containing spaces.\n"+
        "Aliases must be unique within the database.  Non-unique aliases are ignored, but if any aliases are provided,\n"+
        "at least one must be unique or the operation will be canceled."
    )

    show_parser = subparsers.add_parser(
        'show',
        description="Shows the current database path"
    )
    show_parser.set_defaults(func = lambda _:print(initdb()))

    args = parser.parse_args(args_input)
    print()
    if 'func' not in dir(args):
        parser.print_help()
        sys.exit(2)
    args.func(args)


if __name__ == '__main__':
    # print("No previous database registered in config file.  Please run '$ quicksave init'")
    main()
