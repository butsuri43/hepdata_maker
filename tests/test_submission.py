import pytest
from hepdata_maker.Submission import Uncertainty
from hepdata_maker.Submission import Variable
from hepdata_maker.Submission import Table
from hepdata_maker.Submission import Submission
import copy
import numpy as np
import jsonschema
import os.path

# 
# See https://stackoverflow.com/a/431747 (from where working_directory function was copied)
# Code below provides a safe way to change working dir
# We need this to check outputs produced by create_hepdata_record
import os
from contextlib import contextmanager    
@contextmanager
def working_directory(directory):
    owd = os.getcwd()
    try:
        os.chdir(directory)
        yield directory
    finally:
        os.chdir(owd)


@pytest.fixture
def sub_ex1():
    return Submission()

def test_submission_constructor(sub_ex1):
    assert sub_ex1.tables==[]
    assert sub_ex1._config=={}

def test_add_tab_to_dict_safely_raise(sub_ex1):
    tab=Table("test_table1")
    sub_ex1._add_tab_to_dict_safely(tab)
    assert "test_table1" in sub_ex1.__dict__
    with pytest.raises(ValueError):
        sub_ex1._add_tab_to_dict_safely(tab) # Adding the same table should rise an error
    with pytest.raises(TypeError):
        sub_ex1._add_tab_to_dict_safely({"name":"this should not work"})

@pytest.fixture
def variable_ex1():
    var=Variable([1.,2.,3.,4.,5.,6.5],"test_var1")
    unc1=Uncertainty([0.1,0.2,0.3,0.4,0.5,0.65],"test1_err")
    unc2=Uncertainty(2*unc1,"test2_err")
    var.add_uncertainty(unc1)
    var.add_uncertainty(unc2)
    return var

@pytest.fixture
def variable_ex2():
    var=Variable([1,2],"test_var2")
    return var

@pytest.fixture
def variable_ex3():
    var=Variable([3,4],"test_var3")
    return var

@pytest.fixture
def variable_ex4():
    var=Variable([9,3,0],"test_var4")
    return var

@pytest.fixture
def table_ex1(variable_ex1):
    tab=Table("test_table1")
    tab.add_variable(variable_ex1)
    return tab

@pytest.fixture
def table_ex2(variable_ex2):
    tab=Table("test_table2")
    tab.add_variable(variable_ex2)
    return tab

@pytest.fixture
def table_ex3(variable_ex3):
    tab=Table("test_table3")
    tab.add_variable(variable_ex3)
    return tab

@pytest.fixture
def table_ex4(variable_ex4):
    tab=Table("test_table4")
    tab.add_variable(variable_ex4)
    return tab

@pytest.fixture
def sub_ex2(table_ex1,table_ex2):
    sub=Submission()
    sub.add_table(table_ex1)
    sub.add_table(table_ex2)
    return sub

def test_add_table(sub_ex1,table_ex1):
    sub_ex1.add_table(table_ex1)
    assert sub_ex1.tables[0].name=='test_table1'
    assert len(sub_ex1.tables[0].variables)==1

def test_add_table_raise(sub_ex1,table_ex1):
    with pytest.raises(TypeError):
        sub_ex1.add_table({"name":"should fail"}) # adding object that is not a table rises an error
    
def test_get_table_names(sub_ex2):
    assert sub_ex2.get_table_names()==['test_table1','test_table2']

def test_table_index(sub_ex2):
    assert sub_ex2.table_index("test_table1")==0
    assert sub_ex2.table_index("test_table2")==1
    sub_ex2.delete_table("test_table1")
    assert sub_ex2.table_index("test_table2")==0
    with pytest.raises(ValueError):
        sub_ex2.table_index("test_table1")

def test_update_table(sub_ex2,table_ex2,caplog):
    # 1) make sure update works as expecte
    table_ex1b=Table("test_table1")
    table_ex1b.add_variable(Variable([4,3],"test_var3"))
    sub_ex2.update_table(table_ex1b)
    assert "test_table1" in sub_ex2.get_table_names()
    assert table_ex1b==sub_ex2.tables[sub_ex2.get_table_names()=="test_table1"]
    assert np.all(sub_ex2.tables[sub_ex2.get_table_names()=="test_table1"].variables[0]==[4,3])
    assert "test_table1" in sub_ex2.__dict__

    # 2) Make sure that even when name is new for table, it is going to propagate (albeit with a warning)
    tab3=Table("test_table3")
    sub_ex2.update_table(tab3)
    assert 'no table of such name found' in caplog.text
    assert tab3.name in sub_ex2.get_table_names()
    assert tab3.variables==sub_ex2.tables[sub_ex2.table_index(tab3.name)].variables
    assert len(sub_ex2.tables)==3
    assert "test_table3" in sub_ex2.__dict__

