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

@pytest.mark.parametrize("unc_steering,global_variables,local_variables",[({"name":"test_unc",
                                                                            "transformations":["[1,2]"]
                                                                            },{},{}),
                                                                          ({"name":"test_unc",
                                                                            "transformations":["other_var"]},
                                                                           {"other_var":[1,2]},{}),
                                                                          ({"name":"test_unc",
                                                                            "transformations":["other_var"]},
                                                                          {},{"other_var":[1,2]})
                                                                          ])
def test_uncertainty_constructor_steering_file(unc_steering,global_variables,local_variables):
    unc=Uncertainty(unc_steering=unc_steering,
                    global_variables=global_variables,
                    local_variables=local_variables)
    assert unc.name=="test_unc"
    assert unc.is_visible==True
    assert unc.ndim==1
    assert unc.is_symmetric==True
    assert np.all(unc==[1,2])

@pytest.mark.filterwarnings("ignore::numpy.VisibleDeprecationWarning")
@pytest.mark.parametrize("error_data,error_name", [([1,[2,3],4],""),
                                                   ([1,2,3,4],["this should fail"]),
                                                   ([[[1,2],[2,3]],[[3,4],[5,6]]],""),
                                                   (23,"test")])
def test_uncertainty_constructor_raise_TypeError(error_data,error_name):
    with pytest.raises(TypeError):
        Uncertainty(error_data,error_name)
