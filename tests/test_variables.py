import pytest
from hepdata_maker.Submission import Uncertainty
from hepdata_maker.Submission import Variable
import numpy as np

@pytest.mark.parametrize("var_data,var_name,is_binned",
                         [([1,2],"",False),
                          ([1,2],None,False),
                          ([0.1,0.2],"test",False),
                          ([],"test",False),
                          ([[0,1],[1,2]],"test",True),
                          ([["0","1"],["2","1"]],"test",True),
                          (np.array([1,2],dtype=object),"test",False)]
                         )
def test_variable_constructor(var_data,var_name,is_binned):
    var=Variable(var_data,var_name,is_binned=is_binned)
    assert var.name==var_name
    assert var.is_visible==True
    assert var.ndim==np.array(var_data).ndim
    assert var.is_binned==is_binned


@pytest.mark.filterwarnings("ignore::numpy.VisibleDeprecationWarning")
@pytest.mark.parametrize("var_data,var_name,is_binned", [([1,2,3,4],["this should fail"],False),   # array instead of string for the name
                                                         ([[[1,2],[2,3]],[[3,4],[5,6]]],"",False), # 3-D input array
                                                         (23,"",False)])                           # 0-D input array
def test_variable_constructor_raise_TypeError(var_data,var_name,is_binned):
    with pytest.raises(TypeError):
        Variable(var_data,var_name,is_binned=is_binned)

@pytest.mark.filterwarnings("ignore::numpy.VisibleDeprecationWarning")
@pytest.mark.parametrize("var_data,var_name,is_binned", [([1,[2,3],4],"",False),                   # unspecified dimensionality of the data_array
                                                         ])
def test_variable_constructor_raise_ValueError(var_data,var_name,is_binned):
    with pytest.raises(ValueError):
        Variable(var_data,var_name,is_binned=is_binned)

@pytest.mark.parametrize("error_data,error_name",[([1,2],""),
                                                  ([0.1,-0.1],"test"),
                                                  (["1","2.2"],"test")
                                                  ])
def test_add_uncertainty(error_data,error_name):
    var=Variable([1,2],"")
    unc1=Uncertainty(error_data,error_name)
    var.add_uncertainty(unc1)
    assert len(var.uncertainties)==1
    assert var.uncertainties[0].name==error_name
    assert np.all(var.uncertainties[0]==unc1) # those are really just numpy arrays
    assert error_name in var.__dict__

def test_add_uncertainty_raise_dim():
    var=Variable([1,2],"")
    unc1=Uncertainty([0.1,0.2,0.3,0.4,0.5,0.65],"test1_err")
    with pytest.raises(ValueError):
        var.add_uncertainty(unc1) # different dimentionality to Variable
        
def test_add_uncertainty_raise_name():
    var=Variable([1,2],"")
    unc1=Uncertainty([0.1,0.2],"test1_err")
    unc2=Uncertainty([0.1,0.2],"test1_err")    
    var.add_uncertainty(unc1)
    with pytest.raises(ValueError):
        var.add_uncertainty(unc2) # the uncertainty of this name already exists! 

def test_add_uncertainty_raise_wrongObject():
    var=Variable([1,2],"")
    with pytest.raises(TypeError):
        var.add_uncertainty([1,2]) # need Uncertainty object and nothing else

@pytest.fixture
def variable_ex1():
    var=Variable([1.,2.,3.,4.,5.,6.5],"test_var1")
    unc1=Uncertainty([0.1,0.2,0.3,0.4,0.5,0.65],"test1_err")
    unc2=Uncertainty(2*unc1,"test2_err")
    var.add_uncertainty(unc1)
    var.add_uncertainty(unc2)
    return var

def test_get_uncertainty_names(variable_ex1):
    assert variable_ex1.get_uncertainty_names()==['test1_err','test2_err']

