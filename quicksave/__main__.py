import argparse
import sys
import os
from . import utils
from . import commands

if sys.version_info < (3,3):
    FileNotFoundError = IOError

def main(args_input=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        "quicksave",
        description="A very simple file versioning system.  Useful for quickly "+
        " maintaining a few versions of a file without setting up a full version control repository",
    )
    parser.add_argument(
        '--return-result',
        action='store_true',
        help=argparse.SUPPRESS
    )
    subparsers = parser.add_subparsers()
    helper = {'__main__':parser.print_help}

    init_parser = subparsers.add_parser(
        'init', aliases=['load-db'],
        description="Initializes the quicksave database at the specified path.\n"+
        "If the path does not exist, then create an empty database.\n"+
        "If the path does exist, attempt to load an existing database"
    )
    init_parser.set_defaults(func=commands.command_init)
    helper['init'] = init_parser.print_help
    helper['load-db'] = init_parser.print_help
    init_parser.add_argument(
        'database_path',
        type=utils.check_is_directory,
        default=os.path.join(os.path.expanduser('~'), '.quicksave_db'),
        nargs='?',
        help="The database path to initialize.  If it exists, then load the database.  If not, then create a new one"
    )

    register_parser = subparsers.add_parser(
        'register',
        description="Registers a new file for versioning.  Different versions of a single\n"+
        "file are grouped together by a few file keys which distinguish the set from other files.\n"+
        "A new unique file key will be automatically generated, but this key can also be aliased by\n"+
        "the original absolute filepath of the file, the original filename, and any user provided aliases.\n"+
        "Note that the following file keys are reserved for special use: "+str(utils._SPECIAL_FILE)+".\n"+
        "Returns the file key and list of aliases for the new set of versions, and the initial state key for the starting version"
    )
    register_parser.set_defaults(func=commands.command_register)
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
        "and any user defined aliases. The following state keys are reserved for special use: "+str(utils._SPECIAL_STATE)+".\n"+
        "Returns the file key (iff it was inferred), the new state key, and a list of aliases"
    )
    save_parser.set_defaults(func=commands.command_save)
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
    revert_parser.set_defaults(func=commands.command_revert)
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
    revert_parser.add_argument(
        '-f', '--force',
        action='store_true',
        help="Forces the revert to progress even if the file is already in the requested state"
    )

    alias_parser = subparsers.add_parser(
        'alias',
        description="Create, override, or delete an alias for a file or state key.\n"+
        "The action taken by this command depends on the specific command syntax:\n"+
        "'$ quicksave alias <link> <target>' creates or overwrites the file key alias <link> to point to the file key (or alias) <target>.\n"+
        "'$ quicksave alias -d <link>' deletes the file key alias <link>.  Cannot delete file keys (only aliases).\n"+
        "'$ quicksave alias <link> <target> <filekey>' creates or overwrites the state key alias <link> to point to the state key (or alias) <target> under the file key <file>.\n"+
        "'$ quicksave alias -d <link> <filekey>' deletes the state key alias <link> under the file key <filekey>.  Cannot delete state keys (only aliases).\n"+
        "To delete authoritative file or state keys, use '$ quicksave delete-key <file key> [state key]'"
    )
    alias_parser.set_defaults(func=commands.command_alias)
    alias_parser.set_defaults(help=alias_parser.print_usage)
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
    list_parser.set_defaults(func=commands.command_list)
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
    list_parser.add_argument(
        '-t', '--target',
        help="Only display aliases for the provided target key.  Implies the -a option. "+
        "If filekey is provided, then this must be a state key or alias. "+
        "Otherwise, this must be a file key or alias",
        default=None
    )

    delete_parser = subparsers.add_parser(
        'delete-key',
        aliases=['rm', 'delete'],
        description="Deletes a file or state key, and all its aliases"
    )
    delete_parser.set_defaults(func=commands.command_delete)
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
    lookup_parser.set_defaults(func=commands.command_lookup)
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
    recover_parser.set_defaults(func=commands.command_recover)
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
    show_parser.set_defaults(func = lambda args, printer:utils.initdb(printer) if args.return_result else printer(utils.initdb(printer)))
    helper['show'] = show_parser.print_help

    clean_parser = subparsers.add_parser(
        'clean',
        description="Cleans the database to reduce used space.\n"+
        "If no flags are set, this is a no-op. Each flag enables a different stage of cleaning"
    )
    clean_parser.set_defaults(func=commands.command_clean)
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
        help="WARNING: deduplication may take a very long time, depending on the "+
        "size of your database as it must compute hashes for every single state "+
        "of every single file in the database. "+
        "Scans the database for state keys which store identical states of "+
        "a file under the same file key. Removes all but one state key from each "+
        "set of duplicates, and updates all aliases of the deleted keys to point "+
        "to the remaining state key.  Deduplication will also replace any missing "+
        "hash aliases for all remaining states."
    )
    clean_parser.add_argument(
        '-w', '--walk-database',
        action='store_true',
        help="Checks the database file manifest against the list of files visible "+
        "within the directory.  Files found in the database directory that do not "+
        "exist in the manifest are deleted.  Files listed in the manifest which cannot "+
        "be found in the directory will have their corresponding state key (and its aliases) deleted"
    )
    clean_parser.add_argument(
        '-a', '--aliases',
        action='store_true',
        help="Checks for and removes any aliases which point to invalid or nonexistent keys"
    )
    clean_parser.add_argument(
        '-s', '--states',
        action='store_true',
        help="Checks for and removes any state keos.path.basename(aliases with missing parent file keys"
    )
    clean_parser.add_argument(
        '-r', '--rebuild-file-index',
        action='store_true',
        help="Checks the file index for each file key against the filename registered to each state key. "+
        "The file index is rebuilt using this list of filenames."
    )
    clean_parser.add_argument(
        '--clean-all',
        action='store_true',
        help="Runs all cleaning subroutines.  Equivalent to -tdwasr"
    )

    status_parser = subparsers.add_parser(
        'status',
        description="Checks if the given file currently matches a known state"
    )
    status_parser.set_defaults(func=commands.command_status)
    helper['status'] = status_parser.print_help
    status_parser.add_argument(
        'filename',
        type=argparse.FileType('rb'),
        help="The file to check"
    )
    status_parser.add_argument(
        '-k', '--file-key',
        help="The file key linked to the set of states to save this file in.\n"+
        "If the file key is not specified it will be inferred by the full filepath or the filename (in that order).\n"+
        "If neither the filepath nor the filename match any file key aliases in this database,\n"+
        "quicksave will require the user to provide this option.",
        default=None
    )

    config_parser = subparsers.add_parser(
        'config',
        description="Sets or checks the current configuration of quicksave"
    )
    config_parser.set_defaults(func=commands.command_config)
    config_parser.set_defaults(help=config_parser.print_usage)
    helper['config'] = config_parser.print_help
    config_parser.add_argument(
        'key',
        nargs='?',
        help="The name of the setting to check or set. This argument is always "
        "required unless using --list to view all keys",
        default=None
    )
    config_parser.add_argument(
        'value',
        nargs='?',
        help="The value to set.  If not specified, read the current setting",
        default=None
    )
    config_parser.add_argument(
        '--global',
        action='store_true',
        help="Saves the setting to the global configuration instead of the current database's configuration. "+
        "This does not apply when reading configuration (when reading configuration, both global and database values are displayed).",
        dest="_global"
    )
    config_parser.add_argument(
        '--clear',
        action='store_true',
        help="Clear the provided key from the database configuration. This "+
        "does not apply when setting configuration"
    )
    config_parser.add_argument(
        '-l',
        '--list',
        action='store_true',
        help="List all configuration keys in use. The 'key' argument is not "
        "required when this option is present",
        dest="_list"
    )

    help_parser = subparsers.add_parser(
        'help',
        description="Displays help about quicksave and its subcommands"
    )
    help_parser.set_defaults(func=lambda args, printer:command_help(args, helper, printer))
    helper['help'] = help_parser.print_help
    help_parser.add_argument(
        'subcommand',
        nargs='?',
        help="The subcommand whose help message should be displayed",
        default = None
    )

    args = parser.parse_args(args_input)

    def do_print(*_args, **kwargs):
        if not args.return_result:
            print(*_args, **kwargs)

    if 'func' not in dir(args):
        parser.print_help()
        sys.exit(2)
    result = None
    try:
        result = args.func(args, do_print)
    except FileNotFoundError as e:
        raise FileNotFoundError("Command failed!  Unable to open a requested file. "+
                                " Try running `$ quicksave clean -w` to clean the database") from e
    except Exception as e:
        raise RuntimeError("Command failed!  Encountered an unknown exception!") from e
    if args.return_result:
        return result

def command_help(args, helper, do_print):
    if not args.subcommand:
        helper['__main__']()
        do_print("\nUse '$ quicksave help <subcommand>' for help with a specific subcommand")
    elif args.subcommand =='__main__' or args.subcommand not in helper:
        sys.exit("Unknown subcommand name: %s"%args.subcommand)
    else:
        helper[args.subcommand]()

if __name__ == '__main__':
    # print("No previous database registered in config file.  Please run '$ quicksave init'")
    main()
