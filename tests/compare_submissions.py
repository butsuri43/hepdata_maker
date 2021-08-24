import click
import glob
import rich
from rich.console import Console
from hepdata_maker import checks
import os.path
import re
import yaml
from yaml import CSafeLoader as Loader
import jq
console = Console()


def list_basename(in_list):
    return [os.path.basename(x) for x in in_list]

def clear_from_spurious_files(file_list):
    failing_patterns=["^\\..*",".*~","_.*"]
    return [x for x in file_list if
            not any(
                [
                    re.match(pattern,os.path.basename(x))
                    for pattern in failing_patterns
                ])
            ]
    
def get_file_names(directory):
    all_files=list_basename(glob.glob(directory+'/**/*',recursive=True))
    all_files=clear_from_spurious_files(all_files)
    yaml_files=[x for x in all_files if re.match(".*.yaml$",x)]
    png_files=[x for x in all_files if re.match(".*.png$",x)]
    other=list(set(all_files)-set(yaml_files)-set(png_files))
    return {"png":png_files,"yaml":yaml_files,"other":other}

def get_referenced_yaml_files(submission_file_path):
    directory=os.path.dirname(submission_file_path)
    all_referenced=[submission_file_path]
    # Open the submission.yaml file and load all YAML documents.
    with open(submission_file_path, 'r') as stream:
        docs = list(yaml.load_all(stream, Loader=Loader))

    # Loop over all YAML documents in the submission.yaml file.
    for doc in docs:
        if 'data_file' in doc:
            # Extract data file from YAML document.
            data_file_path = directory + '/' + doc['data_file'] if directory else doc['data_file']
            all_referenced.append(data_file_path)
    return all_referenced

def get_names_down_to_errors(submission_file_path):
    directory=os.path.dirname(submission_file_path)
    all_names={'tables':{}}
    # Open the submission.yaml file and load all YAML documents.
    with open(submission_file_path, 'r') as stream:
        docs = list(yaml.load_all(stream, Loader=Loader))

    # Loop over all YAML documents in the submission.yaml file.
    for doc in docs:
        if 'name' in doc:
            all_names['tables'][doc['name']]={'independent_variables':{},'dependent_variables':{}}
            # Extract data file from YAML document.
            if('data_file' in doc):
                data_file_path = directory + '/' + doc['data_file'] if directory else doc['data_file']
                with open(data_file_path, 'r') as stream:
                    data_info = yaml.load(stream, Loader=Loader)
                    indep_var_names=list(set(jq.all(r'.independent_variables[].header.name',data_info)))
                    for var_name in indep_var_names:
                        error_names=list(set(jq.all(rf'.independent_variables[] | select(.header.name=="{var_name}").values[].errors?[]?.label',data_info)))
                        all_names['tables'][doc['name']]['independent_variables'][var_name]={"errors":error_names}
                    dep_var_names=list(set(jq.all('.dependent_variables[].header.name',data_info)))
                    for var_name in dep_var_names:
                        error_names=list(set(jq.all(rf'.dependent_variables[] | select(.header.name=="{var_name}").values[].errors?[]?.label',data_info)))
                        all_names['tables'][doc['name']]['dependent_variables'][var_name]={"errors":error_names}
                            
    return all_names
def get_referenced_additional_resources(submission_file_path):
    directory=os.path.dirname(submission_file_path)
    all_referenced=[]
    # Open the submission.yaml file and load all YAML documents.
    with open(submission_file_path, 'r') as stream:
        docs = list(yaml.load_all(stream, Loader=Loader))

    # Loop over all YAML documents in the submission.yaml file.
    for doc in docs:
        if 'additional_resources' in doc:
            for resource in doc['additional_resources']:
                if not resource['location'].startswith('http'):
                    location = os.path.join(directory, resource['location'])
                    all_referenced.append(location)
        elif 'data_file' in doc:
            # Extract data file from YAML document.
            data_file_path = directory + '/' + doc['data_file'] if directory else doc['data_file']
            with open(data_file_path, 'r') as stream:
                data_info = list(yaml.load(stream, Loader=Loader))
                if('additional_resources' in data_info):
                    for resource in data_info['additional_resources']:
                        if not resource['location'].startswith('http'):
                            location = os.path.join(directory, resource['location'])
                            all_referenced.append(location)
    return all_referenced

