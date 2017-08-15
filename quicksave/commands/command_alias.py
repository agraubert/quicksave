import sys
from .. import utils

def command_alias(args, do_print):
    utils.initdb(do_print)
    msg = ""
    _data_result = []
    if not (args.d or args.target or args.filekey):
        args.help()
        sys.exit("Unable to modify table: Not enough arguments provided to determine action")
    if not ((args.d and args.target) or args.filekey): #working with file keys
        if args.d:
            if args.link not in utils._CURRENT_DATABASE.file_keys:
                sys.exit("Unable to delete alias: The provided file alias does not exist (%s)"%args.link)
            result = utils._CURRENT_DATABASE.file_keys[args.link]
            if not result[0]:
                sys.exit("Unable to delete alias: The provided alias was a file key (%s).  Use '$ quicksave delete-key <file key>' to delete file keys"%(args.link))
            del utils._CURRENT_DATABASE.file_keys[args.link]
            utils._CURRENT_DATABASE.register_fa(result[0], '~last', True)
            msg = "Deleted file alias: %s"%args.link
            _data_result = [args.link]
        elif args.target:
            if args.target not in utils._CURRENT_DATABASE.file_keys:
                sys.exit("Unable to create alias: The provided target key does not exist (%s)"%args.target)
            if args.link in utils._CURRENT_DATABASE.file_keys and not utils._CURRENT_DATABASE.file_keys[args.link][0]:
                sys.exit("Unable to create alias: The provided alias name is already in use by a file key (%s)"%args.link)
            if args.link in utils._SPECIAL_FILE:
                sys.exit("Unable to create alias: The requested alias overwrites a reserved file key (%s)"%args.link)
            authoritative_key = utils._CURRENT_DATABASE.resolve_key(args.target, True)
            utils._CURRENT_DATABASE.register_fa(authoritative_key, args.link, True)
            utils._CURRENT_DATABASE.register_fa(authoritative_key, '~last', True)
            msg = "Registered file alias: %s --> %s"%(args.link, authoritative_key)
            _data_result = [args.link, authoritative_key]
    else:
        if args.d:
            if not args.target:
                sys.exit("Unable to delete alias: A file key must be provided as the second argument")
            if args.target not in utils._CURRENT_DATABASE.file_keys:
                sys.exit("Unable to delete alias: The provided file key does not exist (%s)"%args.target)
            if args.filekey:
                sys.exit("Unable to delete alias: Unexpected argument: %s"%args.filekey)
            filekey = utils._CURRENT_DATABASE.resolve_key(args.target, True)
            if filekey+":"+args.link not in utils._CURRENT_DATABASE.state_keys:
                sys.exit("Unable to delete alias: The provided state alias does not exist (%s)"%args.link)
            result = utils._CURRENT_DATABASE.state_keys[filekey+":"+args.link]
            if not result[0]:
                sys.exit("Unable to delete alias: The provided alias was a state key (%s).  Use '$ quicksave delete-key <file key> <state key>' to delete state keys"%(args.link))
            del utils._CURRENT_DATABASE.state_keys[filekey+":"+args.link]
            msg = "Deleted state alias: %s from file key %s"%(args.link, filekey)
            utils._CURRENT_DATABASE.register_fa(filekey, '~last', True)
            _data_result = [args.link, filekey]
        else:
            if not args.filekey:
                sys.exit("Unable to create state alias: A file key or alias was not provided")
            elif args.filekey not in utils._CURRENT_DATABASE.file_keys:
                sys.exit("Unable to create alias: The provided file key does not exist (%s)"%args.filekey)
            filekey = utils._CURRENT_DATABASE.resolve_key(args.filekey, True)
            if filekey+":"+args.target not in utils._CURRENT_DATABASE.state_keys:
                sys.exit("Unable to create alias: The provided state key does not exist (%s)"%args.target)
            if args.link in utils._SPECIAL_STATE:
                sys.exit("Unable to create alias: The requested alias overwrites a reserved state key (%s)"%args.link)
            statekey = utils._CURRENT_DATABASE.resolve_key(filekey+":"+args.target, False)
            if filekey+":"+args.link in utils._CURRENT_DATABASE.state_keys and not utils._CURRENT_DATABASE.state_keys[filekey+":"+args.link][0]:
                sys.exit("Unable to create alias: The provided alias name is already in use by a state key (%s)"%args.link)
            utils._CURRENT_DATABASE.register_sa(filekey, statekey.replace(filekey+":", '', 1), args.link, True)
            utils._CURRENT_DATABASE.register_fa(filekey, '~last', True)
            msg = "Registered state alias: %s --> %s under file key: %s"%(args.link, statekey.replace(filekey+":", '', 1), filekey)
            _data_result = [args.link, statekey.replace(filekey+":",'',1), filekey]
    do_print(msg)
    utils._CURRENT_DATABASE.save()
    return _data_result
