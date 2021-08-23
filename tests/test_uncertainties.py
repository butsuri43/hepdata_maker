import pytest
from hepdata_maker.Submission import Uncertainty
import numpy as np

@pytest.mark.parametrize("error_data,error_name", [([1,2,3,4],""),
                                                   ([1,2,3,4],None),
                                                   ([0.1,0.2,0.3,0.4],"total"),
                                                   ([],"test"),
                                                   ([[0,1],[2,1]],"test"),
                                                   ([["0","1"],["2","1"]],"test")]
                         )
def test_uncertainty_constructor(error_data,error_name):
    unc=Uncertainty(error_data,error_name)
    assert unc.name==error_name
    assert unc.is_visible==True
    assert unc.ndim==np.array(error_data).ndim
    assert unc.is_symmetric==(True if np.array(error_data).ndim==1 else False)
    snippet=unc.steering_file_snippet()
    assert snippet['name']==error_name
    assert snippet['transformations'][0]==str(error_data)
    
@pytest.mark.parametrize("unc_steering,global_variables,local_variables",
                         [({"name":"test_unc",
                            "transformations":["[1,2]"]
                            },{},{}),
                          ({"name":"test_unc",
                            "transformations":["other_var"]},
                           {"other_var":[1,2]},{}),
                          ({"name":"test_unc",
                            "transformations":["other_var"]},
                           {},{"other_var":[1,2]}),
                          ({
                              "name":"test_unc",
                              "in_files":[{
                                  "name":"input_example1.json",
                                  "decode":".my_error | .[]"
                              }]
                          },{},{}),
                          ({
                              "name":"test_unc",
                              "in_files":[{
                                  "name":"input_example2.json",
                                  "decode":".variables[0].values[].errors[0].error"
                              }]
                          },{},{}),
                          ({
                              "name":"test_unc",
                              "in_files":[{
                                  "name":"input_example3.yaml",
                                  "decode":".variables[0].values[].errors[0].error"
                              }]
                          },{},{}),
                          ({
                              "name":"test_unc",
                              "in_files":[{
                                  "name":"input_example4.root:test_histo1",
                                  "decode":"dy"
                              }]
                          },{},{}),
                          ({
                              "name":"test_unc",
                              "in_files":[{
                                  "name":"input_example4.root:test_directory/test_histo1_inside_dir",
                                  "decode":"dy"
                              }]
                          },{},{}),
                          ({
                              "name":"test_unc",
                              "in_files":[{
                                  "name":"input_example5.csv",
                                  "delimiter":",",
                                  "decode":"var1_test_unc"
                              }],
                              "data_type":"float",
                          },{},{}),
                          ({
                              "name":"test_unc",
                              "in_files":[{
                                  "name":"input_example6.tex",
                                  "tabular_loc_decode": "latex.find_all(['tabular*','tabular'])[0]",
                                  "replace_dict": {
                                      "\\\\pm": "&"
                                  },
                                  "decode":"table[1:,1]"
                              }],
                              "data_type":"float",
                          },{},{})
                          ])
def test_uncertainty_constructor_steering_file(datadir,unc_steering,global_variables,local_variables):
    # Provide correct paths for data directory:
    if('in_files' in unc_steering):
        for index in range(len(unc_steering['in_files'])):
            unc_steering['in_files'][index]['name']=str(datadir.join(unc_steering['in_files'][index]['name']))

    unc=Uncertainty(unc_steering=unc_steering,
                    global_variables=global_variables,
                    local_variables=local_variables)
    assert unc.name=="test_unc"
    assert unc.is_visible==True
    assert unc.ndim==1
    assert unc.is_symmetric==True
    assert np.all(unc==[1,2])
    snippet=unc.steering_file_snippet()
    check_fields=['in_files','transformations','fancy_name','name']
    for field_name in check_fields:
        if(field_name in unc_steering):
            assert unc_steering[field_name]==snippet[field_name]    

    
@pytest.mark.filterwarnings("ignore::numpy.VisibleDeprecationWarning")
@pytest.mark.parametrize("error_data,error_name", [([1,[2,3],4],""),
                                                   ([1,2,3,4],["this should fail"]),
                                                   ([[[1,2],[2,3]],[[3,4],[5,6]]],""),
                                                   (23,"test")])
def test_uncertainty_constructor_raise_TypeError(error_data,error_name):
    with pytest.raises(TypeError):
        Uncertainty(error_data,error_name)
