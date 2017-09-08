import os
import sys
from .. import utils, qs_database
import argparse
import zipfile
import tarfile
import tempfile
import shutil
import csv
import subprocess

def add_file(archive, filename, arcname=None):
    if archive._fmt == 'zip':
        archive.write(filename, arcname)
    else:
        archive.add(filename, arcname)

def list_members(archive):
    if archive._fmt == 'zip':
        return archive.namelist()
    else:
        return archive.getnames()

def get_member(archive, member, staging_dir):
    archive.extract(member, staging_dir.name)
    return os.path.join(
        staging_dir.name,
        member
    )

def strip_key(key, keycode):
    return keycode.join(key.split(keycode)[:-1])+keycode


def command_export(args, do_print):
    utils.initdb(do_print)
    (root, ext) = os.path.splitext(args.output.name)
    if ext == '.zip':
        archive = zipfile.ZipFile(args.output, 'w')
        archive._fmt='zip'
    elif ext == '.gz' or ext == '.bz2':
        tar = os.path.splitext(root)[1]
        if tar != '.tar':
            raise TypeError('Unsupported output format: '+tar+ext)
        if ext == '.gz':
            archive = tarfile.open(
                mode='w|gz',
                fileobj=args.output
            )
            archive._fmt='tar'
        else:
            archive = tarfile.open(
                mode='w|bz2',
                fileobj=args.output
            )
            archive._fmt='tar'
    else:
        raise TypeError('Unsupported output format: '+ext)

    staging = tempfile.TemporaryDirectory()
    meta = open(staging.name+os.path.sep+'META', 'w')
    add_file(
        archive,
        os.path.join(
            utils._CURRENT_DATABASE.base_dir,
            '.db_config'
        ),
        'DATABASE'
    )
    excludes = {
        utils._CURRENT_DATABASE.resolve_key(key, True)
        for key in args.exclude
        if key in utils._CURRENT_DATABASE.file_keys
    }
    for (key, data) in utils._CURRENT_DATABASE.file_keys.items():
        if data[0] is None and key not in excludes:
            meta.write(
                '--KEY:\t%s\n' % key
            )
            for state in data[2]:
                add_file(
                    archive,
                    os.path.join(
                        utils._CURRENT_DATABASE.base_dir,
                        data[1],
                        state
                    ),
                    key+'.'+state
                )
    if not args.exclude_global:
        for (key, value) in utils._FLAGS.items():
            meta.write(
                '--CONFIG:\t%s\t%s\n' % (
                    key,
                    value
                )
            )
    meta.close()
    add_file(
        archive,
        os.path.join(staging.name, meta.name),
        'META'
    )
    staging.cleanup()
    archive.close()
    args.output.close()
    return args.output.name

