import os
import sys
from .. import utils

def command_status(args, do_print):
    utils.initdb(do_print)
    infer = not bool(args.file_key)
    did_stash = False
    if infer:
        filepath = os.path.abspath(args.filename.name)
        if utils._checkflag('inference.path', '1')=='1' and filepath in utils._CURRENT_DATABASE.file_keys:
            args.file_key = utils._CURRENT_DATABASE.resolve_key(filepath, True)
        elif utils._checkflag('inference.name', '1')=='1' and os.path.basename(filepath) in utils._CURRENT_DATABASE.file_keys:
            args.file_key = utils._CURRENT_DATABASE.resolve_key(os.path.basename(filepath), True)
        else:
            sys.exit("Unable to check status: Could not infer the file key.  Please set one explicitly with the -k option")
    if args.file_key not in utils._CURRENT_DATABASE.file_keys:
        sys.exit("Unable to check status: The requested file key does not exist in this database (%s)" %(args.file_key))
    args.file_key = utils._CURRENT_DATABASE.resolve_key(args.file_key, True)
    utils._CURRENT_DATABASE.register_fa(args.file_key, '~last', True)
    hashalias = utils.gethash(args.filename)
    currentstate = utils.fetchstate(hashalias, args.file_key)
    args.filename.close()
    basefile = os.path.basename(args.filename.name)
    if infer:
        do_print("Inferred file key:", args.file_key)
    do_print("Status:", basefile,"-->",
        '"'+currentstate.replace(args.file_key+":", '', 1)+'"' if currentstate else "<New State>"
    )
    return [args.file_key, currentstate]
