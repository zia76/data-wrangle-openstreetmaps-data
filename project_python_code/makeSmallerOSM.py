#!/usr/bin/env python
# -*- coding: utf-8 -*-

import xml.etree.cElementTree as ET
import random
from optparse import OptionParser

"""
This script takes in an osm file, parses it, and returns a
random subset of elements also in osm format. The percent
of the original file size to output can be specified as an arg
in -p --percent, and defaults to 1%.
"""
OSM_FILE = "portland_oregon.osm"  # input file
SAMPLE_FILE = "portland_sample.osm" #output subsample file

p = OptionParser()
p.add_option('-p', '--percent', dest = 'percentToOutput', type = "float",\
             default = 1)
options, arguments = p.parse_args()

percentToOutput = options.percentToOutput
random.seed(42)

def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag"""

    context = ET.iterparse(osm_file, events=('start', 'end'))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()


with open(SAMPLE_FILE, 'wb') as output:
    output.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    output.write('<osm>\n  ')

    # Write 1% of top level elements, randomly chosen
    for i, element in enumerate(get_element(OSM_FILE)):
        if random.randint(1, int(100 / percentToOutput)) == 1:
            output.write(ET.tostring(element, encoding='utf-8'))

    output.write('</osm>')
