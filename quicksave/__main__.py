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

_SPECIAL_PRIMARY = ['~trash']
_SPECIAL_STATE = ['~stash', '~trash']
_CURRENT_DATABASE = None
configfile = os.path.join(os.path.expanduser('~'), '.quicksave_config')

def check_is_directory(argument):
    fullpath = os.path.abspath(argument)
    if os.path.isfile(fullpath):
        raise argparse.ArgumentTypeError("Path \"%s\" must be a directory")
    os.makedirs(fullpath, exist_ok=True)
    return fullpath

def read_write_file_exists(argument):
    fullpath = os.path.abspath(argument)
    if not os.path.isfile(fullpath):
        raise argparse.ArgumentTypeError("Path \"%s\" must be a file")
    return open(fullpath, 'a+b')

def initdb():
    global _CURRENT_DATABASE
    if os.path.isfile(configfile):
        reader = open(configfile)
        database_path = reader.read().strip()
        reader.close()
        if database_path != "<N/A>":
            _CURRENT_DATABASE = db(database_path)
    if not _CURRENT_DATABASE:
        writer = open(configfile, mode='w')
        writer.write("<N/A>\n")
        writer.close()
        sys.exit("No database loaded.  Please run '$ quicksave init' to create or load a database")

def command_init(args):
    writer = open(configfile, mode='w')
    writer.write(args.database_path+'\n')
    writer.close()

def command_register(args):
    initdb()
    filepath = os.path.abspath(args.filename.name)
    (key, folder) = _CURRENT_DATABASE.register_pk(filepath)
    if key in _SPECIAL_PRIMARY:
        sys.exit("Unable to register: The provided filename overwrites a reserved primary key (%s)"%key)
    aliases = []
    if len(args.aliases):
        for user_alias in args.aliases:
            if user_alias in _SPECIAL_PRIMARY:
                sys.exit("Unable to register: Cannot create an alias which overwrites a reserved primary key (%s)"%user_alias)
            if _CURRENT_DATABASE.register_pa(key, user_alias):
                aliases.append(''+user_alias)
        if not len(aliases):
            sys.exit("Unable to register: None of the provided aliases were available")
    if filepath not in _SPECIAL_PRIMARY and _CURRENT_DATABASE.register_pa(key, filepath):
        aliases.append(filepath)
    if os.path.basename(filepath) not in _SPECIAL_PRIMARY and _CURRENT_DATABASE.register_pa(key, os.path.basename(filepath)):
        aliases.append(os.path.basename(filepath))
    (statekey, datafile) = _CURRENT_DATABASE.register_sk(key, os.path.relpath(filepath))
    hasher = sha256()
    chunk = args.filename.read(4096)
    while len(chunk):
        hasher.update(chunk)
        chunk = args.filename.read(4096)
    args.filename.close()
    hashalias = hasher.hexdigest()
    _CURRENT_DATABASE.register_sa(key, statekey, hashalias)
    if key+":"+hashalias[:7] in _CURRENT_DATABASE.state_keys:
        del _CURRENT_DATABASE.state_keys[key+":"+hashalias[:7]]
    else:
        _CURRENT_DATABASE.register_sa(key, statekey, hashalias[:7])
    _CURRENT_DATABASE.save()
    print("Registered new primary key:", key)
    print("Aliases for this key:", aliases)
    print("Initial state key:", statekey)

def command_save(args):
    initdb()
    infer = not bool(args.primary_key)
    if infer:
        filepath = os.path.abspath(args.filename.name)
        if filepath in _CURRENT_DATABASE.primary_keys:
            args.primary_key = _CURRENT_DATABASE.resolve_key(filepath, True)
        elif os.path.basename(filepath) in _CURRENT_DATABASE.primary_keys:
            args.primary_key = _CURRENT_DATABASE.resolve_key(os.path.basename(filepath), True)
        else:
            sys.exit("Unable to save: Could not infer the primary key.  Please set one explicitly with the -p option")
    if args.primary_key not in _CURRENT_DATABASE.primary_keys:
        sys.exit("Unable to save: The requested primary key does not exist in this database (%s)" %(args.primary))
    (key, datafile) = _CURRENT_DATABASE.register_sk(args.primary_key, os.path.abspath(args.filename.name))
    aliases = []
    if len(args.aliases):
        for user_alias in args.aliases:
            if user_alias in _SPECIAL_STATE:
                sys.exit("Unable to save: Cannot create an alias which overwrites a reserved state key (%s)" % user_alias)
            if _CURRENT_DATABASE.register_sa(args.primary_key, key, user_alias, args.force):
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
    _CURRENT_DATABASE.register_sa(args.primary_key, key, hashalias)
    if args.primary_key+":"+hashalias[:7] in _CURRENT_DATABASE.state_keys:
        del _CURRENT_DATABASE.state_keys[args.primary_key+":"+hashalias[:7]]
    elif args.force or args.primary_key+":"+hashalias not in _CURRENT_DATABASE.state_keys:
        _CURRENT_DATABASE.register_sa(args.primary_key, key, hashalias[:7], args.force)
        aliases.append(hashalias[:7])
    _CURRENT_DATABASE.save()
    if infer:
        print("Inferred primary key:", args.primary_key)
    print("New state key:", key)
    print("Aliases for this key:", aliases)