def command_import(args, do_print):
    #args.input, args.database_path, args.mode
    from .command_init import command_init
    try:
        if args.database_path:
            args.database_path = utils.check_is_directory(os.path.abspath(args.database_path))
            command_init(args, do_print)
        utils.initdb(do_print)
    except SystemExit:
        args.database_path = os.path.join(os.path.expanduser('~'), '.quicksave_db')
        command_init(args, do_print)
        utils.initdb(do_print)

    (root, ext) = os.path.splitext(args.input.name)
    if ext == '.zip':
        archive = zipfile.ZipFile(args.input, 'r')
        archive._fmt='zip'
    elif ext == '.gz' or ext == '.bz2':
        tar = os.path.splitext(root)[1]
        if tar != '.tar':
            raise TypeError('Unsupported output format: '+tar+ext)
        if ext == '.gz':
            archive = tarfile.open(
                mode='r:gz',
                fileobj=args.input
            )
            archive._fmt='tar'
        else:
            archive = tarfile.open(
                mode='r:bz2',
                fileobj=args.input
            )
            archive._fmt='tar'
    else:
        raise TypeError('Unsupported output format: '+ext)
    members = list_members(archive)
    if 'DATABASE' not in members:
        sys.exit("This quicksave archive is corrupted")
    staging = tempfile.TemporaryDirectory()
    meta = open(get_member(archive, 'META', staging))
    filekeys = set()
    config = {}
    for line in meta:
        line = line.split('\t')
        typ = line[0]
        if typ == '--KEY:':
            filekeys.add(line[1].strip())
        elif typ == '--CONFIG:':
            config[line[1]] = line[2]
    # print("The following filekeys will be imported:", filekeys)
    db_path = get_member(archive, 'DATABASE', staging)
    shutil.move(
        db_path,
        os.path.join(
            staging.name,
            '.db_config'
        )
    )
    try:
        DB = qs_database.Database(staging.name)
    except ValueError as e:
        raise SystemExit("This quicksave database is corrupted") from e
    #modes:
    # overwrite/merge: imported keys merge to keys of the same name
    #   file key conflict updates foldername to existing foldername
    #   file alias conflict overrites existing alias
    #   state key/alias conflict overwrites existing (file conflicts use new file)
    # copy/rename: imported keys are renamed to avoid collision
    #   file key conflict renames key and folder to remain separate
    #   file alias conflict appends # to new aliases
    #   state key conflict increments the SK to avoid conflict
    #   state alias conflict appends # to new aliases
    # fail/keep: imported keys are dropped to avoid collision
    #   all conflicts skip the entity

    #maps for updating imported entries iff needed
    keynames = {}
    foldernames = {}
    filenames = {}
    output = {}
    #import file keys
    for (filekey, filedata) in DB.file_keys.items():
        if filedata[0] is None and filekey in filekeys:
            current_folders = {
                os.path.basename(folder)
                for folder in utils._CURRENT_DATABASE.data_folders
            }
            keynames[filekey] = filekey
            foldernames[filekey] = os.path.abspath(
                os.path.join(
                    utils._CURRENT_DATABASE.base_dir,
                    os.path.basename(filedata[1])
                )
            )
            if filekey in utils._CURRENT_DATABASE.file_keys:
                if args.mode == 'overwrite' or args.mode == 'merge':
                    foldernames[filekey] = utils._CURRENT_DATABASE.file_keys[filekey][1]
                elif args.mode == 'rename' or args.mode == 'copy':
                    keynames[filekey] = qs_database.make_key(
                        strip_key(filekey, '_FK'),
                        utils._CURRENT_DATABASE.file_keys
                    )
                    foldernames[filekey] = os.path.abspath(
                        os.path.join(
                            utils._CURRENT_DATABASE.base_dir,
                            qs_database.reserve_name(
                                os.path.basename(filedata[1]),
                                current_folders
                            )
                        )
                    )
                elif args.mode == 'fail' or args.mode == 'keep':
                    del keynames[filekey]
                    continue
            elif filedata[1] in current_folders:
                keynames[filekey] = filekey
                foldernames[filekey] = os.path.abspath(
                    os.path.join(
                        utils._CURRENT_DATABASE.base_dir,
                        qs_database.reserve_name(
                            filedata[1],
                            current_folders
                        )
                    )
                )
            output[filekey] = [keynames[filekey], foldernames[filekey]]
            # do_print('importing file', filekey)
            # do_print('filekey', filekey, '->', keynames[filekey])
            # do_print('folder', os.path.basename(filedata[1]), '->', os.path.basename(foldernames[filekey]))
            # do_print()
            os.makedirs(foldernames[filekey], exist_ok=True)
            utils._CURRENT_DATABASE.file_keys[keynames[filekey]] = [
                None,
                foldernames[filekey],
                set() if keynames[filekey] not in utils._CURRENT_DATABASE.file_keys
                else utils._CURRENT_DATABASE.file_keys[keynames[filekey]][2]
            ]

    #now import state keys
    for (statekey, statedata) in DB.state_keys.items():
        if statedata[0] is None and statedata[1]+'.'+statedata[2] in members:
            (parent, state) = statekey.split(':')
            if parent not in keynames:
                continue
            newkey = keynames[parent]+':'+state
            keynames[newkey] = newkey
            keynames[statekey] = newkey
            filenames[newkey] = statedata[2]
            filenames[statekey] = statedata[2]
            if newkey in utils._CURRENT_DATABASE.state_keys:
                if args.mode == 'overwrite' or args.mode == 'merge':
                    filenames[newkey] = utils._CURRENT_DATABASE.state_keys[newkey][2]
                    filenames[statekey] = filenames[newkey]
                elif args.mode == 'rename' or args.mode == 'copy':
                    keynames[newkey] = qs_database.make_key(
                        strip_key(newkey, '_SK'),
                        utils._CURRENT_DATABASE.state_keys
                    )
                    keynames[statekey] = keynames[newkey]
                    filenames[newkey] = qs_database.reserve_name(
                        statedata[2],
                        utils._CURRENT_DATABASE.file_keys[keynames[parent]][2]
                    )
                    filenames[statekey] = filenames[newkey]
                elif args.mode == 'keep' or args.mode == 'fail':
                    del keynames[statekey]
                    continue
            elif statedata[2] in utils._CURRENT_DATABASE.file_keys[keynames[parent]][2]:
                filenames[newkey] = qs_database.reserve_name(
                    statedata[2],
                    utils._CURRENT_DATABASE.file_keys[keynames[parent]][2]
                )
                filenames[statekey] = filenames[newkey]
            output[statekey] = [keynames[newkey], filenames[newkey]]
            # do_print('importing state', state)
            # do_print('statekey', statekey, '->', keynames[newkey])
            # do_print('file', statedata[2], '->', filenames[newkey])
            # do_print()
            utils._CURRENT_DATABASE.state_keys[keynames[newkey]] = [
                None,
                keynames[parent],
                filenames[newkey]
            ]
            shutil.copyfile(
                get_member(
                    archive,
                    statedata[1]+'.'+statedata[2],
                    staging
                ),
                os.path.join(
                    foldernames[parent],
                    filenames[newkey]
                )
            )
            utils._CURRENT_DATABASE.file_keys[keynames[parent]][2].add(
                filenames[newkey]
            )

    # Now copy file aliases
    for (filealias, filedata) in DB.file_keys.items():
        if filedata[0] is not None and filedata[0] in keynames:
            keynames[filealias] = filealias
            if filealias in utils._CURRENT_DATABASE.file_keys:
                if args.mode == 'rename' or args.mode == 'copy':
                    keynames[filealias] = qs_database.make_key(
                        filealias,
                        utils._CURRENT_DATABASE.file_keys
                    )
                elif args.mode == 'keep' or args.mode == 'fail':
                    continue
            output[filealias] = [keynames[filealias], keynames[filedata[0]]]
            # do_print('importing file alias', filealias)
            # do_print('alias', filealias, '->', keynames[filealias])
            # do_print('target', filedata[0], '->', keynames[filedata[0]])
            # do_print()
            utils._CURRENT_DATABASE.file_keys[keynames[filealias]] = [
                keynames[filedata[0]],
                None,
                None
            ]

    # Now copy state aliases
    for (statealias, statedata) in DB.state_keys.items():
        if statedata[0] is not None and statedata[0] in keynames:
            keynames[statealias] = statealias
            if statealias in utils._CURRENT_DATABASE.state_keys:
                if args.mode == 'rename' or args.mode == 'copy':
                    keynames[statealias] = qs_database.make_key(
                        statealias,
                        utils._CURRENT_DATABASE.state_keys
                    )
                elif args.mode == 'keep' or args.mode == 'fail':
                    continue
            output[statealias] = [keynames[statealias], keynames[statedata[0]]]
            # do_print('importing state alias', statealias)
            # do_print('alias', statealias, '->', keynames[statealias])
            # do_print('target', statedata[0], '->', keynames[statedata[0]])
            # do_print()
            utils._CURRENT_DATABASE.state_keys[keynames[statealias]] = [
                keynames[statedata[0]],
                ':'.join(keynames[statedata[0]].split(':')[:-1]),
                None
            ]

    # now import global config
    for (key, value) in config.items():
        utils._FLAGS[key] = value
    raw_writer = open(utils.configfile, mode='w')
    raw_writer.write(utils._CURRENT_DATABASE.base_dir+'\n')
    writer = csv.writer(raw_writer, delimiter='\t', lineterminator='\n')
    writer.writerows([[key,utils._FLAGS[key]] for key in utils._FLAGS])
    raw_writer.close()
    # now clean up
    utils._CURRENT_DATABASE.save()
    staging.cleanup()
    archive.close()
    devnull = open(os.devnull, 'w') if sys.version_info < (3,3) else subprocess.DEVNULL
    subprocess.call(
        'quicksave clean -d',
        shell=True,
        stdout=devnull,
        stderr=devnull
    )
    return output
