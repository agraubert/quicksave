import unittest
import tempfile
import sys
import os
from py_compile import compile
from shutil import copyfile
import random
from  hashlib import sha256

def random_string(upper=125):
    return "".join([chr(random.randint(65, upper)) for _ in range(15)])

class test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_directory = tempfile.TemporaryDirectory()
        cls.db_directory = tempfile.TemporaryDirectory()
        basepath = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        cls.script_path = os.path.join(
            basepath,
            'quicksave',
            '__main__.py'
        )
        sys.path.append(basepath)
        from quicksave.__main__ import configfile
        copyfile(configfile, 'config_backup')
        random.seed()

    @classmethod
    def tearDownClass(cls):
        from quicksave.__main__ import configfile
        copyfile('config_backup', configfile)
        cls.test_directory.cleanup()

    def test_compilation(self):
        compiled_path = compile(self.script_path)
        self.assertTrue(compiled_path)

    def test_a_init(self):
        from quicksave.__main__ import main

        #INIT
        self.assertEqual(main([
            'init',
            self.db_directory.name
        ]), self.db_directory.name)

        #REGISTER
        sourcefile = open(os.path.join(self.test_directory.name, random_string(90)), 'w+b')
        content = os.urandom(4096)
        sourcefile.write(content)
        sourcefile.close()
        f_aliases = [random_string() for _ in range(random.randint(0, 5))]
        s_aliases = [random_string() for _ in range(random.randint(0, 5))]
        command = ['register', sourcefile.name] + [alias for alias in s_aliases]
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
        hashkey = sha256(content).hexdigest()
        self.assertTrue(hashkey[:7] in result[3])
        with self.assertRaises(SystemExit):
            main(command)
        self.filekey = result[0]
        self.statekey = result[1]
        self.sourcefile = sourcefile.name
        self.sourcecontent = content
        main(['register', sourcefile.name] + [alias for alias in s_aliases]+['--ignore-filepath'])

        #SAVE
        with self.assertRaises(SystemExit):
            main([
                'save',
                self.sourcefile
            ])
        copyfile(self.sourcefile, os.path.join(self.test_directory.name, '_blerg_'))
        with self.assertRaises(SystemExit):
            main([
                'save',
                os.path.join(self.test_directory.name, '_blerg_'),
                '-k',
                self.filekey
            ])
        new_sourcefile = open(os.path.join(self.test_directory.name, random_string(90)), 'w+b')
        new_content = os.urandom(4096)
        new_sourcefile.write(content)
        new_sourcefile.close()
        aliases = [random_string() for _ in range(random.randint(0, 5))]
        with self.assertRaises(SystemExit):
            main([
                'save',
                new_sourcefile.name
            ])
        command = ['save', new_sourcefile.name] + aliases + ['-k', self.filekey]
        result = main(command)
        self.assertEqual(result[0], self.filekey)
        self.assertEqual(result[1], new_sourcefile.name[:5]+"_SK2")
        self.assertTrue(len(result[2]), len(aliases)+1)
        for alias in s_aliases:
            self.assertTrue(alias in result[2])
        hashkey = sha256(content).hexdigest()
        self.assertTrue(hashkey[:7] in result[2])
