import sys
import csv
from .. import utils

def command_config(args, do_print):
    utils.initdb(do_print)
    if args.value: #set config
        if args._global:
            utils._FLAGS[args.key] = args.value
            raw_writer = open(utils.configfile, mode='w')
            raw_writer.write(utils._CURRENT_DATABASE.base_dir+'\n')
            writer = csv.writer(raw_writer, delimiter='\t', lineterminator='\n')
            writer.writerows([[key,utils._FLAGS[key]] for key in utils._FLAGS])
            raw_writer.close()
        else:
            utils._CURRENT_DATABASE.flags[args.key] = args.value
            utils._CURRENT_DATABASE.save()
    else: #read config
        if args.clear:
            if args._global:
                if args.key not in utils._FLAGS:
                    sys.exit("Unable to clear setting: The requested key (%s) is not set in the global configuration"%args.key)
                del utils._FLAGS[args.key]
                raw_writer = open(utils.configfile, mode='w')
                raw_writer.write(utils._CURRENT_DATABASE.base_dir+'\n')
                writer = csv.writer(raw_writer, delimiter='\t', lineterminator='\n')
                writer.writerows([[key,utils._FLAGS[key]] for key in utils._FLAGS])
                raw_writer.close()
            else:
                if args.key not in utils._CURRENT_DATABASE.flags:
                    sys.exit("Unable to clear setting: The requested key (%s) is not set in the database configuration"%args.key)
                del utils._CURRENT_DATABASE.flags[args.key]
                utils._CURRENT_DATABASE.save()
        else:
            do_print("Checking status of the requested key:", args.key)
            islocal = False
            do_print()
            if args.key in utils._CURRENT_DATABASE.flags:
                islocal=True
                do_print("* Database setting:", utils._CURRENT_DATABASE.flags[args.key])
            if args.key in utils._FLAGS:
                do_print(' ' if islocal else '*', 'Global setting:', utils._FLAGS[args.key])
    return [
        args.key,
        utils._FLAGS[args.key] if args.key in utils._FLAGS else None,
        utils._CURRENT_DATABASE.flags[args.key] if args.key in utils._CURRENT_DATABASE.flags else None
    ]
