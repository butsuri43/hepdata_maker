import pytest
from hepdata_maker.Submission import Uncertainty
from hepdata_maker.Submission import Variable
from hepdata_maker.Submission import Table
import numpy as np

@pytest.mark.parametrize("tab_name",["test",
                                     ""])
def test_table_constructor(tab_name):
    tab=Table(tab_name)
    assert tab.name==tab_name

@pytest.mark.parametrize("tab_steering,global_variables,local_variables",
                         [(
                             {
                                 "name":"test_tab",
                                 "fancy_name":"this could be $\\LaTeX$",
                                 "should_be_processed":True,
                                 "title":"title of the table; put into HEPData",
                                 "location":"Location of the table on the paper website",
                                 "images":[{"name":"input_example4.pdf"}],
                                 "additional_resources":[{"description":"example of additional resources","location":"dumb_tarball.tar.gz"}],
                                 "keywords":{"cmenergies":["13000"],"phrases":"dummy_data"},
                                 "variables":[
                                     {
                                         "name":"x-value",
                                         "in_files":[
                                             {
                                                 "name":"input_example4.root:test_histo1",
                                                 "decode":"x_edges"
                                             }
                                         ]
                                     },
                                     {
                                         "name":"y-value",
                                         "in_files":[
                                            {
                                                "name":"input_example4.root:test_histo1",
                                                "decode":"y"
                                            }
                                         ],
                                         "errors":[
                                             {
                                                 "name":"test_unc",
                                                 "in_files":[
                                                     {
                                                         "name":"input_example4.root:test_histo1",
                                                         "decode":"dy"
                                                     }
                                                 ]
                                             }
                                         ]
                                     }

                                 ],
                                 "comment":""
                              }
                             ,{},{})
                          ])
def test_variable_constructor_steering_file(datadir,tab_steering,global_variables,local_variables):
    # Provide correct paths for data directory:
    if('in_files' in tab_steering):
        for index in range(len(tab_steering['in_files'])):
            tab_steering['in_files'][index]['name']=str(datadir.join(tab_steering['in_files'][index]['name']))

    tab=Table(tab_steering=tab_steering,
              global_variables=global_variables,
              local_variables=local_variables,
              data_root=datadir)
    assert tab.name=="test_tab"
    assert len(tab.variables)==2
    assert tab.variables[0].is_binned==True
    assert np.all(tab.variables[1].uncertainties[0]==[1.,2.])
    snippet=tab.steering_file_snippet()
    check_fields=['should_be_processed','title',"location","images","additional_resources","variables",'fancy_name','name',"data_type"]
    for field_name in check_fields:
        if(field_name in tab_steering):
            assert tab_steering[field_name]==snippet[field_name]


@pytest.mark.parametrize("tab_name",[None, # Table has to have a name
                                     65*["x"]] # Table name cannot be larger than 64 characters 
                         )
def test_table_constructor_raise(tab_name):
    with pytest.raises(TypeError):
        Table(tab_name)

@pytest.fixture
def variable_ex1():
    var=Variable([1.,2.,3.,4.,5.,6.5],"test_var1")
    unc1=Uncertainty([0.1,0.2,0.3,0.4,0.5,0.65],"test1_err")
    unc2=Uncertainty(2*unc1,"test2_err")
    var.add_uncertainty(unc1)
    var.add_uncertainty(unc2)
    return var

@pytest.fixture
def table_ex1(variable_ex1):
    tab=Table("test_table1")
    tab.add_variable(variable_ex1)
    return tab

def test_get_variable_names(table_ex1):
    assert table_ex1.get_variable_names()==['test_var1']

def test_variable_index(table_ex1):
    var2=Variable(table_ex1.variables[0],"test_var2")
    table_ex1.add_variable(var2)
    assert table_ex1.variable_index("test_var1")==0
    assert table_ex1.variable_index("test_var2")==1
    table_ex1.delete_variable("test_var1")
    assert table_ex1.variable_index("test_var2")==0
    with pytest.raises(ValueError):
        table_ex1.variable_index("test_var1")


