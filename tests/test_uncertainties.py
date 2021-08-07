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

@pytest.mark.filterwarnings("ignore::numpy.VisibleDeprecationWarning")
@pytest.mark.parametrize("error_data,error_name", [([1,[2,3],4],""),
                                                   ([1,2,3,4],["this should fail"]),
                                                   ([[[1,2],[2,3]],[[3,4],[5,6]]],""),
                                                   (23,"test")])
def test_uncertainty_constructor_raise_TypeError(error_data,error_name):
    with pytest.raises(TypeError):
        Uncertainty(error_data,error_name)
