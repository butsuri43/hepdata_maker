import pytest
from hepdata_maker.Submission import Table
from hepdata_maker.Submission import Variable
from hepdata_maker.Submission import Uncertainty
from hepdata_maker.Submission import add_error_tree_from_var
from hepdata_maker.Submission import add_var_tree_from_table
from hepdata_maker.Submission import print_dict_highlighting_objects
from rich.tree import Tree

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

base_tree_table1 = Tree("test_table1")

base_tree_variable1=Tree("test_var1 (var)")


@pytest.mark.parametrize("base_tree", [base_tree_variable1, None])
def test_tree_error_from_var(variable_ex1,base_tree):
    result=add_error_tree_from_var(variable_ex1,base_tree)
    assert result.label=='test_var1 (var)'
    assert len(result.children)==2
    assert result.children[0].label=='test_var1.test1_err (err)'
    assert result.children[1].label=='test_var1.test2_err (err)'

@pytest.mark.parametrize("variable_test,base_tree_test", [(variable_ex1,{"test":"this should fail (not rich.tree.Tree)"}),
                                                       (Table("this should fail (not Variable)"),base_tree_variable1),
                                                       ("this should fail (not Variable)",base_tree_variable1)])
def test_tree_err_from_variable_raise(variable_test,base_tree_test):
    with pytest.raises(ValueError):
        add_error_tree_from_var(variable_test,base_tree_test)

@pytest.mark.parametrize("base_tree", [base_tree_table1, None])
def test_tree_var_from_table(table_ex1,base_tree):
    result=add_var_tree_from_table(table_ex1,base_tree)
    assert result.label=='test_table1'
    assert len(result.children)==1
    assert result.children[0].label.label=='test_table1.test_var1 (var)'

@pytest.mark.parametrize("table_test,base_tree_test", [(table_ex1,{"test":"this should fail (not rich.tree.Tree)"}),
                                                       (Variable([],"this should fail (not Table)"),base_tree_table1),
                                                       ("this should fail (not Table)",base_tree_table1)])
def test_tree_var_from_table_raise(table_test,base_tree_test):
    with pytest.raises(ValueError):
        add_var_tree_from_table(table_test,base_tree_test)

@pytest.mark.parametrize("dictionary,title",[(["This should fail"],""),
                                             ("This should fail too","test"),
                                             ({"name":"test"},["this should fail"])
                                             ])
def test_print_dict_highligh_raise(dictionary,title):
    with pytest.raises(ValueError):
        print_dict_highlighting_objects(dictionary,title)


def test_print_dict_highligh():
    assert print_dict_highlighting_objects({"test":"myobject"},"my title") is None

