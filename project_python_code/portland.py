#!/usr/bin/env python
import xml.etree.cElementTree as ET
import pprint, re, codecs, json, optparse, os, csv
from collections import defaultdict
from time import time

"""
Takes an osm file and csv file containing valid zip codes, specified as args:

python portland.py   -f portland_oregon.osm   -z zipCodes.csv

parses the osm data, cleans up the street addresses and zip codes,
prints a list of zip codes found in the data to a txt file,
and outputs cleaned data to JSON
"""


p = optparse.OptionParser()
p.add_option('-f', '--file', dest = 'filename') #specifies input osm file
p.add_option('-z', '--zip', dest = 'validZipCodes') #csv of valid zip codes
options, arguments = p.parse_args()

filename = options.filename
validZipCodesFile = options.validZipCodes



#parses osm file and stores counts of each tag type in a dict which is returned
def count_tags(filename):
    d = defaultdict(int)
    for event, elem in ET.iterparse(filename):
        d[elem.tag] += 1

    return d

#if last word in address not an expected street name, add to street_types dict
def audit_street_type(street_types, street_name):
    m = street_type_re.search(street_name)
    if m:
        street_type = m.group()
        if street_type not in expected:
            street_types[street_type].add(street_name)

def is_street_name(elem):
    return (elem.attrib['k'] == "addr:street")

#finds addresses, then audits street names. returns set of unexpected st. types
def audit(filename):
    osm_file = open(filename, "r")
    street_types = defaultdict(set)
    for event, elem in ET.iterparse(osm_file, events=("start",)):
        if elem.tag == "node" or elem.tag == "way":
            for tag in elem.iter("tag"):
                if is_street_name(tag):
                    audit_street_type(street_types, tag.attrib['v'])

    return street_types

#changes informal street type to formal, eg Ave. to Avenue,
#based on k:v pairs in mapping dict
def update_name(name, mapping):
    splitName = name.rsplit(None, 1)
    if len(splitName) > 1:
        if splitName[1] in mapping:
            newName = splitName[0] + " " + mapping[splitName[1]]
            return newName
    return name

#helper function for sortKeys:
#checks to see if a key has all lowercase, a colon, problematic chars,
#or none of these and adds count to appropriate dict key
def key_type(element, keys):
    if element.tag == "tag":
	k = element.attrib['k']

        if lower.match(k):
            keys["lower"] += 1
        elif lower_colon.match(k):
            keys["lower_colon"] += 1
        elif problemchars.match(k):
            keys["problemchars"] += 1
        else:
            keys["other"] += 1

    return keys

#returns dict of 4 keys w/ counts of how many elements match each regex
def sortKeys(filename):
    keys = {"lower": 0, "lower_colon": 0, "problemchars": 0, "other": 0}
    for _, element in ET.iterparse(filename):
        keys = key_type(element, keys)
    return keys

#returns set of unique users who contributed to the map
def getSetOfUsers(filename):
    users = set()
    for _, element in ET.iterparse(filename):
        for elem in element:
            for k in elem.attrib:
                if k == 'uid':
                    users.add(elem.attrib[k])
    return users

#returns a set of the unique postal codes in the osm entries
def getPostalCodesSet(filename):
    codes = set()
    for _, element in ET.iterparse(filename):
        if element.tag == "tag":
            if element.attrib['k'] == "addr:postcode":
                codes.add(element.attrib['v'])

    return codes


#takes in an osm element and transforms it into a dictionary,
#that is ready to output to json file
#cleans up street names and zip codes in entries before writing to dict
def shape_element(element):
    node = {}
    created = {}
    address = {}
    lat = None
    lon = None
    node_refs = []
    fields = ["id", "type", "visible", "amenity", "cuisine", "name", "phone", "religion"]
    if element.tag == "node" or element.tag == "way" :
        node["type"] = element.tag
        attribs = element.attrib.items()
        for a in attribs:
            if a[0] == 'lat':
                lat = a[1]
            elif a[0] == 'lon':
                lon = a[1]
            elif a[0] in CREATED:
                created[a[0]] = a[1]
            elif a[0] in fields:
                node[a[0]] = a[1]
                    
        for elem in element:
            items = elem.items()
            key = items[0][1]
            if items[0][0] == 'ref' and element.tag == "way":
                node_refs.append(key)
            elif double_colon.match(key):
                continue
            elif lower_colon.match(key):
                val = items[1][1]
                if key[0:5] == "addr:":
                    if items[0][1] == "addr:street":
                        #fix street name before adding
                        name = update_name(val, mapping)
                        address[key[5:]] = name
                    #do NOT add invalid postal codes, skip them entirely
                    elif items[0][1] == "addr:postcode":
                        if val[0:5] in validZipCodes:
                           address[key[5:]] = val
                        else:
                            #extract valid zip codes from full address entries
                            print "running regex on zip code entry:", val
                            zipCode = re.search(r'.*(\d{5}(\-\d{4})?)$', val)
                            if zipCode != None:
                                if zipCode.group(1)[0:5] in validZipCodes:
                                    address[key[5:]] = zipCode.group(1)
                                    print val, "===>", zipCode.group(1)
                            else:
                                print "no match for:", val

                    else:
                        name = val
                        address[key[5:]] = name

            else:
                if key in fields:
                    node[key] = items[1][1]

                    


        if node_refs:
            node["node_refs"] = node_refs
        if address:
            node["address"] = address
        if lat and lon:
            node["pos"] = [float(lat),float(lon)]
        if created:
            node["created"] = created
        return node
    else:
        return None

