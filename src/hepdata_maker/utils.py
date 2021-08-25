import json
import jsonref       # type: ignore
import jsonschema    # type: ignore
import pkg_resources # type: ignore
from pathlib import Path
from collections import OrderedDict
from collections.abc import Mapping,Iterable
from typing import Dict,Any,Optional,Union
import os
import validators    # type: ignore

SCHEMA_CACHE:Dict[str,Any]= {}
SCHEMA_BASE = "schemas"
SCHEMA_VERSION = '0.0.0'

def merge_dictionaries(*args: Dict[Any,Any]) -> Dict[Any,Any]:
    # This is easily done in python 3.9 with dict1|dict2, however for 3.8 we need this 
    for arg in args:
        if(not isinstance(arg,Mapping)):
            raise ValueError(f"Only dictionary-like objects can be merged together. Provided were {args}")
    result = {}
    for dictionary in args:
        result.update(dictionary)
    return result

#
# Schema functionality copied/inspired from/by https://github.com/scikit-hep/pyhf/blob/master/src/pyhf/utils.py 
#
def load_schema(schema_id: str,
                version:Optional[str]=None):
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

def check_schema(json_data:Dict[str, Any],
                 schema_name:str,
                 version:Optional[str]=None):
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

def resolve_file_name(file_name:Union[str,os.PathLike],
                      root_dir:Union[str,os.PathLike]):
    # return the file_name for file if absolute path given,
    # return root_dir/file_name if file_name is not an absolute path
    # check if file is not a link or email prior to that
    if(validators.url(file_name) or validators.email(file_name)):
        return file_name
    else:
        return os.path.join(root_dir,file_name)

class objdict(OrderedDict):
    def __init__(self, d):
        new_dict=OrderedDict()
        for key, value in d.items():
            if(isinstance(value, Mapping)):
                new_dict[key]=objdict(value)
            elif(isinstance(value, Iterable) and type(value)!=str):
                new_dict[key]=[objdict(entry) if (isinstance(entry, Mapping) and type(value)!=str) else entry for entry in value]
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
    def to_dict(self):
        return dict(self)
    
def get_available_tables(config_file_path:Union[str,os.PathLike]):
    # Get names and 'should_be_processed' fields for all tables
    # withing a steering_file
    result=[]
    with open(config_file_path, 'r') as stream:
        config_loaded = jsonref.load(stream,base_uri="file://"+os.path.abspath(os.path.dirname(config_file_path))+"/",object_pairs_hook=OrderedDict)
    for table_info in config_loaded['tables']:
        result.append((table_info['name'],table_info['should_be_processed']))
    return result
