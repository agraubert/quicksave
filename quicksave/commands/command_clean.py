import os
import sys
from shutil import rmtree
from .. import utils

def command_clean(args, do_print):
    utils.initdb(do_print)
    didop = False
    msg = ''
    result = {}
    if args.states or args.clean_all:
        didop = True
        keys = []
        for key in list(utils._CURRENT_DATABASE.state_keys):
            if utils._CURRENT_DATABASE.state_keys[key][1] not in utils._CURRENT_DATABASE.file_keys:
                keys.append(""+key)
                del utils._CURRENT_DATABASE.state_keys[key]
        if len(keys):
            msg += "Removed the following %d orphaned state keys and aliases: %s\n"%(
                len(keys),
                str([key for key in keys])
            )
            result['states'] = keys
    if args.aliases or args.clean_all:
        didop = True
        state_keys = []
        file_keys = []
        for key in [key for key in utils._CURRENT_DATABASE.file_keys if utils._CURRENT_DATABASE.file_keys[key][0]]:
            if utils._CURRENT_DATABASE.file_keys[key][0] not in utils._CURRENT_DATABASE.file_keys:
                file_keys.append(""+key)
                del utils._CURRENT_DATABASE.file_keys[key]
        for key in [key for key in utils._CURRENT_DATABASE.state_keys if utils._CURRENT_DATABASE.state_keys[key][0]]:
            if utils._CURRENT_DATABASE.state_keys[key][0] not in utils._CURRENT_DATABASE.state_keys:
                state_keys.append(""+key)
                del utils._CURRENT_DATABASE.state_keys[key]
        if len(file_keys):
            msg += "Removed the following %d invalid file aliases: %s\n"%(
                len(file_keys),
                str([key for key in file_keys])
            )
            result['file_aliases'] = file_keys
        if len(state_keys):
            msg += "Removed the following %d invalid state aliases: %s\n"%(
                len(state_keys),
                str([key for key in state_keys])
            )
            result['state_aliases'] = state_keys
    if args.rebuild_file_index or args.clean_all:
        didop = True
        rebuilt = 0
        for key in [key for key in utils._CURRENT_DATABASE.file_keys if not utils._CURRENT_DATABASE.file_keys[key][0]]:
            old_list = utils._CURRENT_DATABASE.file_keys[key][2]
            new_list = set()
            for statekey in [statekey for statekey in utils._CURRENT_DATABASE.state_keys if utils._CURRENT_DATABASE.state_keys[statekey][1]==key]:
                state = utils._CURRENT_DATABASE.state_keys[statekey]
                if state[2] not in new_list:
                    new_list.add(state[2])
            if None in new_list:
                new_list.remove(None)
            if len(old_list^new_list):
                rebuilt+=1
                utils._CURRENT_DATABASE.file_keys[key][2] = {item for item in new_list}
        if rebuilt:
            msg += "Rebuilt %d file keys with out-of-date indexes\n"%rebuilt
            result['rebuilt'] = rebuilt
    if args.walk_database or args.clean_all:
        didop=True
        prune_folders = []
        prune_files = []
        prune_filekeys = []
        prune_statekeys = []
        folder_map = {
            key: utils._CURRENT_DATABASE.file_keys[key][1]
            for key in utils._CURRENT_DATABASE.file_keys
            if not utils._CURRENT_DATABASE.file_keys[key][0]
        }
        manifest = {entry:{} for entry in utils._CURRENT_DATABASE.data_folders}

        for key in utils._CURRENT_DATABASE.state_keys:
            entry = [item for item in utils._CURRENT_DATABASE.state_keys[key]]
            if not entry[0]:
                manifest[folder_map[entry[1]]][entry[2]] = [key, False]
        for path in os.walk(utils._CURRENT_DATABASE.base_dir):
            if path[0] == utils._CURRENT_DATABASE.base_dir:
                #Folders phase
                for target in set(path[1])-{os.path.basename(folder) for folder in utils._CURRENT_DATABASE.data_folders}:
                    rmtree(os.path.join(
                        os.path.abspath(utils._CURRENT_DATABASE.base_dir),
                        os.path.basename(target)
                    ))
                    prune_folders.append(''+target)
            else:
                for target in path[2]:
                    if path[0] in manifest and target in manifest[path[0]]:
                        manifest[path[0]][target][1] = True
                    else:
                        full_filepath = os.path.join(
                            path[0],
                            target
                        )
                        if os.path.isfile(full_filepath):
                            os.remove(full_filepath)
                        prune_files.append(os.path.join(
                            os.path.relpath(path[0], os.path.abspath(utils._CURRENT_DATABASE.base_dir)),
                            target
                        ))
        #filekeys phase
        for key in folder_map:
            if not os.path.isdir(os.path.join(
                os.path.abspath(utils._CURRENT_DATABASE.base_dir),
                folder_map[key]
            )):
                for alias in [alias for alias in utils._CURRENT_DATABASE.file_keys if utils._CURRENT_DATABASE.file_keys[alias][0]==key]:
                    del utils._CURRENT_DATABASE.file_keys[alias]
                for statekey in [statekey for statekey in utils._CURRENT_DATABASE.state_keys if utils._CURRENT_DATABASE.state_keys[statekey][1]==key]:
                    del utils._CURRENT_DATABASE.state_keys[statekey]
                del utils._CURRENT_DATABASE.file_keys[key]
                prune_filekeys.append(''+key)
        #statekeys phase
        for entry in [manifest[folder][datafile] for folder in manifest for datafile in manifest[folder]]:
            if entry[0] in utils._CURRENT_DATABASE.state_keys and not entry[1]:
                del utils._CURRENT_DATABASE.state_keys[entry[0]]
                prune_statekeys.append(''+entry[0])
                for alias in [alias for alias in utils._CURRENT_DATABASE.state_keys if utils._CURRENT_DATABASE.state_keys[alias][0]==entry[0]]:
                    del utils._CURRENT_DATABASE.state_keys[alias]
        if len(prune_folders):
            msg += "Removed the following %d unused database folders:%s\n"%(len(prune_folders), str(prune_folders))
            result['prune_folders'] = prune_folders
        if len(prune_files):
            msg += "Removed the following %d orphaned files in the database:%s\n"%(len(prune_files), str(prune_files))
            result['prune_files'] = prune_files
        if len(prune_filekeys):
            msg += "Removed the following %d file keys with missing data folders:%s\n"%(len(prune_filekeys), str(prune_filekeys))
            result['prune_filekeys'] = prune_filekeys
        if len(prune_statekeys):
            msg += "Removed the following %d state keys with missing data files:%s\n"%(len(prune_statekeys), str(prune_statekeys))
            result['prune_statekeys'] = prune_statekeys
    if args.trash or args.clean_all:
        didop = True
        statekeys = 0
        statealiases = 0
        trashaliases = 0
        for key in [key for key in utils._CURRENT_DATABASE.file_keys if utils._CURRENT_DATABASE.file_keys[key][0] == '~trash']:
            trashaliases +=1
            del utils._CURRENT_DATABASE.file_keys[key]
        for key in [key for key in utils._CURRENT_DATABASE.state_keys]:
            if key.startswith("~trash:"): #this state key belongs to the trash file key
                if not utils._CURRENT_DATABASE.state_keys[key][0]:
                    statekeys+=1
                else:
                    statealiases+=1
                del utils._CURRENT_DATABASE.state_keys[key]
            elif key.endswith(":~trash"): #this is a trash state key, but it belongs to a regular key
                datafile = utils._CURRENT_DATABASE.state_keys[key][2]
                utils._CURRENT_DATABASE.file_keys[utils._CURRENT_DATABASE.state_keys[key][1]][2].remove(datafile)
                os.remove(os.path.join(
                    os.path.abspath(utils._CURRENT_DATABASE.base_dir),
                    utils._CURRENT_DATABASE.file_keys[utils._CURRENT_DATABASE.state_keys[key][1]][1],
                    datafile
                ))
                statekeys+=1
                del utils._CURRENT_DATABASE.state_keys[key]
            else: #alias to a trash state key
                entry = [item for item in utils._CURRENT_DATABASE.state_keys[key]]
                if entry[0] and entry[0].count('~trash'):
                    statealiases+=1
                    del utils._CURRENT_DATABASE.state_keys[key]
        if statekeys+statealiases:
            msg += "Cleaned %d ~trash state keys and %d aliases\n"%(statekeys, statealiases)
            result['trash_state'] = [statekeys, statealiases]
        if '~trash' in utils._CURRENT_DATABASE.file_keys:
            rmtree(os.path.join(
                os.path.abspath(utils._CURRENT_DATABASE.base_dir),
                utils._CURRENT_DATABASE.file_keys['~trash'][1]
            ))
            del utils._CURRENT_DATABASE.file_keys['~trash']
            msg+="Cleaned the ~trash file key and %d aliases.\n"%trashaliases
            result['trash_file'] = trashaliases
    if args.deduplicate or args.clean_all:
        didop = True
        duplicates = {} #file key -> hash -> original state key
        forward = {} #duplicate state key -> original state key
        for key in sorted([key for key in utils._CURRENT_DATABASE.state_keys if not utils._CURRENT_DATABASE.state_keys[key][0]]):
            entry = [item for item in utils._CURRENT_DATABASE.state_keys[key]]
            reader = open(os.path.join(
                os.path.abspath(utils._CURRENT_DATABASE.base_dir),
                utils._CURRENT_DATABASE.file_keys[entry[1]][1],
                entry[2]
            ), mode='rb')
            hashsum = utils.gethash(reader)
            reader.close()
            if entry[1] not in duplicates:
                duplicates[entry[1]] = {}
            if hashsum not in duplicates[entry[1]]:
                duplicates[entry[1]][hashsum] = ''+key
            else:
                forward[''+key] = duplicates[entry[1]][hashsum]
                entry = [item for item in utils._CURRENT_DATABASE.state_keys[key]]
                os.remove(os.path.join(
                    os.path.abspath(utils._CURRENT_DATABASE.base_dir),
                    utils._CURRENT_DATABASE.file_keys[entry[1]][1],
                    entry[2]
                ))
                utils._CURRENT_DATABASE.file_keys[entry[1]][2].remove(entry[2])
                del utils._CURRENT_DATABASE.state_keys[key]
        didforward = 0
        for key in [key for key in utils._CURRENT_DATABASE.state_keys if utils._CURRENT_DATABASE.state_keys[key][0]]:
            if utils._CURRENT_DATABASE.state_keys[key][0] in forward: #this is a state alias which should be forwarded
                utils._CURRENT_DATABASE.state_keys[key][0] = forward[utils._CURRENT_DATABASE.state_keys[key][0]]
                didforward += 1
        for filekey in duplicates:
            for hashkey in duplicates[filekey]:
                if filekey+":"+hashkey not in utils._CURRENT_DATABASE.state_keys:
                    utils._CURRENT_DATABASE.register_sa(filekey, duplicates[filekey][hashkey].replace(filekey+":", '', 1), hashkey)
                if filekey+":"+hashkey[:7] not in utils._CURRENT_DATABASE.state_keys:
                    utils._CURRENT_DATABASE.register_sa(filekey, duplicates[filekey][hashkey].replace(filekey+":", '', 1), hashkey[:7])
        if len(forward):
            msg += "Removed the following %d duplicate state keys:%s and forwarded %d aliases\n"%(
                len(forward),
                str([key for key in forward]),
                didforward
            )
            result['deduplicate'] = forward
    if not didop:
        sys.exit("No action taken.  Set at least one of the flags when using '$ quicksave clean'")
    utils._CURRENT_DATABASE.save()
    if len(msg):
        do_print(msg[:-1])
    else:
        do_print("Nothing to clean")
    return result