#iterate through osm file and convert it to a JSON file using calls to shape_element
def convertToJSON(filename, pretty = False):
    file_out = "{0}.json".format(filename)
    data = []
    with codecs.open(file_out, "w") as fo:
        for _, element in ET.iterparse(filename):
            el = shape_element(element)
            if el:
                data.append(el)
                if pretty:
                    fo.write(json.dumps(el, indent=2)+"\n")
                else:
                    fo.write(json.dumps(el) + "\n")
    return data

def getValidZipCodesSet():
#produces a set of all valid zip codes in WA and OR using zip code csv file
    validZipCodes = set()
    with open(validZipCodesFile, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            validZipCodes.add(row['Postal Code'])
    return validZipCodes

########
##MAIN##
########

#count all tags to see what we're dealing with in the file
"""
tags = count_tags(filename)
pprint.pprint(tags)
"""
#'node': 2702015, 'nd': 3092275, 'bounds': 1, 'member': 49193,
# 'tag': 1834943, 'relation': 5107, 'way': 303283, 'osm': 1

#check key values for each tag and see if they have colons or problematic chars
#because we want to store them as keys in a dict
lower = re.compile(r'^([a-z]|_)*$')
lower_colon = re.compile(r'^([a-z]|_)*:([a-z]|_)*$')
problemchars = re.compile(r'^([a-z]|_)*[=\+/&<>;\'"?%#$@\,\. \t\r\n]([a-z]|_)*$')

#see how many keys match regexs of normal and problematic structure
"""
keys = sortKeys(filename)
pprint.pprint(keys)
"""
#'lower': 959187, 'lower_colon': 843447, 'other': 32309, 'problemchars': 0


#clean up zip codes
codes = sorted(getPostalCodesSet(filename))
fiveDigitCodes = set([z[0:5] for z in codes if len(z) >= 5])
print "Number of unique zip codes in the dataset:", len(fiveDigitCodes)

validZipCodes = getValidZipCodesSet()
print "number of valid zip codes in Washington and Oregon:", len(validZipCodes)

invalidZipCodes = [z for z in codes if z[0:5] not in validZipCodes]
#[0:5] to forgive 4-digit zip code extensions
print "invalid zip codes in my map:\n", invalidZipCodes

"""#uncomment to print list of zip codes to a txt file
fout = open('postalCodes.txt', 'w')
for code in codes:
    fout.write(code + "\n")
fout.close()
"""

#get a set of unique contributors to the map
users = getSetOfUsers(filename)
print "number of unique users:", len(users)


#section where we clean up street names
street_type_re = re.compile(r'\b\S+\.?$', re.IGNORECASE)

expected = ['Street', 'Avenue', 'Boulevard', 'Drive', 'Court', 'Terrace', 'Way', \
         'Place', 'Square', 'Lane', 'Road', 'Trail', 'Parkway', 'Commons']

mapping = { "St": "Street",
        "St.": "Street",
        "street": "Street",
        "Rd": "Road",
        "Rd.": "Road",
        "road": "Road",
        "ave": "Avenue",
        "Ave": "Avenue",
        "Ave.": "Avenue",
        "Blvd": "Boulevard",
        "Blvd.": "Boulevard",
        "Cir": "Circle",
        "Dr": "Drive",
        "Dr.": "Drive",
        "Hwy": "Highway",
        "highway": "Highway",
        "Ln": "Lane",
        "Pkwy": "Parkway",
        "Pky": "Parkway",

        }

# get a dict of street types in the map that were not expected. key = last word in address,
# value = list of whole addresses with that last word
st_types = audit(filename)
#uncomment to print to console
#pprint.pprint(dict(st_types))

#print out the mappings from old street name to new
for st_type, ways in st_types.iteritems():
    for name in ways:
        better_name = update_name(name, mapping)
        #uncomment to print to console
        #print name, "=>", better_name



lower = re.compile(r'^([a-z]|_)*$')
lower_colon = re.compile(r'^([a-z]|_)*:([a-z]|_)*$')
double_colon = re.compile(r'^([a-z]|_)*:([a-z]|_)*:([a-z]|_)*$')
problemchars = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

CREATED = [ "version", "changeset", "timestamp", "user", "uid"]

#transform the data into a list of dictionaries,
#ignoring data that doesn't fit our guidelines,
#and finally print to json file
data = convertToJSON(filename, False)

