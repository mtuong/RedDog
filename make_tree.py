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
import os, sys, command

input_file = sys.argv[1]
output_file = sys.argv[2]
output_directory = sys.argv[3]

command = "FastTree -gtr -gamma -nt " + input_file + " > " + output_file
os.popen(command)

command = "cp " + output_file + " > " + output_directory
os.popen(command)