def test_update_table_raise(sub_ex1):
    with pytest.raises(TypeError):
        sub_ex1.update_table({"name":"should fail"})

def test_delete_table(sub_ex2,caplog):
    # 1) delete test_var1
    sub_ex2.delete_table("test_table1")
    assert "test_table1" not in sub_ex2.get_table_names()
    assert "test_table1" not in sub_ex2.__dict__

    # 2) see warning if test_table1 tried to removed again:
    assert "that is not found in the submission" not in caplog.text 
    sub_ex2.delete_table("test_table1")
    assert "that is not found in the submission" in caplog.text 

    #3) verify no more tables present
    sub_ex2.delete_table("test_table2")
    assert len(sub_ex2.tables)==0

def test_replace_tables(sub_ex2,table_ex3,table_ex4):
    sub_ex2.tables=[table_ex3,table_ex4]
    assert "test_table1" not in sub_ex2.get_table_names()
    assert "test_table1" not in sub_ex2.__dict__

    assert "test_table3" in sub_ex2.get_table_names()
    assert "test_table4" in sub_ex2.get_table_names()
    assert "test_table3" in sub_ex2.__dict__
    assert "test_table4" in sub_ex2.__dict__

    assert np.all(table_ex3==sub_ex2.tables[0])
    assert np.all(table_ex4==sub_ex2.tables[1])

def test_replace_tables_raise(sub_ex1,table_ex1):
    with pytest.raises(TypeError):
        sub_ex1.tables=[table_ex1,{"name":"This should fail"}]

def test_read_table_config(datadir,sub_ex1):
    sub_ex1.read_table_config(datadir.join("basic_example.json"))
    assert True

@pytest.mark.parametrize("submission_file",["/this/path/does/not/exist",
                                            "should_fail/not_json_steering_file.json"
                                            ]
                         )
def test_read_table_config_raise_ValueError(datadir,sub_ex1,submission_file):
    with pytest.raises(ValueError):
        sub_ex1.read_table_config(datadir.join(submission_file,abs=1)) # in the case for absolute submission_file the datadir path is ignored! 

@pytest.mark.parametrize("submission_file",[["this/is/list/"]])
def test_read_table_config_raise_TypeError(sub_ex1,submission_file):
    with pytest.raises(TypeError):
        sub_ex1.read_table_config(submission_file)

def test_load_table_config_basic_example(datadir,sub_ex1):
    sub_ex1.read_table_config(datadir.join("basic_example.json"))
    sub_ex1.load_table_config()
    assert len(sub_ex1.tables)==1
    assert sub_ex1.get_table_names()==['table1_name']
    assert sub_ex1.tables[0].title=="Description of table1"
    assert sub_ex1.tables[0].location=="Where can it be located in the corresponding publication?"
    assert set(sub_ex1.tables[0].keywords.keys())==set(['observables','cmenergies','phrases','reactions'])
    assert len(sub_ex1.tables[0].variables)==3
    assert np.all(sub_ex1.tables[0].variables[0].name=='mt')
    assert np.all(sub_ex1.tables[0].variables[0]==[1,2,3])
    assert np.all(sub_ex1.tables[0].variables[1].name=='mn')
    assert np.all(sub_ex1.tables[0].variables[1]==[2,3,4])
    assert np.all(sub_ex1.tables[0].variables[2].name=='XsecUL')
    assert np.all(sub_ex1.tables[0].variables[2]==[3.1,3.2,3.3])

def test_load_table_config_should_be_processed(datadir,sub_ex1):
    sub_ex1.read_table_config(datadir.join("basic_example.json"))
    sub_ex1._config['tables'][0]['should_be_processed']=False
    sub_ex1.load_table_config()
    assert len(sub_ex1.tables)==0

def test_load_table_config_selected_table_names(datadir,sub_ex1):
    sub_ex1.read_table_config(datadir.join("basic_example.json"))
    sub_ex1._config['tables'].append(copy.copy(sub_ex1._config['tables'][0]))
    sub_ex1._config['tables'][1]['name']='table2_name'
    print(sub_ex1._config)
    sub_ex1.load_table_config(selected_table_names=[('table2_name',True)])
    print([x.name for x in sub_ex1.tables])
    assert len(sub_ex1.tables)==1
    assert sub_ex1.tables[0].name=='table2_name'

