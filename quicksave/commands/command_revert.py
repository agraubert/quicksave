import os
import sys
from shutil import copyfile
from .. import utils

def command_revert(args, do_print):
    utils.initdb(do_print)
    infer = not bool(args.file_key)
    did_stash = False
    args.stash = args.stash and utils._checkflag('revert.stash', '1')=='1'
    if infer:
        filepath = os.path.abspath(args.filename.name)
        if utils._checkflag('inference.path', '1')=='1' and filepath in utils._CURRENT_DATABASE.file_keys:
            args.file_key = utils._CURRENT_DATABASE.resolve_key(filepath, True)
        elif utils._checkflag('inference.name', '1')=='1' and os.path.basename(filepath) in utils._CURRENT_DATABASE.file_keys:
            args.file_key = utils._CURRENT_DATABASE.resolve_key(os.path.basename(filepath), True)
        else:
            sys.exit("Unable to revert: Could not infer the file key.  Please set one explicitly with the -k option")
    if args.file_key not in utils._CURRENT_DATABASE.file_keys:
        sys.exit("Unable to revert: The requested file key does not exist in this database (%s)" %(args.file_key))
    args.file_key = utils._CURRENT_DATABASE.resolve_key(args.file_key, True)
    if args.file_key+":"+args.state not in utils._CURRENT_DATABASE.state_keys:
        sys.exit("Unable to revert: The requested state (%s) does not exist for this file key (%s)" %(args.state, args.file_key))
    utils._CURRENT_DATABASE.register_fa(args.file_key, '~last', True)
    hashalias = utils.gethash(args.filename)
    currentstate = utils.fetchstate(hashalias, args.file_key)
    authoritative_key = utils._CURRENT_DATABASE.resolve_key(args.file_key+":"+args.state, False)
    if currentstate == authoritative_key and not args.force:
        sys.exit("Unable to revert: The file is already in the requested state")
    if args.stash and not args.state == '~stash':
        did_stash = True
        if args.file_key+":~stash" in utils._CURRENT_DATABASE.state_keys:
            oldfile = utils._CURRENT_DATABASE.state_keys[args.file_key+":~stash"][2]
            if oldfile in utils._CURRENT_DATABASE.file_keys[args.file_key][2]:
                utils._CURRENT_DATABASE.file_keys[args.file_key][2].remove(oldfile)
            del utils._CURRENT_DATABASE.state_keys[args.file_key+":~stash"]
        if currentstate:
            utils._CURRENT_DATABASE.register_sa(args.file_key, hashalias, '~stash', True)
        else:
            utils._CURRENT_DATABASE.register_sk(args.file_key, os.path.abspath(args.filename.name), '~stash')
    args.filename.close()
    statefile = utils._CURRENT_DATABASE.state_keys[authoritative_key][2]
    copyfile(os.path.join(utils._CURRENT_DATABASE.file_keys[args.file_key][1], statefile), args.filename.name)
    if infer:
        do_print("Inferred file key:", args.file_key)
    do_print("State key reverted to:", authoritative_key.replace(args.file_key+":", '', 1))
    if did_stash:
        do_print("Old state saved to: ~stash")
    utils._CURRENT_DATABASE.register_fa(args.file_key, '~last', True)
    utils._CURRENT_DATABASE.save()
    return [args.file_key, authoritative_key.replace(args.file_key+":", '', 1)]
