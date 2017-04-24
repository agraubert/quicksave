import os
import sys
from .. import utils

def command_register(args, do_print):
    utils.initdb(do_print)
    filepath = os.path.abspath(args.filename.name)
    if filepath in utils._CURRENT_DATABASE.file_keys and not args.ignore_filepath:
        sys.exit("Unable to register: Filepath is registered to file key %s (use --ignore-filepath to override this behavior)"%(
            utils._CURRENT_DATABASE.file_keys[filepath][0]
        ))
    (key, folder) = utils._CURRENT_DATABASE.register_fk(filepath)
    utils._CURRENT_DATABASE.register_fa(key, '~last', True)
    if key in utils._SPECIAL_FILE:
        sys.exit("Unable to register: The provided filename overwrites a reserved file key (%s)"%key)
    file_aliases = []
    if len(args.file_alias):
        for user_alias in args.file_alias:
            if user_alias in utils._SPECIAL_FILE:
                sys.exit("Unable to register: Cannot create a file alias which overwrites a reserved file key (%s)"%user_alias)
            if utils._CURRENT_DATABASE.register_fa(key, user_alias):
                file_aliases.append(''+user_alias)
        if not len(file_aliases):
            sys.exit("Unable to register: None of the provided aliases were available")
    if (
            (utils._checkflag('inference.path', '1')=='1' or utils._checkflag('inference.norecord', '0')=='0') and
            filepath not in utils._SPECIAL_FILE and
            utils._CURRENT_DATABASE.register_fa(key, filepath)
        ):
        file_aliases.append(filepath)
    if (
            (utils._checkflag('inference.name', '1')=='1' or utils._checkflag('inference.norecord', '0')=='0') and
            os.path.basename(filepath) not in utils._SPECIAL_FILE and
            utils._CURRENT_DATABASE.register_fa(key, os.path.basename(filepath))
        ):
        file_aliases.append(os.path.basename(filepath))
    (statekey, datafile) = utils._CURRENT_DATABASE.register_sk(key, os.path.relpath(filepath))
    hashalias = utils.gethash(args.filename)
    args.filename.close()
    utils._CURRENT_DATABASE.register_sa(key, statekey, hashalias)
    state_aliases = []
    if key+":"+hashalias[:7] in utils._CURRENT_DATABASE.state_keys:
        del utils._CURRENT_DATABASE.state_keys[key+":"+hashalias[:7]]
    else:
        utils._CURRENT_DATABASE.register_sa(key, statekey, hashalias[:7])
        state_aliases.append(hashalias[:7])
    if len(args.aliases):
        for user_alias in args.aliases:
            if user_alias in utils._SPECIAL_STATE:
                sys.exit("Unable to register: Cannot create a state alias which overwrites a reserved state key (%s)" % user_alias)
            if utils._CURRENT_DATABASE.register_sa(key, statekey, user_alias):
                state_aliases.append(''+user_alias)
        if not len(state_aliases):
            sys.exit("Unable to save: None of the provided aliases were available")
    utils._CURRENT_DATABASE.save()
    do_print("Registered new file key:", key)
    do_print("Aliases for this file key:", file_aliases)
    do_print("Initial state key:", statekey)
    do_print("Aliases for this state key:", state_aliases)
    return [key, [item for item in file_aliases], statekey, [item for item in state_aliases]]
