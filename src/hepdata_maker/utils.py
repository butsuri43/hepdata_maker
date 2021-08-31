import json
import jsonref       # type: ignore
import jsonschema    # type: ignore
import pkg_resources # type: ignore
from pathlib import Path
from collections import OrderedDict
from collections.abc import Mapping,Iterable
from typing import Dict,Any,Optional,Union,List,Tuple
import os
import validators    # type: ignore

SCHEMA_CACHE:Dict[str,Any]= {}
SCHEMA_BASE = "schemas"
SCHEMA_VERSION = '0.0.0'

def merge_dictionaries(*args: Dict[Any,Any]) -> Dict[Any,Any]:
    """
    This is easily done in python 3.9 with dict1|dict2, however for 3.8- we need this.
    """
    for arg in args:
        if(not isinstance(arg,Mapping)):
            raise ValueError(f"Only dictionary-like objects can be merged together. Provided were {args}")
    result = {}
    for dictionary in args:
        result.update(dictionary)
    return result

def load_schema(schema_id: str,
                version:Optional[str]=None):
    """
    Schema functionality adopted from https://github.com/scikit-hep/pyhf/blob/master/src/pyhf/utils.py
    """

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
    """
    Schema functionality adopted from https://github.com/scikit-hep/pyhf/blob/master/src/pyhf/utils.py
    """
    schema = load_schema(schema_name, version=version)
    try:
        resolver = jsonschema.RefResolver(
            base_uri=f"file://{pkg_resources.resource_filename(__name__, 'schemas/'):s}",
            referrer=schema_name,
            store=SCHEMA_CACHE,
        )
        validator = jsonschema.Draft7Validator(
            schema, resolver=resolver, format_checker=None
        )
        return validator.validate(json_data)
    except jsonschema.ValidationError as err:
        print("Steering file does not match the schema!")
        raise err

def resolve_file_name(file_name:Union[str,os.PathLike],
                      root_dir:Union[str,os.PathLike]):
    """
    Returns the FILE_NAME for file if absolute path given
    or detected a link or an email,
    returns ROOT_DIR/FILE_NAME if file_name is not an absolute path.
    """
    if(validators.url(file_name) or validators.email(file_name)):
        return file_name
    else:
        return os.path.join(root_dir,file_name)

class objdict(OrderedDict):
    """
    Ordered dictionary with keys accesible as object attributes.

    .. note:: This class will propably disappear in next versions of the hepdata_maker.
    """
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
    """
    Get names and 'should_be_processed' fields for all tables
    withing a steering_file
    """
    result=[]
    with open(config_file_path, 'r') as stream:
        config_loaded = jsonref.load(stream,base_uri="file://"+os.path.abspath(os.path.dirname(config_file_path))+"/",object_pairs_hook=OrderedDict)
    for table_info in config_loaded['tables']:
        result.append((table_info['name'],table_info.get('should_be_processed',True)))
    return result

def get_requested_table_list(steering_file:str,
                             load_all_tables:bool,
                             indices:List[int],
                             names:List[str])->List[Tuple[str,bool]]:
    """
    Get names of tables inside a steering_file with matching position/names
    """
    available_tables=get_available_tables(steering_file)
    if(load_all_tables):
        return available_tables
    if(len(indices)==0 and len(names)==0):
        raise TypeError(f"You need to provide the name/index of the table you want to print. Choose from: (name,index)={[(tuple[0],index) for index,tuple in enumerate(available_tables)]}")
    if(len(indices)>0 and (max(indices)>len(available_tables) or min(indices)<0)):
        raise ValueError(f"You requested table with index {max(indices)} while only range between 0 and {len(available_tables)} is available!")
    requested_tables=[]
    if(indices is not None):
        for idx in indices:
            name=available_tables[idx][0]
            should_be_processed=available_tables[idx][1]
            if(not should_be_processed):
                raise ValueError(f"You requested table with index {idx} (name: {name}) however flag 'should_be_processed' is set to False.")
            requested_tables.append((name,should_be_processed))
    available_table_names=[table[0] for table in available_tables]
    if(names is not None):
        for name in names:
            if(name not in available_table_names):
                raise ValueError(f"You requested table with name {name} however this name is not found in the file {steering_file}. Available are {[table[0] for table in available_tables]}")
            for av_name,should_be_processed in available_tables:
                if(av_name==name and (not should_be_processed)):
                    raise ValueError(f"You requested table with name: {name} however flag 'should_be_processed' is set to False.")
            requested_tables.append((name,True))
    return requested_tables
