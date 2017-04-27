import sys
from .. import utils

def command_lookup(args, do_print):
    utils.initdb(do_print)
    if not (args.filekey or args.target in utils._CURRENT_DATABASE.file_keys):
        sys.exit("Unable to lookup: The requested file key does not exist in this database (%s)" %(
            args.filekey if args.filekey else args.target
        ))
    if args.filekey:
        if args.filekey not in utils._CURRENT_DATABASE.file_keys:
            sys.exit("Unable to lookup: The requested file key does not exist in this database (%s)"%args.filekey)
        args.filekey = utils._CURRENT_DATABASE.resolve_key(args.filekey, True)
    if args.filekey and args.filekey+":"+args.target not in utils._CURRENT_DATABASE.state_keys:
        sys.exit("Unable to lookup: The requested state (%s) does not exist for this file key (%s)" %(args.target, args.filekey))
    keyheader = args.filekey+":" if args.filekey else ''
    result = utils._CURRENT_DATABASE.resolve_key(keyheader+args.target, not args.filekey)
    if keyheader:
        result = result.replace(args.filekey+":", '', 1)
    do_print(args.target, '-->', result)
    return result
