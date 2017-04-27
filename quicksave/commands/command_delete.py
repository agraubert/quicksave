import sys
import os
from shutil import rmtree
from .. import utils

def command_delete(args, do_print):
    utils.initdb(do_print)
    didtrash = False
    args.save = args.save and utils._checkflag('delete.trash', '1')=='1'
    if not args.filekey:
        #when deleting a file key:
        #   - Remove the data folder for the current ~trash entry
        #   - Remove any file aliases to ~trash
        #   - Remove all state keys and aliases under ~trash
        #   - Unregister all file aliases
        #   - Update all state keys and aliases to point to ~trash:<key>
        if args.target not in utils._CURRENT_DATABASE.file_keys:
            sys.exit("Unable to delete key: The provided file key does not exist in this database (%s)"%args.target)
        if utils._CURRENT_DATABASE.file_keys[args.target][0]:
            sys.exit("Unable to delete key: The provided file key was an alias.  Use '$ quicksave alias -d <file alias>' to delete")
        if args.target == '~trash':
            sys.exit("Unable to directly delete ~trash keys.  Use '$ quicksave clean -t' to clean all ~trash keys")
        if args.save and '~trash' in utils._CURRENT_DATABASE.file_keys:
            rmtree(os.path.join(
                os.path.abspath(utils._CURRENT_DATABASE.base_dir),
                utils._CURRENT_DATABASE.file_keys['~trash'][1]
            ))
            if args.clean_aliases:
                for key in [key for key in utils._CURRENT_DATABASE.file_keys if utils._CURRENT_DATABASE.file_keys[key][0]=='~trash']:
                    del utils._CURRENT_DATABASE.file_keys[key]
            for key in [key for key in utils._CURRENT_DATABASE.state_keys if key.startswith('~trash')]:
                del utils._CURRENT_DATABASE.state_keys[key]
            del utils._CURRENT_DATABASE.file_keys['~trash']
        for key in [key for key in utils._CURRENT_DATABASE.file_keys if utils._CURRENT_DATABASE.file_keys[key][0]==args.target]:
            del utils._CURRENT_DATABASE.file_keys[key]
        for key in [key for key in utils._CURRENT_DATABASE.state_keys if key.startswith(args.target+":")]:
            if args.save:
                entry = [item for item in utils._CURRENT_DATABASE.state_keys[key]]
                entry[1] = entry[1].replace(args.target, '~trash', 1)
                if entry[0]:
                    entry[0] = entry[0].replace(args.target, '~trash', 1)
                utils._CURRENT_DATABASE.state_keys[key.replace(args.target, '~trash', 1)] = [item for item in entry]
            del utils._CURRENT_DATABASE.state_keys[key]
        if args.save:
            didtrash = True
            utils._CURRENT_DATABASE.file_keys['~trash'] = [item for item in utils._CURRENT_DATABASE.file_keys[args.target]]
        else:
            rmtree(os.path.join(
                os.path.abspath(utils._CURRENT_DATABASE.base_dir),
                utils._CURRENT_DATABASE.file_keys[args.target][1]
            ))
        del utils._CURRENT_DATABASE.file_keys[args.target]
        utils._CURRENT_DATABASE.save()
        do_print("Deleted file key: %s"%args.target)
        if didtrash:
            do_print("File data saved to ~trash")

    else:
        #when deleting a state key:
        #   - Remove the datafile (and entry in the parent file key) for the current ~trash entry
        #   - Remove any state aliases to ~trash (-c)
        #   - Unregister all state aliases
        if args.filekey not in utils._CURRENT_DATABASE.file_keys:
            sys.exit("Unable to delete key: The provided file key does not exist in this database (%s)"%args.filekey)
        authoritative_key = utils._CURRENT_DATABASE.resolve_key(args.filekey, True)
        if authoritative_key+":"+args.target not in utils._CURRENT_DATABASE.state_keys:
            sys.exit("Unable to delete key: The provided state key does not exist in this database (%s)"%args.target)
        if utils._CURRENT_DATABASE.state_keys[authoritative_key+":"+args.target][0]:
            sys.exit("Unable to delete key: The provided state key was an alias.  Use '$ quicksave alias -d <state alias> <file key>' to delete a state alias")
        if args.target == '~trash':
            sys.exit("Unable to directly delete ~trash keys.  Use '$ quicksave clean -t' to clean all ~trash keys")
        if args.save and authoritative_key+":~trash" in utils._CURRENT_DATABASE.state_keys:
            os.remove(os.path.join(
                os.path.abspath(utils._CURRENT_DATABASE.base_dir),
                utils._CURRENT_DATABASE.file_keys[authoritative_key][1],
                utils._CURRENT_DATABASE.state_keys[authoritative_key+":~trash"][2]
            ))
            utils._CURRENT_DATABASE.file_keys[authoritative_key][2].remove(
                utils._CURRENT_DATABASE.state_keys[authoritative_key+":~trash"][2]
            )
            if args.clean_aliases:
                for key in [key for key in utils._CURRENT_DATABASE.state_keys if utils._CURRENT_DATABASE.state_keys[key][0]==authoritative_key+":~trash"]:
                    del utils._CURRENT_DATABASE.state_keys[key]
            del utils._CURRENT_DATABASE.state_keys[authoritative_key+":~trash"]
        for key in [key for key in utils._CURRENT_DATABASE.state_keys if utils._CURRENT_DATABASE.state_keys[key][0]==authoritative_key+":"+args.target]:
            del utils._CURRENT_DATABASE.state_keys[key]
        if args.save:
            didtrash = True
            utils._CURRENT_DATABASE.state_keys[authoritative_key+":~trash"] = [item for item in utils._CURRENT_DATABASE.state_keys[authoritative_key+":"+args.target]]
        else:
            os.remove(os.path.join(
                os.path.abspath(utils._CURRENT_DATABASE.base_dir),
                utils._CURRENT_DATABASE.file_keys[authoritative_key][1],
                utils._CURRENT_DATABASE.state_keys[authoritative_key+":"+args.target][2]
            ))
            utils._CURRENT_DATABASE.file_keys[authoritative_key][2].remove(
                utils._CURRENT_DATABASE.state_keys[authoritative_key+":"+args.target][2]
            )
        del utils._CURRENT_DATABASE.state_keys[authoritative_key+":"+args.target]
        utils._CURRENT_DATABASE.register_fa(authoritative_key, '~last', True)
        utils._CURRENT_DATABASE.save()
        do_print("Deleted state key: %s (File key: %s)"%(args.target, authoritative_key))
        if didtrash:
            do_print("State data saved to ~trash")
