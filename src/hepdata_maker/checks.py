#
# Most of the code in this file was taken from 'check.py' from https://hepdata-submission.readthedocs.io/en/latest/tips.html:
# https://hepdata-submission.readthedocs.io/en/latest/_downloads/3623abae3e9b3aa92c8493b05315cc7e/check.py
#
# The functions here do basic validation of HEPData submission files 
#

from hepdata_validator.submission_file_validator import SubmissionFileValidator # type: ignore 
from hepdata_validator.data_file_validator import DataFileValidator             # type: ignore
from yaml import CSafeLoader as Loader # type: ignore
import yaml # type: ignore
import json
from .logs import logging
import os.path
from typing import Dict,Any,Optional

log = logging.getLogger(__name__)

def validate_data_yaml(data_yaml: Dict[str,Any],
                       data_file_path: Optional[str]=None) -> bool:
    # Check that the length of the 'values' list is consistent for
    # each of the independent_variables and dependent_variables.
    indep_count = [len(indep['values']) for indep in data_yaml['independent_variables']]
    dep_count = [len(dep['values']) for dep in data_yaml['dependent_variables']]
    if len(set(indep_count + dep_count)) > 1: # if more than one unique count
        raise ValueError("%s has inconsistent length of 'values' list: " % data_file_path +
                         "independent_variables%s, dependent_variables%s." % (str(indep_count), str(dep_count)))
    return True

def validate_data_file(data_file_path: str) -> bool :
    # Just try to load YAML data file without validating schema.
    # Script will terminate with an exception if there is a problem.
    contents = yaml.load(open(data_file_path, 'r'), Loader=Loader)

    data_file_validator = DataFileValidator()
    is_valid_data_file = data_file_validator.validate(file_path=data_file_path, data=contents)
    if not is_valid_data_file:
        raise ValueError(f"Data file {data_file_path} is not a valid hepdata data file. Errors from DataFileValidator:",
                         *[x.message for x in  data_file_validator.get_messages()[data_file_path]])
    validate_data_yaml(contents)
    return True
    
def validate_submission(submission_file_path: str) -> bool:
    directory=os.path.dirname(submission_file_path)
    submission_file_validator = SubmissionFileValidator()
    is_valid_submission_file = submission_file_validator.validate(file_path=submission_file_path)
    if not is_valid_submission_file:
        raise ValueError(f"Submission file {submission_file_path} is not a valid hepdata submission.yaml file. Errors from SubmissionFileValidator:",
                         *[x.message for x in  submission_file_validator.get_messages()[submission_file_path]])

    
    # Open the submission.yaml file and load all YAML documents.
    with open(submission_file_path, 'r') as stream:
        docs = list(yaml.load_all(stream, Loader=Loader))

    # Loop over all YAML documents in the submission.yaml file.
    for doc in docs:

        # Skip empty YAML documents.
        if not doc:
            continue

        # Check for presence of local files given as additional_resources.
        if 'additional_resources' in doc:
            for resource in doc['additional_resources']:
                if not resource['location'].startswith('http'):
                    location = os.path.join(directory, resource['location'])
                    if not os.path.isfile(location):
                        raise ValueError('File %s is missing.' % location)
                    elif '/' in resource['location']:
                        raise ValueError('File %s should not contain "/".' % resource['location'])

        # Check for non-empty YAML documents with a 'data_file' key.
        elif 'data_file' in doc:

            # Check for presence of '/' in data_file value.
            if '/' in doc['data_file']:
                raise ValueError('%s should not contain "/".' % doc['data_file'])

            
            # Extract data file from YAML document.
            data_file_path = directory + '/' + doc['data_file'] if directory else doc['data_file']
            validate_data_file(data_file_path)

        elif('comment' in doc):
            log.debug(f"comment section present in {submission_file_path}")
        else:
            """
            # For now single-file submissions (with data inside submission.yaml) are not supported by submission_maker.
            # Those files do not pass SubmissionFileValidator thus no intention to support them! 
            
            elif('independent_variables' in doc and 'dependent_variables' in doc):
            validate_data_yaml({'independent_variables': doc.pop('independent_variables', None),
            'dependent_variables': doc.pop('dependent_variables', None)})
            """
            raise ValueError(f"Unrecognised yaml section in submission.yaml file {submission_file_path}. The problematic part: {doc}")
    return True
