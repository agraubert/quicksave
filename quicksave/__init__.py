import argparse

#saves the states of files
#quicksave register <filename> [aliases...]
#   The file's set of registered states are linked to a uniquely generated key (the primary key),
#       but can also be accessed by the original absolute filepath, the original filename, or any user-defined aliases for this file
#   Automatically runs '$quicksave save' afterwards to generate an initial save
#   Returns the primary key for this file and the state key of the initial save
#quicksave save <filename> [primary key] [aliases...]
#   saves <filename>'s current state to the database
#   If no primary key is specified, it attempts to link to a primary key based on filepath, then filename
#       If neither the filepath nor the filename match any primary keys, require the user to specify one
#   Otherwise, link to the provided primary key
#   Generates the following state keys for the savepoint: rev-# (unique, where # is the index number of revisions to date),
#       the first 7 characters of a sha-256 hash, the full sha-256 hash (assumed unique),
#       the filename (iff it differs from the filename on the primary key and is not already a state-key), and any user-defined aliases
#   Returns the primary key (iff it was not specified) and the state-key (iff an alias was not provided)
#quicksave revert <filename> [primary key] state-key
#   Reverts filename to

def main():
    parser = argparse.ArgumentParser("quicksave")
    subparsers = parser.add_supbarsers()

if __name__ == '__main__':
    main()
