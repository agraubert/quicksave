import csv
import os
from ..utils import configfile

def command_init(args, _):
    flags = {}
    if os.path.isfile(configfile):
        raw_reader = open(configfile)
        next(raw_reader)
        reader = csv.reader(raw_reader, delimiter='\t')
        for line in reader:
            flags[line[0]] = line[1]
        raw_reader.close()
    raw_writer = open(configfile, mode='w')
    raw_writer.write(args.database_path+'\n')
    writer = csv.writer(raw_writer, delimiter='\t', lineterminator='\n')
    writer.writerows([[key, flags[key]] for key in flags])
    raw_writer.close()
    return args.database_path