def test_add_var_to_dict_safely_raise(table_ex1):
    var=Variable([1.,2.,3.],"test_var1")
    with pytest.raises(ValueError):
        table_ex1._add_var_to_dict_safely(var)
    with pytest.raises(TypeError):
        table_ex1._add_var_to_dict_safely({"name":"this should not work"})

def test_name_raise(table_ex1):
    with pytest.raises(ValueError):
        table_ex1.name=['x']*65

@pytest.mark.parametrize("var_data,var_name,is_binned",[([1,2,3,4,5,6],"",False),
                                              ([1,2,3,4,5,6],"test",False),
                                              (["1","2","3","4","5","6"],"test",False),
                                              ([[1,2],[2,3],[3,4],[4,5],[5,6],[6,7]],"test_binned",True)
                                              ])
def test_add_variable(table_ex1,var_data,var_name,is_binned):
    #1) check plain variable addition
    var=Variable(var_data,var_name,is_binned=is_binned)
    table_ex1.add_variable(var)
    assert len(table_ex1.variables)==2
    assert table_ex1.variables[1].name==var_name
    assert np.all(table_ex1.variables[1]==var_data) 

    #2) Not-visible variable can be of any lenght
    var2=Variable([2,3],"hidden",is_visible=False)
    table_ex1.add_variable(var2)
    assert "hidden" in table_ex1.get_variable_names()



def test_add_variable_raise(table_ex1):
    var=Variable([1,2],"")
    #1) Visible variable cannot be added if lenght does not match already included variables
    with pytest.raises(ValueError):
        table_ex1.add_variable(var) # different dimentionality to the already stored variable

    #2) Adding an object different than Variable should raise error
    with pytest.raises(TypeError):
        table_ex1.add_variable({"name":"should fail"})
    

def test_update_variable(table_ex1,caplog):
    # 1) make sure update works as expecte
    var1=table_ex1.variables[0]
    var2=Variable(np.negative(var1),"test_var1")
    table_ex1.update_variable(var2)
    assert var2.name in table_ex1.get_variable_names()
    assert np.all(var2==table_ex1.variables[table_ex1.get_variable_names()==var2.name])
    assert "test_var1" in table_ex1.__dict__

    # 2) Make sure that even when name is new for variable, it is going to propagate (albeit with a warning)
    var3=Variable(var2,"test_var3")
    table_ex1.update_variable(var3)
    print(table_ex1.get_variable_names())
    assert 'no variable of such name found' in caplog.text
    assert var3.name in table_ex1.get_variable_names()
    assert np.all(var3==table_ex1.variables[table_ex1.get_variable_names()==var3.name])
    assert len(table_ex1.variables)==2
    assert "test_var3" in table_ex1.__dict__

def test_update_variable_raise(table_ex1):
    with pytest.raises(TypeError):
        table_ex1.update_variable({"name":"should fail"})

def test_delete_variable(table_ex1,caplog):
    # 1) delete test_var1
    table_ex1.delete_variable("test_var1")
    assert "test_var1" not in table_ex1.get_variable_names()
    assert "test_var1" not in table_ex1.__dict__

    # 2) see warning if test_var1 tried to removed again:
    assert "that is not found in the table" not in caplog.text 
    table_ex1.delete_variable("test_var1")
    assert "that is not found in the table" in caplog.text 

    #3) verify no more variables present
    assert len(table_ex1.variables)==0

def test_replace_variables(table_ex1):
    var1=table_ex1.variables[0]
    var3=Variable(np.negative(var1),"test_var3")
    var4=Variable(2*var3,"test_var4")
    table_ex1.variables=[var3,var4]
    assert "test_var1" not in table_ex1.get_variable_names()
    assert "test_var1" not in table_ex1.__dict__

    assert "test_var3" in table_ex1.get_variable_names()
    assert "test_var4" in table_ex1.get_variable_names()
    assert "test_var3" in table_ex1.__dict__
    assert "test_var4" in table_ex1.__dict__

    assert np.all(var3==table_ex1.variables[0])
    assert np.all(var4==table_ex1.variables[1])

def test_replace_variables_raise(table_ex1):
    var1=table_ex1.variables[0]
    var3=Variable(np.negative(var1),"test3_var")
    with pytest.raises(TypeError):
        table_ex1.variables=[var3,{"name":"This should fail"}]