def command_revert(args):
    initdb()
    infer = not bool(args.primary_key)
    did_stash = False
    if infer:
        filepath = os.path.abspath(args.filename.name)
        if filepath in _CURRENT_DATABASE.primary_keys:
            args.primary_key = _CURRENT_DATABASE.resolve_key(filepath, True)
        elif os.path.basename(filepath) in _CURRENT_DATABASE.primary_keys:
            args.primary_key = _CURRENT_DATABASE.resolve_key(os.path.basename(filepath), True)
        else:
            sys.exit("Unable to revert: Could not infer the primary key.  Please set one explicitly with the -p option")
    if args.primary_key not in _CURRENT_DATABASE.primary_keys:
        sys.exit("Unable to revert: The requested primary key does not exist in this database (%s)" %(args.primary))
    args.primary_key = _CURRENT_DATABASE.resolve_key(args.primary_key, True)
    if args.stash and not args.state == '~stash':
        did_stash = True
        if args.primary_key+":~stash" in _CURRENT_DATABASE.state_keys:
            oldfile = _CURRENT_DATABASE.state_keys[args.primary_key+":~stash"][2]
            if oldfile in _CURRENT_DATABASE.primary_keys[args.primary_key][2]:
                _CURRENT_DATABASE.primary_keys[args.primary_key][2].remove(oldfile)
            del _CURRENT_DATABASE.state_keys[args.primary_key+":~stash"]
        _CURRENT_DATABASE.register_sk(args.primary_key, os.path.abspath(args.filename.name), '~stash')
    if args.primary_key+":"+args.state not in _CURRENT_DATABASE.state_keys:
        sys.exit("Unable to revert: The requested state (%s) does not exist for this primary key (%s)" %(args.state, args.primary_key))
    args.filename.close()
    authoritative_key = _CURRENT_DATABASE.resolve_key(args.primary_key+":"+args.state, False)
    statefile = _CURRENT_DATABASE.state_keys[authoritative_key][2]
    copyfile(os.path.join(_CURRENT_DATABASE.primary_keys[args.primary_key][1], statefile), args.filename.name)
    if infer:
        print("Inferred primary key:", args.primary_key)
    print("State key reverted to:", authoritative_key.replace(args.primary_key+":", '', 1))
    if did_stash:
        _CURRENT_DATABASE.save()
        print("Old state saved to: ~stash")

def command_alias(args):
    sys.exit("This command is not yet ready")

def command_list(args):
    initdb()
    if not args.primary:
        print("Showing all primary keys", "and aliases" if args.aliases else '')
        print()
        for key in _CURRENT_DATABASE.primary_keys:
            isprimary = _CURRENT_DATABASE.primary_keys[key][0]
            if not isprimary:
                print('Primary Key: ' if args.aliases else '', key, sep='')
            elif args.aliases:
                print("Primary Alias:", key, "(Alias of: %s)"%isprimary)
    else:
        if args.primary not in _CURRENT_DATABASE.primary_keys:
            sys.exit("Unable to list: The requested primary key does not exist in this database (%s)" %(args.primary))
        print("Showing all state keys", " and aliases" if args.aliases else '', " for primary key ", args.primary, sep='')
        print()
        for key in _CURRENT_DATABASE.state_keys:
            if _CURRENT_DATABASE.state_keys[key][1] == args.primary:
                isprimary = _CURRENT_DATABASE.state_keys[key][0]
                display_key = key.replace(args.primary+":", '', 1)
                if not isprimary:
                    print("State Key: " if args.aliases else '', display_key, sep='')
                elif args.aliases:
                    print("State Alias:", display_key, "(Alias of: %s)"%isprimary.replace(args.primary+":", '', 1))

def command_delete(args):
    sys.exit("This command is not yet ready")