def test_load_table_config_double_load(datadir,sub_ex1,caplog):
    sub_ex1.read_table_config(datadir.join("basic_example.json"))
    sub_ex1.load_table_config()
    with pytest.raises(ValueError):
        sub_ex1.load_table_config() # loading of the same file should raise an error
    assert "You have already loaded information from a(nother?) steering file" in caplog.text

def test_load_table_config_double_load_v2(datadir,sub_ex1,caplog):
    sub_ex1.read_table_config(datadir.join("basic_example.json"))
    sub_ex1.load_table_config()
    print(sub_ex1._config['tables'])
    # Not a normal usecasel, but 
    # should be fine with other table name
    sub_ex1._config['tables'][0]['name']='table2_name'
    sub_ex1.load_table_config()
    assert set(sub_ex1.get_table_names())==set(['table1_name','table2_name'])

@pytest.mark.parametrize("submission_file",["should_fail/not_readable_image_file.json",
                                            "should_fail/not_readable_data_file.json",
                                            "should_fail/not_readable_error_file.json"
                                            ]
                         )
def test_load_table_config_raise_ValueError(datadir,sub_ex1,submission_file):
    sub_ex1.read_table_config(datadir.join(submission_file))
    with pytest.raises(ValueError):
        sub_ex1.load_table_config()


def test_load_table_config_table_description(datadir,sub_ex1):
    sub_ex1.read_table_config(datadir.join("table_description_example.json"))
    with working_directory(datadir):
        sub_ex1.load_table_config()
        assert sub_ex1.tables[0].title=="""Here is table description.
It can be attached to steering file. For example
{
    "type": "submission",
    "tables":
    [
	{
            "name":"table1_name",
            "title":"table_description_file.txt"
	}
    ]
}
"""
        assert sub_ex1.tables[1].title=="This is normal title"


@pytest.mark.parametrize("forbidden_name",["dolar_$_is_not_allowed",
                                            "exclamation_!_is_not_allowed",
                                            "quotation_mark_\"_is_not_allowed",
                                            "brackets_(_are_not_allowed",
                                            "and_#%&'()*+,-/:<=>?@[]\\^`_many_more_are_forbidden"]
                         )
def test_load_table_config_table_names_raise(sub_ex1,forbidden_name):
    with pytest.raises(jsonschema.exceptions.ValidationError):    
        sub_ex1.config={
            "type":"submission",
            "tables":[
                {
                    "name":forbidden_name
                }
            ]
        }
@pytest.mark.parametrize("allowed_name",["letters_BIG_and_small",
                                          "underscores_",
                                          "numbers_0123456789",
                                          "should_not_be_but_dot_._is_allowed_too",
                                          "slash_/",
                                          "semicolon_;"])
def test_load_table_config_table_names(sub_ex1,allowed_name):
    sub_ex1.config={
        "type":"submission",
        "tables":[
            {
                "name":allowed_name
            }
        ]
    }
    sub_ex1.load_table_config()
    assert sub_ex1.tables[0].name==allowed_name


@pytest.mark.parametrize("submission_file",["basic_example.json",
                                            "table_description_example.json"])
def test_create_hepdata_record(datadir,tmp_path,sub_ex1,submission_file):

    sub_ex1.read_table_config(datadir.join(submission_file))
    with working_directory(datadir):
        sub_ex1.load_table_config()
        sub_ex1.create_hepdata_record()
        assert os.path.isdir('submission_files')
        assert os.path.isfile('submission.tar.gz')
    """
    directory_with_example_file=os.path.dirname(os.path.abspath(submission_file))
    path_link_to_directory_with_example=tmp_path/os.path.basename(directory_with_example_file)
    path_link_to_directory_with_example.symlink_to(directory_with_example_file)

    print(str(tmp_path))
    with working_directory(str(tmp_path)):
        cwd = os.getcwd()
        print(cwd)
        sub_ex1.read_table_config(submission_file)
        sub_ex1.load_table_config(data_root=data_root)
        sub_ex1.create_hepdata_record()
        assert (tmp_path/'submission_files').is_dir()
        assert (tmp_path/'submission.tar.gz').is_file()
    """
