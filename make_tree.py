#!/bin/env python
'''
make_tree.py

Copyright (c) 2015, David Edwards, Bernie Pope, Kat Holt
All rights reserved. (see README.txt for more details)

example:
python make_tree.py  <input_file> <outTemp_file> <output_directory>

Created:    17/10/2016
Modified:   

author: David Edwards
'''
import os, sys, commands

input_file = sys.argv[1]
output_file = sys.argv[2]
output_directory = sys.argv[3]

command1 = "FastTree -gtr -gamma -nt " + input_file + " > " + output_file
print "Running FastTree as follows:"
print command1
os.popen(command1)

command2 = "cd " + output_directory + " && cp " + output_file + " . "
print "Copying output tree as follows:"
print command2
os.popen(command2)
