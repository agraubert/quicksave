import os
import shutil
import csv

def reserve_name(base_name, existence_set):
    (filepath, filename) = os.path.split(base_name)
    if filename not in existence_set:
        return base_name
    index = 1
    (rootfile, extension) = os.path.splitext(filename)
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
        self.file_keys = {} #key: [None, data folder, set of data files] or alias: [authoriative key, None, None]
        self.state_keys = {} #key: [None, file key, data file] or alias: [authoriative key, file key, None]
        self.flags = {}
        if not (os.path.isdir(self.base_dir) and
                    os.path.isfile(os.path.join(
                        self.base_dir,
                        '.db_config'
                    ))
                ):
            #initialize the database
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
                if data[0] == 'FK': #file key
                    data_folder = os.path.abspath(os.path.join(self.base_dir, data[2]))
                    self.file_keys[data[1]] = [
                        None,
                        data_folder,
                        {item for item in data[3:]}
                    ]
                    self.data_folders.add(data_folder)
                elif data[0] == 'FA':
                    self.file_keys[data[1]] = [
                        data[2],
                        None,
                        None
                    ]
                elif data[0] == 'SK':
                    self.state_keys[data[1]] = [
                        None,
                        data[2],
                        data[3]
                    ]
                elif data[0] == 'SA':
                    self.state_keys[data[1]] = [
                        data[2],
                        data[3],
                        None
                    ]
                elif data[0] == 'CONFIG':
                    self.flags[data[1]] = data[2]
            configreader.close()
    def register_fk(self, filename):
        (filepath, root_name) = os.path.split(filename)
        canonical = ''.join(char for char in root_name if char.isalnum())
        data_folder = os.path.abspath(os.path.join(self.base_dir, reserve_name(canonical, {os.path.basename(folder) for folder in self.data_folders})))
        os.makedirs(data_folder, exist_ok=True)
        self.data_folders.add(data_folder)
        key = make_key(canonical[:5]+"_FK", self.file_keys)
        self.file_keys[key] = [
            None,
            data_folder,
            set()
        ]
        return (key, data_folder)

    def register_fa(self, key, alias, overwrite=False):
        key = self.resolve_key(key, True)
        if key in self.file_keys and (overwrite or alias not in self.file_keys):
            self.file_keys[alias] = [
                key,
                None,
                None
            ]
            return True
        return False

    def register_sk(self, filekey, filepath, forcekey = False):
        if filekey not in self.file_keys:
            sys.exit("The provided file key does not exist in this database (%s)"%filekey)
        filename =os.path.basename(filepath)
        filekey = self.resolve_key(filekey, True)
        canonical = ''.join(char for char in filename if char.isalnum() or char=='.')
        data_file = reserve_name(canonical, self.file_keys[filekey][2])
        key = make_key(canonical.replace('.','')[:5]+"_SK", {
            sk.replace(filekey+':', '', 1)
            for sk in self.state_keys if self.state_keys[sk][1]==filekey
        })
        if forcekey:
            key = forcekey
        shutil.copyfile(os.path.abspath(filepath), os.path.join(self.file_keys[filekey][1], data_file))
        self.file_keys[filekey][2].add(data_file)
        self.state_keys[filekey+":"+key] = [
            None,
            filekey,
            data_file
        ]
        return (key, data_file)

    def register_sa(self, filekey, key, alias, overwrite=False):
        filekey = self.resolve_key(filekey, True)
        key = self.resolve_key(filekey+":"+key, False).replace(filekey+":", '', 1)
        if filekey in self.file_keys and filekey+':'+key in self.state_keys and self.state_keys[filekey+':'+key][1]==filekey and (overwrite or filekey+":"+alias not in self.state_keys):
            self.state_keys[filekey+":"+alias] =  [
                filekey+":"+key,
                filekey,
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
        for key in self.file_keys:
            entry = self.file_keys[key]
            if entry[0]:
                writer.writerow(['FA', key, entry[0]])
            else:
                writer.writerow(['FK', key, os.path.relpath(entry[1], self.base_dir)]+[item for item in entry[2]])
        for key in self.state_keys:
            entry = self.state_keys[key]
            if entry[0]:
                writer.writerow(['SA', key, entry[0], entry[1]])
            else:
                writer.writerow(['SK', key, entry[1], entry[2]])
        for key in self.flags:
            writer.writerow(['CONFIG', key, self.flags[key]])
        configwriter.close()

    def resolve_key(self, alias, isfile):
        if isfile:
            # print("PRIME>>",self.file_keys)
            current = alias
            while self.file_keys[current][0]:
                current = self.file_keys[current][0]
            return current
        else:
            # print("STATE>>",self.state_keys)
            current = alias
            while self.state_keys[current][0]:
                current = self.state_keys[current][0]
            return current