def test_uncertainty_index(variable_ex1):
    assert variable_ex1.uncertainty_index("test1_err")==0
    assert variable_ex1.uncertainty_index("test2_err")==1
    variable_ex1.delete_uncertainty("test1_err")
    assert variable_ex1.uncertainty_index("test2_err")==0
    with pytest.raises(ValueError):
        variable_ex1.uncertainty_index("test1_err")

def test_update_uncertainty(variable_ex1,caplog):
    # 1) make sure update works as expecte
    unc1=variable_ex1.uncertainties[0]
    unc3=Uncertainty(np.negative(unc1),"test1_err")
    variable_ex1.update_uncertainty(unc3)
    assert unc3.name in variable_ex1.get_uncertainty_names()
    assert np.all(unc3==variable_ex1.uncertainties[variable_ex1.get_uncertainty_names()==unc3.name])
    assert "test1_err" in variable_ex1.__dict__

    # 2) Make sure that even when name is new for variable, it is going to propagate (albeit with a warning)
    unc4=Uncertainty(unc3,"test4_err")
    variable_ex1.update_uncertainty(unc4)
    assert 'no uncertainty of such name found' in caplog.text
    assert unc4.name in variable_ex1.get_uncertainty_names()
    assert np.all(unc4==variable_ex1.uncertainties[variable_ex1.get_uncertainty_names()==unc4.name])
    assert len(variable_ex1.uncertainties)==3
    assert "test4_err" in variable_ex1.__dict__

def test_update_uncertainty_raise(variable_ex1):
    with pytest.raises(TypeError):
        variable_ex1.update_uncertainty({"name":"should fail"})

def test_replace_uncertainties(variable_ex1):
    unc1=variable_ex1.uncertainties[0]
    unc3=Uncertainty(np.negative(unc1),"test3_err")
    unc4=Uncertainty(2*unc3,"test4_err")
    variable_ex1.uncertainties=[unc3,unc4]
    assert "test1_err" not in variable_ex1.get_uncertainty_names()
    assert "test2_err" not in variable_ex1.get_uncertainty_names()
    assert "test1_err" not in variable_ex1.__dict__
    assert "test2_err" not in variable_ex1.__dict__

    assert "test3_err" in variable_ex1.get_uncertainty_names()
    assert "test4_err" in variable_ex1.get_uncertainty_names()
    assert "test3_err" in variable_ex1.__dict__
    assert "test4_err" in variable_ex1.__dict__

    assert np.all(unc3==variable_ex1.uncertainties[0])
    assert np.all(unc4==variable_ex1.uncertainties[1])

def test_replace_uncertainties_raise(variable_ex1):
    unc1=variable_ex1.uncertainties[0]
    unc3=Uncertainty(np.negative(unc1),"test3_err")
    with pytest.raises(TypeError):
        variable_ex1.uncertainties=[unc3,{"name":"This should fail"}]
    
def test_delete_uncertainty(variable_ex1,caplog):
    # 1) delete test1_err
    variable_ex1.delete_uncertainty("test1_err")
    assert "test1_err" not in variable_ex1.get_uncertainty_names()
    assert "test1_err" not in variable_ex1.__dict__

    # 2) see warning if test1_err tried to removed again:
    assert "that is not found in the variable" not in caplog.text 
    variable_ex1.delete_uncertainty("test1_err")
    assert "that is not found in the variable" in caplog.text 

    #3) remove the remaining uncertainty 
    variable_ex1.delete_uncertainty("test2_err")
    assert "test2_err" not in variable_ex1.get_uncertainty_names()
    assert "test2_err" not in variable_ex1.__dict__
    assert len(variable_ex1.uncertainties)==0

def test_add_unc_to_dict_safely_raise(variable_ex1):
    unc1=Uncertainty([0.1,0.2],"test1_err")
    with pytest.raises(ValueError):
        variable_ex1._add_unc_to_dict_safely(unc1)
    with pytest.raises(TypeError):
        variable_ex1._add_unc_to_dict_safely(variable_ex1)