@click.command()
@click.argument('dir_one',type=click.Path(exists=True))
@click.argument('dir_two',type=click.Path(exists=True))
def compare_submissions(dir_one,dir_two):
    console.rule("checking hepdata submission files",characters="=")
    console.print(f"Comparing submission in '{dir_one}' and '{dir_two}'.")

    console.rule("checking individual submissions",characters="-")
    submission_one=glob.glob(dir_one+'/**/submission.yaml',recursive=True)[0]
    submission_two=glob.glob(dir_two+'/**/submission.yaml',recursive=True)[0]
    checks.validate_submission(submission_one)
    console.print(f" -> submission {submission_one} is [bold] good.")
    checks.validate_submission(submission_two)
    console.print(f" -> submission {submission_two} is [bold] good.")

    console.rule("Compare number of files",characters="-")
    files_dir_one=get_file_names(dir_one)
    files_dir_two=get_file_names(dir_two)

    actually_required_yamls_one=list_basename(get_referenced_yaml_files(submission_one))
    actually_required_yamls_two=list_basename(get_referenced_yaml_files(submission_two))
    
    actually_required_additional_one=list_basename(get_referenced_yaml_files(submission_one))
    actually_required_additional_two=list_basename(get_referenced_yaml_files(submission_two))

    # the actuall names of the yaml files can varry as hepdata_lib enforces naming that follows table_name 
    if(len(set(actually_required_yamls_one))!=len(set(actually_required_yamls_two))):
        raise ValueError(f"Different number of required 'yaml' files detected. '{dir_one}' has {len(set(actually_required_yamls_one))} ({set(actually_required_yamls_one)}) while '{dir_two}' has ({len(set(actually_required_yamls_two))}) ({set(actually_required_yamls_two)}).")
    # the actuall names of the additional_resources can varry as hepdata_lib enforces naming that follows table_name 
    if(len(set(actually_required_additional_one))!=len(set(actually_required_additional_two))):
        raise ValueError(f"Different number of 'additional_resources' files detected. '{dir_one}' has {len(set(actually_required_yamls_one))} ({set(actually_required_yamls_one)}) while '{dir_two}' has {len(set(actually_required_yamls_two))} ({set(actually_required_yamls_two)})")
    
    console.print(f" -> [bold] passed!")
    console.rule("Compare table names ",characters="-")
    with console.status(f"Reading names of tables, variables and errors associated with submission files {dir_one}"):
        names_one=get_names_down_to_errors(submission_one)
    with console.status(f"Reading names of tables, variables and errors associated with submission files {dir_two}"):
        names_two=get_names_down_to_errors(submission_two)
    tables_one=list(names_one['tables'].keys())
    tables_two=list(names_two['tables'].keys())
    if(tables_one!=tables_two):
        raise ValueError(f"Tables present have different names. '{dir_one}' has {tables_one} while '{dir_two}' has {tables_two}")
    console.print(f" -> [bold] passed!")

    console.rule("Compare variable names in all table",characters="-")
    independent_variables_one=jq.all('.tables[].independent_variables | keys_unsorted',names_one)
    independent_variables_two=jq.all('.tables[].independent_variables | keys_unsorted ',names_two)
    if(independent_variables_one!=independent_variables_two):
        raise ValueError(f"Independent variables have different names! '{dir_one}' has {independent_variables_one} while '{dir_two}' has {independent_variables_two}")

    dependent_variables_one=jq.all('.tables[].dependent_variables | keys_unsorted ',names_one)
    dependent_variables_two=jq.all('.tables[].dependent_variables | keys_unsorted ',names_two)
    if(dependent_variables_one!=dependent_variables_two):
        raise ValueError(f"Dependent variables have different names! '{dir_one}' has {dependent_variables_one} while '{dir_two}' has {dependent_variables_two}")
    console.print(f" -> [bold] passed!")

    console.rule("Compare error names in all table",characters="-")
    errors_one=jq.all('.tables[].independent_variables[].errors?',names_one)+jq.all('.tables[].dependent_variables[].errors?',names_one)
    errors_two=jq.all('.tables[].independent_variables[].errors?',names_two)+jq.all('.tables[].dependent_variables[].errors?',names_two)
    if(errors_one!=errors_two):
        raise ValueError(f"Errors have different names! '{dir_one}' has {errors_one} while '{dir_two}' has {errors_two}")
    console.print(f" -> [bold] passed!")


if __name__ == '__main__':
    compare_submissions()
