import sys
import os
from .. import utils
from ..qs_database import make_key

def command_recover(args, do_print):
    utils.initdb(do_print)
    if '~trash' not in utils._CURRENT_DATABASE.file_keys:
        sys.exit("Unable to recover: There is no data stored in the ~trash file key")
    entry = [item for item in utils._CURRENT_DATABASE.file_keys['~trash']]
    filekey = make_key(os.path.basename(entry[1])[:5]+"_FK", utils._CURRENT_DATABASE.file_keys)
    utils._CURRENT_DATABASE.file_keys[filekey] = [item for item in entry]
    aliases = []
    for key in [key for key in utils._CURRENT_DATABASE.file_keys if utils._CURRENT_DATABASE.file_keys[key][0]=='~trash']:
        utils._CURRENT_DATABASE.file_keys[key][0] = filekey
        aliases.append(key)
    if len(args.aliases):
        for user_alias in args.aliases:
            if user_alias in utils._SPECIAL_FILE:
                sys.exit("Unable to recover: Cannot create a file alias which overwrites a reserved file key (%s)"%user_alias)
            if utils._CURRENT_DATABASE.register_fa(filekey, user_alias):
                aliases.append(''+user_alias)
        if not len(aliases):
            sys.exit("Unable to recover: None of the provided aliases were available")
    for key in [key for key in utils._CURRENT_DATABASE.state_keys if key.startswith("~trash:")]:
        entry = [item for item in utils._CURRENT_DATABASE.state_keys[key]]
        entry[1] = entry[1].replace('~trash', filekey, 1)
        if entry[0]:
            entry[0] = entry[0].replace('~trash', filekey, 1)
        utils._CURRENT_DATABASE.state_keys[key.replace('~trash', filekey, 1)] = [item for item in entry]
        del utils._CURRENT_DATABASE.state_keys[key]
    del utils._CURRENT_DATABASE.file_keys['~trash']
    utils._CURRENT_DATABASE.register_fa(filekey, '~last', True)
    utils._CURRENT_DATABASE.save()
    do_print("Recovered file key:", filekey)
    do_print("Aliases for this file key:", aliases)
