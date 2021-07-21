#
# Core of the functionality copied/inspired from/by https://github.com/scikit-hep/pyhf/blob/master/src/pyhf/utils.py 
#
import json
import jsonschema
import pkg_resources
from pathlib import Path

SCHEMA_CACHE = {}
SCHEMA_BASE = "schemas"
SCHEMA_VERSION = '0.0.0'

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

def check_schema(file_path, schema_name, version=None):
    schema = load_schema(schema_name, version=version)
    with open(file_path, 'r') as fstream:
        file_data = json.load(fstream)
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
    except jsonschema.ValidationError as err:
        print("Steering file does not match the schema!")
        raise err
