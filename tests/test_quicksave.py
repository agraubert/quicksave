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
        from quicksave.__main__ import configfile
        if os.path.isfile(configfile):
            copyfile(configfile, 'config_backup')
        warnings.simplefilter('ignore', ResourceWarning)

    @classmethod
    def tearDownClass(cls):
        from quicksave.__main__ import configfile
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

    def test_g_delete(self):
        from quicksave.__main__ import main

        main([
            '--return-result',
            'delete-key',
            DATA['temp-filekey']
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
        from quicksave.__main__ import main, _fetch_db

        #create an unused folder in the database
        folderpath = os.path.join(self.db_directory.name, random_string(90))
        os.mkdir(folderpath)

        #Create an orphaned database file
        database = _fetch_db()
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
        database = _fetch_db()
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
        database = _fetch_db()
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

        #finaly run the clean
        result = main([
            '--return-result',
            'clean',
            '-dtw'
        ])
        # print(result)

        self.assertTrue("prune_folders" in result)
        self.assertEqual(len(result['prune_folders']), 1)
        self.assertTrue(os.path.basename(folderpath) in result['prune_folders'])

        self.assertTrue('prune_files' in result)
        self.assertEqual(len(result['prune_files']), 1)
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
