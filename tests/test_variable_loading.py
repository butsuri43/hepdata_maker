import pytest
from hepdata_maker.variable_loading import get_array_from_json
from hepdata_maker.variable_loading import get_array_from_yaml
import numpy as np


def test_jq_behaviour_modification(datadir):

    submission_file=datadir.join("jq_mod_test.json")
    json_out_1=get_array_from_json(submission_file,"keys")
    json_out_2=get_array_from_json(submission_file,"keys | .[]")
    assert np.all(json_out_1==json_out_2)

    submission_file=datadir.join("jq_mod_test.yaml")
    yaml_out_1=get_array_from_yaml(submission_file,"keys")
    yaml_out_2=get_array_from_yaml(submission_file,"keys | .[]")
    assert np.all(yaml_out_1==yaml_out_2)
