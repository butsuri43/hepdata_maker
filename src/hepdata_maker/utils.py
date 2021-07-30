import json
import jsonschema
import pkg_resources
from pathlib import Path
from collections import OrderedDict
import collections
import os

SCHEMA_CACHE = {}
SCHEMA_BASE = "schemas"
SCHEMA_VERSION = '0.0.0'

#
# Schema functionality copied/inspired from/by https://github.com/scikit-hep/pyhf/blob/master/src/pyhf/utils.py 
#
def load_schema(schema_id, version=None):
    global SCHEMA_CACHE
    if not version:
        version = SCHEMA_VERSION
    try:
        return SCHEMA_CACHE[f'{SCHEMA_BASE}{Path(version).joinpath(schema_id)}']
    except KeyError:
        pass

    path = pkg_resources.resource_filename(
        __name__, str(Path('schemas').joinpath(version, schema_id))
    )
    with open(path) as json_schema:
        schema = json.load(json_schema)
        SCHEMA_CACHE[schema['$id']] = schema
    return SCHEMA_CACHE[schema['$id']]

# load the defs.json as it is included by $ref
load_schema('defs.json')

def check_schema(json_data, schema_name, version=None):
    schema = load_schema(schema_name, version=version)
    try:
        resolver = jsonschema.RefResolver(
            base_uri=f"file://{pkg_resources.resource_filename(__name__, 'schemas/'):s}",
            referrer=schema_name,
            store=SCHEMA_CACHE,
        )
        #print("base_url",resolver.base_uri)
        validator = jsonschema.Draft7Validator(
            schema, resolver=resolver, format_checker=None
        )
        return validator.validate(json_data)
    except jsonschema.ValidationError as err:
        print("Steering file does not match the schema!")
        raise err

def resolve_file_name(file_name,root_dir):
    # return the file_name for file if absolute path given,
    # return root_dir/file_name if file_name is not an absolute path
    return os.path.join(root_dir,file_name)

class objdict(collections.OrderedDict):
    def __init__(self, d):
        new_dict=collections.OrderedDict()
        for key, value in d.items():
            if(isinstance(value, collections.abc.Mapping)):
                new_dict[key]=objdict(value)
            elif(isinstance(value, collections.abc.Iterable) and type(value)!=str):
                new_dict[key]=[objdict(entry) if (isinstance(entry, collections.abc.Mapping) and type(value)!=str) else entry for entry in value]
            else:
                new_dict[key]=value
        super().__init__(d)
        self.__dict__.update(new_dict)
    def __setitem__(self, key, value):
        super().__setitem__(key,value)
        self.__dict__[key]=value
    def __delitem__(self, key):
        super().__delitem__(key)
        del self.__dict__[key]
def get_available_tables(config_file_path):
    result=[]
    with open(config_file_path, 'r') as stream:
        config_loaded = json.load(stream,object_pairs_hook=OrderedDict)
    for table_info in [objdict(x) for x in config_loaded['tables']]:
        result.append((table_info.name,table_info.should_be_processed))
    return result
