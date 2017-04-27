import sys
from .. import utils

def command_list(args, do_print):
    utils.initdb(do_print)
    output = []
    if args.target:
        args.aliases = True
    if not args.filekey:
        if args.target and args.target not in utils._CURRENT_DATABASE.file_keys:
            sys.exit("Unable to list: The provided target file key does not exist in this database (%s)"%args.target)
        do_print("Showing all file keys", "and aliases" if args.aliases else '')
        do_print()
        if args.target:
            args.target = utils._CURRENT_DATABASE.resolve_key(args.target, True)
        source = utils._CURRENT_DATABASE.file_keys if not args.target else filter(
            lambda x:x==args.target or utils._CURRENT_DATABASE.file_keys[x][0]==args.target,
            utils._CURRENT_DATABASE.file_keys
        )
        for key in source:
            isfile = utils._CURRENT_DATABASE.file_keys[key][0]
            if not isfile:
                do_print('File Key: ' if args.aliases else '', key, sep='')
                output.append(key)
            elif args.aliases:
                do_print("File Alias:", key, "(Alias of: %s)"%isfile)
                output.append(key)
    else:
        if args.filekey not in utils._CURRENT_DATABASE.file_keys:
            sys.exit("Unable to list: The requested file key does not exist in this database (%s)" %(args.filekey))
        args.filekey = utils._CURRENT_DATABASE.resolve_key(args.filekey, True)
        if args.target:
            args.target = utils._CURRENT_DATABASE.resolve_key(args.filekey+":"+args.target, False)
        if args.target and args.target not in utils._CURRENT_DATABASE.state_keys:
            sys.exit("Unable to list: The provided target state key does not exist in this database (%s)"%args.target)
        do_print("Showing all state keys", " and aliases" if args.aliases else '', " for file key ", args.filekey, sep='')
        do_print()
        source = utils._CURRENT_DATABASE.state_keys if not args.target else filter(
            lambda x:x==args.target or utils._CURRENT_DATABASE.state_keys[x][0]==args.target,
            utils._CURRENT_DATABASE.state_keys
        )
        for key in source:
            if utils._CURRENT_DATABASE.state_keys[key][1] == args.filekey:
                isfile = utils._CURRENT_DATABASE.state_keys[key][0]
                display_key = key.replace(args.filekey+":", '', 1)
                if not isfile:
                    do_print("State Key: " if args.aliases else '', display_key, sep='')
                    output.append(display_key)
                elif args.aliases:
                    do_print("State Alias:", display_key, "(Alias of: %s)"%isfile.replace(args.filekey+":", '', 1))
                    output.append(display_key)
    return [item for item in output]
