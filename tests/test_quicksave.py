import unittest
import tempfile
import sys
import os
from py_compile import compile
from shutil import copyfile, rmtree
import random
from  hashlib import sha256
import warnings
from filecmp import cmp

DATA = {}
_do_print = lambda *args, **kwargs: None

def random_string(upper=125):
    return "".join([chr(random.randint(65, upper)) for _ in range(20)])

if "TemporaryDirectory" not in dir(tempfile):
    def simple_tempdir():
        output = lambda :None
        output.name = tempfile.mkdtemp()
        output.cleanup = lambda :rmtree(output.name)
        return output
    tempfile.TemporaryDirectory = simple_tempdir

class test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        random.seed()
        basepath = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        cls.test_directory = tempfile.TemporaryDirectory()
        cls.db_directory = tempfile.TemporaryDirectory()
        cls.script_path = os.path.join(
            basepath,
            'quicksave',
            '__main__.py'
        )
        from quicksave.utils import configfile
        if os.path.isfile(configfile):
            copyfile(configfile, 'config_backup')
        warnings.simplefilter('ignore', ResourceWarning)

    @classmethod
    def tearDownClass(cls):
        from quicksave.utils import configfile
        if os.path.isfile('config_backup'):
            copyfile('config_backup', configfile)
            os.remove("config_backup")
        cls.test_directory.cleanup()
        cls.db_directory.cleanup()
        warnings.resetwarnings()

    def test_compilation(self):
        compiled_path = compile(self.script_path)
        self.assertTrue(compiled_path)

    def test_a_init(self):
        from quicksave.__main__ import main

        #INIT
        self.assertEqual(main([
            '--return-result',
            'init',
            self.db_directory.name
        ]), self.db_directory.name)
        self.assertEqual(main([
            '--return-result',
            'show'
        ]), self.db_directory.name)

    def test_b_register(self):
        from quicksave.__main__ import main

        #REGISTER
        sourcefile = open(os.path.join(self.test_directory.name, random_string(90)), 'w+b')
        DATA['register-sourcefile'] = sourcefile.name
        DATA['register-content'] = os.urandom(4096)
        sourcefile.write(DATA['register-content'])
        sourcefile.close()
        f_aliases = [random_string() for _ in range(random.randint(0, 5))]+['__test_alias__']
        s_aliases = [random_string() for _ in range(random.randint(0, 5))]+['__test_state_alias__']
        command = ['--return-result', 'register', sourcefile.name] + [alias for alias in s_aliases]
        for i in range(len(f_aliases)):
            command+= ['-a', f_aliases[i]]
        result = main(command)
        self.assertTrue(result[0], os.path.basename(sourcefile.name)[:5]+"_FK1")
        self.assertTrue(len(result[1]), len(f_aliases)+2)
        for alias in f_aliases:
            self.assertTrue(alias in result[1])
        self.assertTrue(sourcefile.name in result[1])
        self.assertTrue(os.path.basename(sourcefile.name) in result[1])
        self.assertTrue(result[2], os.path.basename(sourcefile.name)[:5]+"_SK1")
        self.assertTrue(len(result[3]), len(s_aliases)+1)
        for alias in s_aliases:
            self.assertTrue(alias in result[3])
        hashkey = sha256(DATA['register-content']).hexdigest()
        self.assertTrue(hashkey[:7] in result[3])
        with self.assertRaises(SystemExit):
            main(command)

        DATA['register-filekey'] = result[0]
        DATA['register-statekey'] = result[2]
        DATA['register-hashkey'] = hashkey
        main(['--return-result', 'register', sourcefile.name] + [alias for alias in s_aliases]+['--ignore-filepath'])

    def test_c_save(self):
        from quicksave.__main__ import main

        #SAVE
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'save',
                DATA['register-sourcefile']
            ])
        copyfile(DATA['register-sourcefile'], os.path.join(self.test_directory.name, '_blerg_'))
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'save',
                os.path.join(self.test_directory.name, '_blerg_'),
                '-k',
                DATA['register-filekey']
            ])
        sourcefile = open(os.path.join(self.test_directory.name, random_string(90)), 'w+b')
        DATA['save-sourcefile'] = sourcefile.name
        DATA['save-content'] = os.urandom(4096)
        sourcefile.write(DATA['save-content'])
        sourcefile.close()
        aliases = [random_string() for _ in range(random.randint(0, 5))]
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'save',
                sourcefile.name
            ])
        command = ['--return-result', 'save', sourcefile.name] + aliases + ['-k', DATA['register-filekey']]
        result = main(command)
        self.assertEqual(result[0], DATA['register-filekey'])
        self.assertEqual(result[1], os.path.basename(sourcefile.name)[:5]+"_SK1")
        self.assertEqual(len(result[2]), len(aliases)+2)
        for alias in aliases:
            self.assertTrue(alias in result[2])
        self.assertTrue(os.path.basename(sourcefile.name) in result[2])
        hashkey = sha256(DATA['save-content']).hexdigest()
        self.assertTrue(hashkey[:7] in result[2])
        DATA['save-hashkey'] = hashkey
        DATA['save-statekey'] = result[1]

    def test_d_revert(self):
        from quicksave.__main__ import main

        sourcefile = open(os.path.join(self.test_directory.name, random_string(90)), 'w+b')
        DATA['revert-sourcefile'] = sourcefile.name
        DATA['revert-content'] = os.urandom(4096)
        sourcefile.write(DATA['revert-content'])
        sourcefile.close()
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'revert',
                sourcefile.name,
                DATA['save-statekey']
            ])
        result = main([
            '--return-result',
            'revert',
            sourcefile.name,
            DATA['register-hashkey'],
            '-k',
            DATA['register-filekey']
        ])
        self.assertEqual(result[0], DATA['register-filekey'])
        self.assertEqual(result[1], DATA['register-statekey'])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'revert',
                sourcefile.name,
                DATA['register-statekey'],
                '-k',
                DATA['register-filekey']
            ])
        self.assertTrue(cmp(
            sourcefile.name,
            DATA['register-sourcefile']
        ))
        main([
            '--return-result',
            'revert',
            sourcefile.name,
            '~stash',
            '-k',
            DATA['register-filekey']
        ])
        reader = open(sourcefile.name, mode='rb')
        self.assertEqual(reader.read(2048), DATA['revert-content'][:2048])
        self.assertEqual(reader.read(), DATA['revert-content'][2048:])
        reader.close()
        main([
            '--return-result',
            'revert',
            sourcefile.name,
            DATA['save-statekey'],
            '-k',
            DATA['register-filekey']
        ])
        self.assertTrue(cmp(
            sourcefile.name,
            DATA['save-sourcefile']
        ))
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'revert',
                sourcefile.name,
                DATA['save-statekey'],
                '-k',
                DATA['register-filekey']
            ])
        main([
            '--return-result',
            'revert',
            sourcefile.name,
            '~stash',
            '-k',
            DATA['register-filekey']
        ])
        with open(sourcefile.name, 'rb') as reader:
            current = sha256(reader.read()).hexdigest()
        desired = sha256(DATA['revert-content']).hexdigest()
        self.assertEqual(current, desired)
        initial = main([
            '--return-result',
            'lookup',
            DATA['register-filekey'],
            '~stash'
        ])
        main([
            '--return-result',
            'revert',
            sourcefile.name,
            DATA['save-statekey'],
            '-k',
            DATA['register-filekey'],
            '--no-stash'
        ])
        final = main([
            '--return-result',
            'lookup',
            DATA['register-filekey'],
            '~stash'
        ])
        self.assertEqual(initial, final)
        main([
            '--return-result',
            'revert',
            sourcefile.name,
            '~stash',
            '-k',
            DATA['register-filekey']
        ])

    def test_e_alias(self):
        from quicksave.__main__ import main

        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'alias',
                'blarg'
            ])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'alias',
                '-d',
                'Probably not a real key though'
            ])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'alias',
                '-d',
                DATA['register-filekey']
            ])
        result = main([
            '--return-result',
            'alias',
            '-d',
            '__test_alias__'
        ])
        self.assertEqual(1, len(result))
        self.assertEqual(result[0], '__test_alias__')
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'alias',
                '_link',
                'Probably not a real key though'
            ])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'alias',
                DATA['register-filekey'],
                DATA['register-filekey']
            ])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'alias',
                '~trash',
                DATA['register-filekey']
            ])
        new_alias = random_string()
        result = main([
            '--return-result',
            'alias',
            new_alias,
            '~last'
        ])
        DATA['new-file-alias'] = ''+new_alias
        self.assertEqual(2, len(result))
        self.assertEqual(result[0], new_alias)
        self.assertEqual(result[1], DATA['register-filekey'])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'alias',
                '-d',
                '_link',
                'Probably not a real key though'
            ])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'alias',
                '-d',
                '_link',
                'Probably not a real key though'
                'extraneous argument'
            ])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'alias',
                '-d',
                'Probably not a real key though',
                DATA['register-filekey']
            ])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'alias',
                '-d',
                '~stash',
                DATA['register-filekey']
            ])
        result = main([
            '--return-result',
            'alias',
            '-d',
            '__test_state_alias__',
            DATA['register-filekey']
        ])
        self.assertEqual(2, len(result))
        self.assertEqual(result[0], '__test_state_alias__')
        self.assertEqual(result[1], DATA['register-filekey'])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'alias',
                '_link',
                '_target',
                'Probably not a real key though'
            ])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'alias',
                '_link',
                '_target',
                DATA['register-filekey']
            ])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'alias',
                '~stash',
                DATA['register-statekey'],
                DATA['register-filekey']
            ])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'alias',
                DATA['save-statekey'],
                DATA['register-statekey'],
                DATA['register-filekey']
            ])
        new_alias = random_string()
        result = main([
            '--return-result',
            'alias',
            new_alias,
            DATA['save-statekey'],
            DATA['register-filekey']
        ])
        DATA['new-state-alias'] = ''+new_alias
        self.assertEqual(3, len(result))
        self.assertEqual(result[0], new_alias)
        self.assertEqual(result[1], DATA['save-statekey'])
        self.assertEqual(result[2], DATA['register-filekey'])

    def test_f_list(self):
        from quicksave.__main__ import main

        result = main([
            '--return-result',
            'list'
        ])
        self.assertEqual(2, len(result))
        self.assertTrue(DATA['register-filekey'] in result)
        DATA['temp-filekey'] = result[(1+result.index(DATA['register-filekey']))%2]

        result = main([
            '--return-result',
            'list',
            '-a'
        ])
        self.assertGreater(len(result), 2)
        DATA['all-file-handles'] = [item for item in result]

        result = main([
            '--return-result',
            'list',
            DATA['register-filekey']
        ])
        self.assertEqual(3, len(result))
        self.assertTrue(DATA['register-statekey'] in result)
        self.assertTrue(DATA['save-statekey'] in result)
        self.assertTrue("~stash" in result)

        result = main([
            '--return-result',
            'list',
            DATA['register-filekey'],
            '-a'
        ])
        self.assertGreater(len(result), 3)
        DATA['all-state-handles'] = [item for item in result]

        register_filekey_handles = set(main([
            '--return-result',
            'list',
            '-t',
            DATA['register-filekey']
        ]))
        temp_filekey_handles = set(main([
            '--return-result',
            'list',
            '-t',
            DATA['temp-filekey']
        ]))
        self.assertSetEqual(set(DATA['all-file-handles']), register_filekey_handles|temp_filekey_handles)
        all_state_handles = set()
        for key in main(['--return-result', 'list', DATA['register-filekey']]):
            all_state_handles|=set(main([
                '--return-result',
                'list',
                DATA['register-filekey'],
                '-t',
                key
            ]))
        self.assertSetEqual(set(DATA['all-state-handles']), all_state_handles)

    def test_g_delete(self):
        from quicksave.__main__ import main
        ## Test no-save option
        tmp = open(os.path.join(self.test_directory.name, random_string(90)), 'w+b')
        tmp.write(os.urandom(4096))
        tmp.close()
        filekey = main([
            '--return-result',
            'register',
            tmp.name
        ])[0]
        main([
            '--return-result',
            'delete-key',
            filekey,
            '--no-save'
        ])
        remaining = main([
            '--return-result',
            'list',
            '-a'
        ])
        DATA['all-file-handles'] = [item for item in remaining]
        self.assertFalse(filekey in remaining)
        self.assertFalse('~trash' in remaining)
        ## Test regular options
        main([
            '--return-result',
            'delete-key',
            DATA['temp-filekey'],
        ])
        remaining = main([
            '--return-result',
            'list',
            '-a'
        ])
        DATA['all-file-handles'] = [item for item in remaining]
        self.assertFalse(DATA['temp-filekey'] in remaining)
        self.assertTrue('~trash' in remaining)
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'delete-key',
                '~trash'
            ])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'delete-key',
                DATA['new-file-alias']
            ])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'delete-key',
                'Probably not a real key though'
            ])
        main([
            '--return-result',
            'delete-key',
            DATA['register-filekey'],
            DATA['register-statekey']
        ])
        remaining = main([
            '--return-result',
            'list',
            '~last',
            '-a'
        ])
        DATA['all-state-handles'] = [item for item in remaining]
        self.assertFalse(DATA['register-statekey'] in remaining)
        self.assertTrue('~trash' in remaining)
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'delete-key',
                'Probably not a real key though',
                '~trash'
            ])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'delete-key',
                DATA['register-filekey'],
                '~trash'
            ])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'delete-key',
                DATA['register-filekey'],
                DATA['new-state-alias']
            ])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'delete-key',
                DATA['register-filekey'],
                'Probably not a real key though'
            ])

    def test_h_lookup(self):
        from quicksave.__main__ import main

        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'lookup',
                'Probably not a real key though'
            ])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'lookup',
                'Probably not a real key though',
                'Also unlikely to be a key'
            ])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'lookup',
                DATA['register-filekey'],
                'Also unlikely to be a key'
            ])
        for filekey in DATA['all-file-handles']:
            result = main([
                '--return-result',
                'lookup',
                filekey
            ])
            if filekey != '~trash':
                self.assertEqual(result, DATA['register-filekey'])
        for statekey in DATA['all-state-handles']:
            result = main([
                '--return-result',
                'lookup',
                '~last',
                statekey
            ])
            if not statekey.startswith("~"):
                self.assertEqual(result, DATA['save-statekey'])

    def test_i_recover(self):
        from quicksave.__main__ import main

        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'recover',
                '~last'
            ])
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'recover'
            ]+DATA['all-file-handles'])
        main([
            '--return-result',
            'recover',
            'recovered'
        ])
        self.assertTrue('recovered' in main([
            '--return-result',
            'list',
            '-a'
        ]))
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'recover'
            ])

    def test_j_clean(self):
        from quicksave.__main__ import main
        from quicksave.utils import _fetch_db

        #create an unused folder in the database
        folderpath = os.path.join(self.db_directory.name, random_string(90))
        os.mkdir(folderpath)

        #Create an orphaned database file
        database = _fetch_db(lambda *args, **kwargs: None)
        filepath = os.path.join(
            self.db_directory.name,
            database.file_keys[DATA['register-filekey']][1],
            random_string(90)
        )
        writer = open(filepath, 'wb')
        writer.write(os.urandom(32))
        writer.close()

        #Create an unlinked file key
        writer = open(os.path.join(self.test_directory.name, random_string(90)), 'w+b')
        writer.write(os.urandom(4096))
        writer.close()
        result = main([
            '--return-result',
            'register',
            writer.name
        ])
        database = _fetch_db(_do_print)
        rmtree(os.path.join(
            database.base_dir,
            database.file_keys[result[0]][1],
        ))
        unlinked_file_key = ""+result[0]

        #Create an unlinked state key
        writer = open(os.path.join(self.test_directory.name, random_string(90)), 'w+b')
        writer.write(os.urandom(4096))
        writer.close()
        result = main([
            '--return-result',
            'register',
            writer.name
        ])
        database = _fetch_db(_do_print)
        os.remove(os.path.join(
            database.base_dir,
            database.file_keys[result[0]][1],
            database.state_keys[result[0]+":"+result[2]][2]
        ))
        unlinked_state_key = result[0]+":"+result[2]

        #Create some trash keys
        statekeys = main([
            '--return-result',
            'list',
            'recovered'
        ])
        main([
            '--return-result',
            'delete-key',
            'recovered',
            statekeys[0]
        ])
        target = main([
            '--return-result',
            'lookup',
            'recovered'
        ])
        main([
            '--return-result',
            'delete-key',
            target
        ])

        #create some duplicates
        #Create an unlinked state key
        writer = open(os.path.join(self.test_directory.name, random_string(90)), 'w+b')
        writer.write(os.urandom(4096))
        writer.close()
        main([
            '--return-result',
            'register',
            writer.name
        ])
        result = main([
            '--return-result',
            'save',
            writer.name,
            '--allow-duplicate'
        ])
        duplicate_state_key = result[0]+":"+result[1]

        #create an orphaned state, and some invalid file aliases
        writer = open(os.path.join(self.test_directory.name, random_string(90)), 'w+b')
        writer.write(os.urandom(4096))
        writer.close()
        register_result = main([
            '--return-result',
            'register',
            writer.name
        ])
        writer = open(writer.name, 'w+b')
        writer.write(os.urandom(4096))
        writer.close()
        save_result = main([
            '--return-result',
            'save',
            writer.name
        ])
        database = _fetch_db(_do_print)
        del database.file_keys[register_result[0]]
        del database.state_keys[register_result[0]+":"+save_result[1]]
        database.save()
        orphan_states = {state for state in database.state_keys if state.startswith(register_result[0])}
        invalid_file_aliases = set(register_result[1])

        #Create an invalid state alias, and break the file index
        writer = open(os.path.join(self.test_directory.name, random_string(90)), 'w+b')
        writer.write(os.urandom(4096))
        writer.close()
        register_result = main([
            '--return-result',
            'register',
            writer.name
        ])
        database = _fetch_db(_do_print)
        _statekey = register_result[0]+":"+register_result[2]
        del database.state_keys[_statekey]
        database.file_keys[register_result[0]][2] = 'fish'
        database.save()
        invalid_state_aliases = {key for key in database.state_keys if database.state_keys[key][0]==_statekey}

        #finaly run the clean
        result = main([
            '--return-result',
            'clean',
            '-dtwras'
        ])

        self.assertTrue("prune_folders" in result)
        self.assertEqual(len(result['prune_folders']), 2)
        self.assertTrue(os.path.basename(folderpath) in result['prune_folders'])

        self.assertTrue('prune_files' in result)
        self.assertEqual(len(result['prune_files']), 2)
        self.assertTrue(os.path.relpath(filepath, self.db_directory.name) in result['prune_files'])

        self.assertTrue('prune_filekeys' in result)
        self.assertEqual(len(result['prune_filekeys']), 1)
        self.assertTrue(unlinked_file_key in result['prune_filekeys'])

        self.assertTrue('prune_statekeys' in result)
        self.assertEqual(len(result['prune_statekeys']), 1)
        self.assertTrue(unlinked_state_key in result['prune_statekeys'])

        self.assertTrue('trash_file' in result)
        self.assertFalse(result['trash_file'])

        self.assertTrue('trash_state' in result)
        self.assertEqual(result['trash_state'][0], 2)

        self.assertTrue('deduplicate' in result)
        self.assertEqual(len(result['deduplicate']), 1)
        self.assertTrue(duplicate_state_key in result['deduplicate'])

        self.assertTrue('states' in result)
        self.assertEqual(len(result['states']), 5)
        self.assertFalse(set(result['states'])^orphan_states)

        self.assertTrue('file_aliases' in result)
        self.assertEqual(len(result['file_aliases']), 2)
        self.assertFalse(set(result['file_aliases'])^invalid_file_aliases)

        self.assertTrue('state_aliases' in result)
        self.assertEqual(len(result['state_aliases']), 2)
        self.assertFalse(set(result['state_aliases'])^invalid_state_aliases)

        self.assertTrue('rebuilt' in result)
        self.assertEqual(result['rebuilt'], 1)

    def test_k_status(self):
        from quicksave.__main__ import main

        writer = open(os.path.join(self.test_directory.name, random_string(90)), 'w+b')
        writer.write(os.urandom(4096))
        writer.close()
        self.assertFalse(main([
            '--return-result',
            'status',
            writer.name,
            '-k',
            DATA['register-filekey']
        ])[1])
        statename = main([
            '--return-result',
            'list',
            DATA['register-filekey']
        ])
        statename.pop(statename.index("~stash"))
        statename=statename[0]
        main([
            '--return-result',
            'revert',
            writer.name,
            statename,
            '-k',
            DATA['register-filekey']
        ])
        state = main([
            '--return-result',
            'status',
            writer.name,
            '-k',
            DATA['register-filekey']
        ])[1]
        self.assertEqual(state, DATA['register-filekey']+":"+statename)
        main([
            '--return-result',
            'revert',
            writer.name,
            '~stash',
            '-k',
            DATA['register-filekey']
        ])
        result = main([
            '--return-result',
            'save',
            writer.name,
            '-k',
            DATA['register-filekey']
        ])
        state = main([
            '--return-result',
            'status',
            writer.name,
            '-k',
            DATA['register-filekey']
        ])[1]
        self.assertEqual(state, DATA['register-filekey']+":"+result[1])

    def test_l_config(self):
        from quicksave.__main__ import main
        from quicksave.utils import _fetch_db, _fetch_flags

        test_global= {}
        test_db = {}
        reference_global = {}
        reference_db = {}
        with self.assertRaises(SystemExit):
            main([
                '--return-result',
                'config'
            ])
        for trial in range(100):
            key = ''
            command = ['--return-result', 'config']
            if trial and not trial%10:
                if trial%20:
                    key = {k for k in test_global}.pop()
                    command += [key, '--clear', '--global']
                    del reference_global[key]
                else:
                    key = {k for k in test_db}.pop()
                    command += [key, '--clear']
                    del reference_db[key]
            else:
                key = random_string()
                value = random_string()
                command += [key, value]
                if trial%2:
                    command.append('--global')
                    reference_global[key] = value
                else:
                    reference_db[key] = value
            result = main(command)
            if result[1]:
                test_global[result[0]] = result[1]
            elif result[0] in test_global:
                del test_global[result[0]]
            if result[2]:
                test_db[result[0]] = result[2]
            elif result[0] in test_db:
                del test_db[result[0]]
            self.assertDictEqual(reference_global, test_global)
            self.assertDictEqual(reference_db, test_db)
        for key in reference_global:
            self.assertEqual(reference_global[key], main([
                '--return-result',
                'config',
                key
            ])[1])
        for key in reference_db:
            self.assertEqual(reference_db[key], main([
                '--return-result',
                'config',
                key
            ])[2])
        fullConfig = main([
            '--return-result',
            'config',
            '--list'
        ])
        for (key, value) in fullConfig.items():
            glbVal = value[0]
            dbVal = value[1]
            if glbVal is None:
                self.assertNotIn(key, reference_global)
            else:
                self.assertIn(key, reference_global)
                self.assertEqual(reference_global[key], glbVal)
            if dbVal is None:
                self.assertNotIn(key, reference_db)
            else:
                self.assertIn(key, reference_db)
                self.assertEqual(reference_db[key], dbVal)

        self.assertDictEqual(reference_db, _fetch_db(_do_print).flags)
        self.assertDictEqual(reference_global, _fetch_flags(False))