def command_lookup(args):
    initdb()
    if not (args.primary or args.target in _CURRENT_DATABASE.primary_keys):
        sys.exit("Unable to lookup: The requested primary key does not exist in this database (%s)" %(args.primary))
    if args.primary:
        args.primary = _CURRENT_DATABASE.resolve_key(args.primary, True)
    if args.primary and args.primary+":"+args.target not in _CURRENT_DATABASE.state_keys:
        sys.exit("Unable to lookup: The requested state (%s) does not exist for this primary key (%s)" %(args.target, args.primary))
    keyheader = args.primary+":" if args.primary else ''
    result = _CURRENT_DATABASE.resolve_key(keyheader+args.target, not args.primary)
    if keyheader:
        result = result.replace(args.primary+":", '', 1)
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
        "file are grouped together by a few primary keys which distinguish the set from other files.\n"+
        "A new unique primary key will be automatically generated, but this key can also be aliased by\n"+
        "the original absolute filepath of the file, the original filename, and any user provided aliases.\n"+
        "Note that the following primary keys are reserved for special use: "+str(_SPECIAL_PRIMARY)+".\n"+
        "Returns the primary key and list of aliases for the new set of versions, and the initial state key for the starting version"
    )
    register_parser.set_defaults(func=command_register)
    register_parser.add_argument(
        'filename',
        type=argparse.FileType('rb'),
        help="The file to save.  The filename and path will be used as aliases for the new primary key\n"+
        "if they are not already aliases for a different primary key"
    )
    register_parser.add_argument(
        'aliases',
        nargs='*',
        help="A list of user-defined aliases for the primary key.  Quotes must be used to surround any aliases containing spaces.\n"+
        "Aliases must be unique within the database.  Non-unique aliases are ignored, but if any aliases are provided,\n"+
        "at least one must be unique or the operation will be canceled."
    )

    save_parser = subparsers.add_parser(
        'save',
        description="Saves the current state of the file to the set of versions for this file.\n"+
        "Quicksave will attempt to infer the primary key if one is not provided explicitly.\n"+
        "A new unique state key will be automatically generated, but this key can also be aliased by\n"+
        "the sha-256 hash of the file contents (and just the first 7 characters iff that is unique under this primary key)\n"+
        "and any user defined aliases. The following state keys are reserved for special use: "+str(_SPECIAL_STATE)+".\n"+
        "Returns the primary key (iff it was inferred), the new state key, and a list of aliases"
    )
    save_parser.set_defaults(func=command_save)
    save_parser.add_argument(
        'filename',
        type=argparse.FileType('rb'),
        help="The file to save.  Iff the filename differs from the original filename for the primary key,\n"+
        "it will be added as an alias to the new state key."
    )
    save_parser.add_argument(
        '-p', '--primary-key',
        help="The primary key linked to the set of states to save this file in.\n"+
        "If the primary key is not specified it will be inferred by the full filepath or the filename (in that order).\n"+
        "If neither the filepath nor the filename match any primary key aliases in this database,\n"+
        "quicksave will require the user to provide this option.",
        default=None
    )
    save_parser.add_argument(
        'aliases',
        nargs='*',
        help="A list of user-defined aliases for the current state.  Quotes must be used to surround any aliases containing spaces.\n"+
        "Aliases must be unique under this primary key.  Non-unique aliases are ignored, but if any aliases are provided,\n"+
        "at least one must be unique or the operation will be canceled."
    )
    save_parser.add_argument(
        '-f', '--force',
        action='store_true',
        help="Overwrite any existing state aliases.  The automatically generated state key will always be unique\n"+
        "but the 7 character sha-256 prefix and any user aliases will overwrite existing state aliaes."
    )

    revert_parser = subparsers.add_parser(
        'revert',
        description="Reverts the specified file to the state specified by the provided state key or alias.\n"+
        "Quicksave will attempt to infer the primary key if one is not provided explicitly.\n"+
        "Returns the primary key iff it was inferred and the authoritative state key reverted to"
    )
    revert_parser.set_defaults(func=command_revert)
    revert_parser.add_argument(
        'filename',
        type=read_write_file_exists,
        help="The file to revert"
    )
    revert_parser.add_argument(
        '-p', '--primary-key',
        help="The primary key which contains the state being reverted to.\n"+
        "If the primary key is not specified it will be inferred by the full filepath or the filename (in that order).\n"+
        "If neither the filepath nor the filename match any primary key aliases in this database,\n"+
        "quicksave will require the user to provide this option.",
        default=None
    )
    revert_parser.add_argument(
        'state',
        help="The state key or alias to revert to."
    )
    revert_parser.add_argument(
        '--stash',
        action='store_true',
        help="Quickly save the state under the ~stash state key before reverting.\n"+
        "This *CANNOT* be used if reverting to ~stash and will be ignored if provided in that case.\n"
        "If the file's full sha-256 hash is currently registered as a state alias,\n"+
        "then ~stash will simply alias this file's true state key.\n"+
        "Otherwise, the full state will be saved under ~stash.\n"
        "The ~stash state key should not be used for permanent storage as it may be frequently overwritten.\n"+
        "To save the current ~stash state permanently, use \n"+
        "'$ quicksave revert <filename> ~stash' then\n"+
        "'$ quicksave save <filename>'"
    )

    alias_parser = subparsers.add_parser(
        'alias',
        description="Create, override, or delete an alias for a primary or state key.\n"+
        "The action taken by this command depends on the specific command syntax:\n"+
        "'$ quicksave <link> <target>' creates or overwrites the primary key alias <link> to point to the primary key (or alias) <target>.\n"+
        "'$ quicksave -d <link>' deletes the primary key alias <link>.  Cannot delete primary keys (only aliases).\n"+
        "'$ quicksave <link> <target> <primary>' creates or overwrites the state key alias <link> to point to the state key (or alias) <target> under the primary key <primary>.\n"+
        "'$ quicksave -d <link> <primary>' delets the state key alias <link> under the primary key <primary>.  Cannot delete state keys (only aliases).\n"+
        "To delete authoritative primary or state keys, use '$ quicksave delete-key <primary key> [state key]'"
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
        'primary',
        nargs='?',
        help="The primary key (or alias) containing the desired state key (or alias) <target>",
        default=None
    )
    alias_parser.add_argument(
        '-d',
        action='store_true',
        help='Deletes the provided primary or state alias'
    )

    list_parser = subparsers.add_parser(
        'list',
        description="Lists all primary keys in this database, or all state keys under a provided primary key (or alias)"
    )
    list_parser.set_defaults(func=command_list)
    list_parser.add_argument(
        'primary',
        nargs='?',
        help="If provided, list all state keys under this primary key or alias",
        default=None
    )
    list_parser.add_argument(
        '-a', '--aliases',
        action='store_true',
        help='Display key aliases in addition to just keys'
    )

    delete_parser = subparsers.add_parser(
        'delete-key',
        description="Deletes a primary or state key, and all its aliases"
    )
    delete_parser.set_defaults(func=command_delete)
    delete_parser.add_argument(
        'primary',
        nargs='?',
        help="If provided, delete the state key <target> from within this primary key (or alias)",
        default=None
    )
    delete_parser.add_argument(
        'target',
        help="The target primary or state key to delete.\n"+
        "Iff <primary> is provided, then <target> is taken to be a state key, otherwise it is taken to be a primary key.\n"+
        "This *MUST* be an authoritative key, and not an alias.  Aliases can be deleted using the 'alias' command"
    )
    delete_parser.add_argument(
        '--no-save',
        action='store_false',
        help="By default, deleted primary or state keys are saved under the ~trash key\n"+
        "(which is a reserved primary key and a reserved state key under all primary keys).\n"+
        "~trash should not be used for permanent storage as it may be overwritten frequently.\n"+
        "To recover the ~trash *PRIMARY* key, use '$ quicksave recover [aliases...]'.\n"+
        "To recover the ~trash *STATE* key, use\n"+
        "'$ quicksave revert <filename> ~trash' then\n"+
        "'$ quicksave save <filename>'.  Note that old aliases of the deleted state key will not be recovered, and must be set manually",
        dest='save'
    )

    lookup_parser = subparsers.add_parser(
        'lookup',
        description="Returns the authoritative primary or state key for a given alias"
    )
    lookup_parser.set_defaults(func=command_lookup)
    lookup_parser.add_argument(
        'primary',
        nargs='?',
        help="If provided, lookup the state alias <target> from within this primary key (or alias)",
        default=None
    )
    lookup_parser.add_argument(
        'target',
        help="The target primary or state alias to lookup.\n"+
        "Iff <primary> is provided, then <target> is taken to be a state alias, otherwise it is taken to be a primary alias."
    )

    recover_parser = subparsers.add_parser(
        'recover',
        description="Recovers the most recently deleted primary key.\n"+
        "The recovered data will be saved under a uniquely generated key, but a list of aliases may also be provided.\n"+
        "Old aliases of the deleted key are not recovered, and must be set manually.\n"+
        "Returns the new primary key and list of aliases, if provided"
    )
    recover_parser.set_defaults(func=command_recover)
    recover_parser.add_argument(
        'aliases',
        nargs="+",
        help="A list of user-defined aliases for the recovered key.  Quotes must be used to surround any aliases containing spaces.\n"+
        "Aliases must be unique within the database.  Non-unique aliases are ignored, but if any aliases are provided,\n"+
        "at least one must be unique or the operation will be canceled."
    )

    args = parser.parse_args(args_input)
    if 'func' not in dir(args):
        parser.print_help()
        sys.exit(2)
    args.func(args)


if __name__ == '__main__':
    # print("No previous database registered in config file.  Please run '$ quicksave init'")
    main()
