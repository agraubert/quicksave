import os
import sys
from .. import utils

def command_save(args, do_print):
    utils.initdb(do_print)
    infer = not bool(args.file_key)
    if infer:
        filepath = os.path.abspath(args.filename.name)
        if utils._checkflag('inference.path', '1')=='1' and filepath in utils._CURRENT_DATABASE.file_keys:
            args.file_key = utils._CURRENT_DATABASE.resolve_key(filepath, True)
        elif utils._checkflag('inference.name', '1')=='1' and os.path.basename(filepath) in utils._CURRENT_DATABASE.file_keys:
            args.file_key = utils._CURRENT_DATABASE.resolve_key(os.path.basename(filepath), True)
        else:
            sys.exit("Unable to save: Could not infer the file key.  Please set one explicitly with the -k option")
    if args.file_key not in utils._CURRENT_DATABASE.file_keys:
        sys.exit("Unable to save: The requested file key does not exist in this database (%s)" %(args.file_key))
    args.file_key = utils._CURRENT_DATABASE.resolve_key(args.file_key, True)
    hashalias = utils.gethash(args.filename)
    args.filename.close()
    currentstate = utils.fetchstate(hashalias, args.file_key)
    if currentstate and not args.allow_duplicate:
        sys.exit("Unable to save: Duplicate of %s (use --allow-duplicate to override this behavior, or '$ quicksave alias' to create aliases)"%(
            currentstate.replace(args.file_key+":", '', 1)
        ))
    (key, datafile) = utils._CURRENT_DATABASE.register_sk(args.file_key, os.path.abspath(args.filename.name))
    utils._CURRENT_DATABASE.register_fa(args.file_key, '~last', True)
    aliases = []
    if len(args.aliases):
        for user_alias in args.aliases:
            if user_alias in utils._SPECIAL_STATE:
                sys.exit("Unable to save: Cannot create an alias which overwrites a reserved state key (%s)" % user_alias)
            if utils._CURRENT_DATABASE.register_sa(args.file_key, key, user_alias, args.force):
                aliases.append(''+user_alias)
        if not len(aliases):
            sys.exit("Unable to save: None of the provided aliases were available")
    if args.file_key+":"+hashalias[:7] in utils._CURRENT_DATABASE.state_keys:
        del utils._CURRENT_DATABASE.state_keys[args.file_key+":"+hashalias[:7]]
    elif args.file_key+":"+hashalias not in utils._CURRENT_DATABASE.state_keys:
        utils._CURRENT_DATABASE.register_sa(args.file_key, key, hashalias[:7], args.force)
        aliases.append(hashalias[:7])
    basefile = os.path.basename(args.filename.name)
    if ((basefile not in utils._CURRENT_DATABASE.file_keys or utils._CURRENT_DATABASE.file_keys[basefile][0]!=args.file_key) and
        args.file_key+":"+basefile not in utils._CURRENT_DATABASE.state_keys):
        utils._CURRENT_DATABASE.register_sa(args.file_key, key, basefile)
        aliases.append(""+basefile)
    utils._CURRENT_DATABASE.register_sa(args.file_key, key, hashalias)
    utils._CURRENT_DATABASE.save()
    if infer:
        do_print("Inferred file key:", args.file_key)
    do_print("New state key:", key)
    do_print("Aliases for this key:", aliases)
    return [args.file_key, key, [item for item in aliases]]
