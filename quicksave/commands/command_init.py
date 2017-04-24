import csv
from ..utils import configfile, _FLAGS

def command_init(args, _):
    raw_writer = open(configfile, mode='w')
    raw_writer.write(args.database_path+'\n')
    writer = csv.writer(raw_writer, delimiter='\t', lineterminator='\n')
    writer.writerows([[key,_FLAGS[key]] for key in _FLAGS])
    raw_writer.close()
    return args.database_path
