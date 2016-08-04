import os
import shutil
import csv

def reserve_name(base_name, existence_set):
    (filepath, filename) = os.path.split(base_name)
    if filename not in existence_set:
        return base_name
    index = 1
    (rootfile, extension) = os.path.splitext(filename)
    if len(extension):
        extension = '.'+extension
    current_name = '%s_%d%s' %(rootfile, index, extension)
    while current_name in existence_set:
        index+=1
        current_name = '%s_%d%s' %(rootfile, index, extension)
    return os.path.join(filepath, current_name)

def make_key(base_name, existence_set):
    index = 1
    current_name = '%s%d'%(base_name, index)
    while current_name in existence_set:
        index+=1
        current_name = '%s%d'%(base_name, index)
    return current_name

class Database:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.data_folders = set() #a set of used data folders
        self.primary_keys = {} #key: [None, data folder, set of data files] or alias: [authoriative key, None, None]
        self.state_keys = {} #key: [None, primary key, data file] or alias: [authoriative key, primary key, None]
        if not (os.path.isdir(self.base_dir) and
                    os.path.isfile(os.path.join(
                        self.base_dir,
                        '.db_config'
                    ))
                ):
            #initialize the database
            print("INIT")
            configwriter = open(os.path.join(
                self.base_dir,
                '.db_config'
            ), mode='w')
            configwriter.write('<QUICKSAVE DB>\n')
            configwriter.close()
        else:
            configreader = open(os.path.join(
                self.base_dir,
                '.db_config'
            ), mode='r')
            verification = configreader.readline().strip()
            if verification != "<QUICKSAVE DB>":
                raise ValueError("Unable to verify database")
            reader = csv.reader(configreader, delimiter='\t')
            for data in reader:
                if data[0] == 'PK': #primary key
                    data_folder = os.path.abspath(os.path.join(self.base_dir, data[2]))
                    self.primary_keys[data[1]] = [
                        None,
                        data_folder,
                        {item for item in data[3:]}
                    ]
                    self.data_folders.add(data_folder)
                elif data[0] == 'PA':
                    self.primary_keys[data[1]] = [
                        data[2],
                        None,
                        None
                    ]
                elif data[0] == 'SK':
                    self.state_keys[data[2]+":"+data[1]] = [
                        None,
                        data[2],
                        data[3]
                    ]
                elif data[0] == 'SA':
                    self.state_keys[data[2]+":"+data[1]] = [
                        data[2],
                        data[3],
                        None
                    ]
            configreader.close()
    def register_pk(self, filename):
        (filepath, root_name) = os.path.split(filename)
        canonical = ''.join(char for char in root_name if char.isalnum())
        data_folder = os.path.abspath(os.path.join(self.base_dir, reserve_name(canonical, self.data_folders)))
        os.makedirs(data_folder, exist_ok=True)
        self.data_folders.add(data_folder)
        key = make_key(canonical[:5]+"_PK", self.primary_keys)
        self.primary_keys[key] = [
            None,
            data_folder,
            set()
        ]
        return (key, data_folder)

    def register_pa(self, key, alias):
        key = self.resolve_key(key, True)
        if key in self.primary_keys and alias not in self.primary_keys:
            self.primary_keys[alias] = [
                key,
                None,
                None
            ]
            return True
        return False

    def register_sk(self, primarykey, filename):
        if primarykey not in self.primary_keys:
            sys.exit("The provided primary key does not exist in this database (%s)"%primarykey)
        primarykey = self.resolve_key(primarykey, True)
        canonical = ''.join(char for char in filename if char.isalnum() or char=='.')
        data_file = reserve_name(canonical, self.primary_keys[primarykey][2])
        key = make_key(canonical.replace('.','')[:5]+"_SK", {
            sk.replace(primarykey+':', '', 1)
            for sk in self.state_keys if self.state_keys[sk][1]==primarykey
        })
        shutil.copyfile(os.path.abspath(filename), os.path.join(self.primary_keys[primarykey][1], data_file))
        self.primary_keys[primarykey][2].add(data_file)
        self.state_keys[primarykey+":"+key] = [
            None,
            primarykey,
            data_file
        ]
        return (key, data_file)

    def register_sa(self, primarykey, key, alias):
        primarykey = self.resolve_key(primarykey, True)
        key = self.resolve_key(primarykey+":"+key, False).replace(primarykey+":", '', 1)
        if primarykey in self.primary_keys and primarykey+':'+key in self.state_keys and self.state_keys[primarykey+':'+key][1]==primarykey and primarykey+":"+alias not in self.state_keys:
            self.state_keys[primarykey+":"+alias] =  [
                primarykey+":"+key,
                primarykey,
                None
            ]
            return True
        return False

    def save(self):
        configwriter = open(os.path.join(
            self.base_dir,
            '.db_config'
        ), mode='w')
        configwriter.write('<QUICKSAVE DB>\n')
        writer = csv.writer(configwriter, delimiter='\t', lineterminator='\n')
        for key in self.primary_keys:
            entry = self.primary_keys[key]
            if entry[0]:
                writer.writerow(['PA', key, entry[0]])
            else:
                writer.writerow(['PK', key, os.path.relpath(entry[1], self.base_dir)]+[item for item in entry[2]])
        for key in self.state_keys:
            entry = self.state_keys[key]
            if entry[0]:
                writer.writerow(['SA', key, entry[0], entry[1]])
            else:
                writer.writerow(['SK', key, entry[1], entry[2]])
        configwriter.close()

    def resolve_key(self, alias, primary):
        if primary:
            # print("PRIME>>",self.primary_keys)
            current = alias
            while self.primary_keys[current][0]:
                current = self.primary_keys[current][0]
            return current
        else:
            # print("STATE>>",self.state_keys)
            current = alias
            while self.state_keys[current][0]:
                current = self.state_keys[current][0]
            return current
