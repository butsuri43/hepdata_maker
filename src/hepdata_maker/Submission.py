from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import numpy as np
#import json
import jsonref
from collections import OrderedDict
from collections.abc import Iterable
import collections
import hepdata_lib
import os.path
import regex as re
import scipy.stats, scipy.special
from . import useful_functions as ufs
from . import utils
from .logs import logging
log = logging.getLogger(__name__)
from .console import console
import rich.panel
import rich.tree
from . import variable_loading
import validators

def is_name_correct(name):
    # Just checking whether the name field does not contain forbidden characters
    return re.match("^([a-zA-Z0-9\\._;/+])*$",name) is not None

def add_error_tree_from_var(variable,baseTree=False):
    if(not isinstance(variable,Variable)):
        raise ValueError(f"arugument 'variable' needs to be of type Submission.Variable")
    if(not baseTree):
        baseTree=rich.tree.Tree(variable.name+" (var)")
    if(not isinstance(baseTree,rich.tree.Tree)):
        raise ValueError(f"I require baseTree to be of type rich.tree.Tree (is: {type(baseTree)}).")
    if(len(variable.uncertainties)>0):
        baseTreeLabel=baseTree.label.split()[0]+'.' if len(baseTree.label)>0 else ''
        for err in variable.uncertainties:
            if(not hasattr(err,'name')):
                raise ValueError(f"I need error to has attribute name")
            baseTree.add(baseTreeLabel+err.name+" (err)")
    return baseTree

def add_var_tree_from_table(table,baseTree=False):
    if(not isinstance(table,Table)):
        raise ValueError(f"arugument 'table' needs to be of type Submission.Table")
    if(not baseTree):
        baseTree=rich.tree.Tree(table.name)
    if(not isinstance(baseTree,rich.tree.Tree)):
        raise ValueError(f"I require baseTree to be of type rich.tree.Tree (is: {type(baseTree)}).")
    if(len(table.variables)>0):
        baseTreeLabel=baseTree.label.split()[0]+'.' if len(baseTree.label)>0 else ''
        for var in table.variables:
            spec_var_tree=rich.tree.Tree(baseTreeLabel+str(var.name)+" (var)")
            spec_var_tree=add_error_tree_from_var(var,spec_var_tree)
            baseTree.add(spec_var_tree)
    return baseTree

def perform_transformation(transformation,submission_dict,local_vars):
    try:
        global_vars=utils.merge_dictionaries(submission_dict,{"np":np},{"re":re},{"scipy.stats":scipy.stats},{"scipy.special":scipy.special},{"ufs":ufs})
        return eval(transformation,global_vars,local_vars)
    except Exception as exc:
        log.error(f"Transformation '{transformation}' has failed.")
        log.error(f"Make sure your numpy array data is of the correct type (by specifying 'data-type')!")
        log.error(f"You can use following global variables:")
        print_dict_highlighting_objects(global_vars,title="global variables")
        log.error(f"and local variables:")
        print_dict_highlighting_objects(local_vars,title="local variables")
        raise exc

def print_dict_highlighting_objects(dictionary,title=''):
    log.debug("Inside 'print_dict_highlighting_objects' function")
    if(not isinstance(dictionary,dict)):
        raise ValueError("Object provided to function {__name__} should be dictionary, while it is {type(dictionary)}. Full object for reference: {dictionary}")
    if(not isinstance(title,str)):
        raise ValueError("Title provided to function {__name__} should be string, while it is {type(title)}. Full object for reference: {title}")
    variable_list=[]
    table_list=[]
    other_list=[]
    for key, value in dictionary.items():
        if(isinstance(value,Variable)):
            variable_list.append((key,value))
        if(isinstance(value,Table)):
            table_list.append((key,value))
        else:
            if(not key.startswith("_")): # exclude internal variables
                other_list.append((key,value))
    objects_to_show=[]
    if(len(table_list)>0):
        table_tree=rich.tree.Tree("[bold]Available tables:")        
        for key,value in table_list:
            spec_tab_tree=rich.tree.Tree(key+" (tab)")
            spec_tab_tree=add_var_tree_from_table(value,spec_tab_tree)
            table_tree.add(spec_tab_tree)
        objects_to_show.append(table_tree)
    if(len(variable_list)>0):
        var_tree=rich.tree.Tree("[bold]Available variables:")        
        for key,value in variable_list:
            spec_var_tree=rich.tree.Tree(key+" (var)")
            spec_var_tree=add_error_tree_from_var(value,spec_tab_tree)
            table_tree.add(spec_tab_tree)
        objects_to_show.append(var_tree)
    if(len(other_list)>0):
        other_tree=rich.tree.Tree("[bold]Other objects:")
        for key,value in other_list:
            val_type=value.__name__ if hasattr(value,'__name__') else None
            if(val_type):
                other_tree.add(key+f" ({val_type})")
            else:
                other_tree.add(key)
        objects_to_show.append(other_tree)
    render_group=rich.console.RenderGroup(*objects_to_show)
    console.print(rich.panel.Panel(render_group,expand=False,title=title))

class Uncertainty(np.ndarray):
    def __new__(cls,input_array=[],
                name="unc",
                is_visible=True,
                digits=5,
                unc_steering=None,
                global_variables={},
                local_variables={},
                data_root='./'):
        # Uncertainty class.
        # Can be created an the following way:
        #
        # 1) data array (could be 1 or 2-dim) and name of error ,
        # unc=Uncertainty([1,2,3],'my_name')
        #
        # 2) explicite argument naming:
        # unc=Uncertainty(input_array=[1,2,3],name='my_name'),
        #
        # 3) providing dictionary following src/hepdata_maker/schemas/0.0.0/uncertainty.json schema.
        #    The argument name is ('unc_steering')
        # unc=Uncertainty(unc_steering={"name":"my_name","transformations":[1,2,3]})
        #
        # If unc_steering is given, it takes precedence over other arguments.
        #
        
        if(unc_steering):
            if(not isinstance(unc_steering,utils.objdict)):
                # TODO Do we really want to go further with objdict?! Either allow (and automatically translate to dict) or just fall back to dict?
                if (isinstance(unc_steering,dict)):
                    unc_steering=utils.objdict(unc_steering)
                else:
                    raise TypeError("'unc_steering' needs to be of type utils.objdict or dict!")
            name=unc_steering.get('name',name)
            is_visible=unc_steering.get('is_visible',is_visible)
            digits=unc_steering.get('digits',digits)
            cls.steering_info=unc_steering

        log.debug(f"Creating new Uncertainty object: {name}")
        log.debug(f"   parameters passed {locals()}")
        
        if(unc_steering):
            input_array=None
            if(hasattr(unc_steering,"in_files")):
                for in_file in unc_steering.in_files:
                    tmp_values=tmp_values_up=tmp_values_down=np.empty(0)
                    extra_args={k: in_file[k] for k in ('delimiter', 'file_type', 'replace_dict', 'tabular_loc_decode') if hasattr(in_file,k)}

                    # if decode is present we have either 2-dim specification of [up,down] or 1-dim symmetric error
                    if( hasattr(in_file, 'decode')):
                        tmp_values=variable_loading.read_data_file(utils.resolve_file_name(in_file.name,data_root),in_file.decode,**extra_args)

                    # if decode_up is present we have either 2-dim specification of [decode_up,decode_down] or [decode_up,None]
                    if( hasattr(in_file, 'decode_up')):
                        tmp_values_up=variable_loading.read_data_file(utils.resolve_file_name(in_file.name,data_root),in_file.decode_up,**extra_args)

                    # if decode_down is present we have either 2-dim specification of [decode_up,decode_down] or [None,decode_down]
                    if( hasattr(in_file, 'decode_down')):
                        tmp_values_down=variable_loading.read_data_file(utils.resolve_file_name(in_file.name,data_root),in_file.decode_down,**extra_args)

                    if(tmp_values_up.size>0 or tmp_values_down.size>0):
                        if(not tmp_values_down.size>0):
                            tmp_values_down=np.full_like(tmp_values_up,np.nan)
                        if(not tmp_values_up.size>0):
                            tmp_values_up=np.full_like(tmp_values_down,np.nan)
                        tmp_values=np.array([tmp_values_up,tmp_values_down]).T

                    if(not (tmp_values_up.size>0 or tmp_values_down.size>0 or tmp_values.size>0)):
                        raise TypeError("Something went wrong. Could not read errors")
                    if(input_array):
                        input_array=np.concatenate((input_array,tmp_values))
                    else:
                        input_array=tmp_values
            if( hasattr(unc_steering, 'data_type')):
                if(unc_steering.data_type!='' and unc_steering.data_type and input_array is not None):
                    input_array=input_array.astype(unc_steering.data_type)
            if( hasattr(unc_steering, 'transformations')):
                if(isinstance(unc_steering.transformations,str)):
                    raise ValueError(f"Parameter 'transformations needs to be list of transformations(strings), not string.'")
                for transformation in unc_steering.transformations:
                    input_array=perform_transformation(transformation,global_variables,utils.merge_dictionaries(local_variables,{name:input_array}))
            

        obj=np.asarray(input_array).view(cls)
        obj.name = name
        obj.is_visible = is_visible
        obj.digits = digits
        if(obj.ndim==2):
            obj.is_symmetric=False
        elif(obj.ndim==1):
            obj.is_symmetric=True
        else:
            raise TypeError(f"Uncertainty can only be either one or two dimensional (is: ndim={obj.ndim}). Provided: {input_array} of type {type(input_array)}.")
        if(obj.dtype=='object'):
            raise TypeError(f"Uncertainty can be only either 1-D or 2-D list (and not a 1/2-D hybrid). Provided: {input_array}.")
        if(not (isinstance(name,str) or name is None)):
            raise TypeError(f"Uncertainty's name has to be string (or None). It cannot be {type(name)} as provided with {name}.")
        # Finally, we must return the newly created object:
        return obj

    def __array_finalize__(self, obj):
        if obj is None: return
        self.name = getattr(obj, 'name', None)
        self.is_visible = getattr(obj, 'is_visible', True)        
        self.digits = getattr(obj, 'digits', 5)        
        self.unc_steering = getattr(obj, 'unc_steering', None)
        
    def steering_file_snippet(self):
        if(self.unc_steering): # a steering file was provided:
            return self.unc_steering
        else:
            out_json={}
            out_json['name']=self.name
            out_json['is_visible']=self.is_visible
            out_json['digits']=self.digits
            out_json['transformations']=[self.tolist()]
            return out_json
class Variable(np.ndarray):
    def __new__(cls, input_array=[],name="var", is_independent=True, is_binned=None, is_visible=True, unit="", digits=5,
                var_steering=None,
                global_variables={},
                local_variables={},
                data_root='./'):
        # Variable class.
        # Can be created an the following way:
        #
        # 1) data array (could be 1 or 2-dim) and name of the variable ,
        # var=Variable([1,2,3],'my_name')
        #
        # 2) explicite argument naming:
        # var=Variable(input_array=[1,2,3],name='my_name'),
        #
        # 3) providing dictionary following src/hepdata_maker/schemas/0.0.0/variable.json schema.
        #    The argument name is ('var_steering')
        # var=Variable(var_steering={"name":"my_name","transformations":[1,2,3]})
        #
        # If var_steering is given, it takes precedence over other arguments.
        #

        if(var_steering):
            if(not isinstance(var_steering,utils.objdict)):
                # TODO Do we really want to go further with objdict?! Either allow (and automatically translate to dict) or just fall back to dict?
                if (isinstance(var_steering,dict)):
                    var_steering=utils.objdict(var_steering)
                else:
                    raise TypeError("'var_steering' needs to be of type utils.objdict or dict!")
            name=var_steering.get('name',name)
            is_independent=var_steering.get('is_independent',is_independent)
            is_binned=var_steering.get('is_binned',is_binned)
            unit=var_steering.get('unit',unit)
            is_visible=var_steering.get('is_visible',is_visible)
            digits=var_steering.get('digits',digits)

        log.debug(f"Creating new Variable (np.ndarray derived) object: {name}")
        log.debug(f"parameters passed:")
        log.debug(f"{locals()}")

        if(var_steering):
            input_array=None # Steering files overrides arguments
            if(hasattr(var_steering,'in_files')):
                for in_file in var_steering.in_files:
                    extra_args={k: in_file[k] for k in ('delimiter', 'file_type', 'replace_dict', 'tabular_loc_decode') if k in in_file}
                    tmp_values=variable_loading.read_data_file(utils.resolve_file_name(in_file.name,data_root),in_file.decode,**extra_args)
                    if(input_array):
                        input_array=np.concatenate((input_array,tmp_values))
                    else:
                        input_array=tmp_values
            if( hasattr(var_steering, 'data_type')):
                if(var_steering.data_type!='' and input_array is not None):
                    input_array=input_array.astype(var_steering.data_type)
            if(hasattr(var_steering,'transformations')):
                for transformation in var_steering.transformations:
                    input_array=perform_transformation(transformation,global_variables,utils.merge_dictionaries(local_variables,{name:input_array}))
            if(input_array is None):
                input_array=[]
        obj = np.asarray(input_array).view(cls)
        # add the new attribute to the created instance
        try:
            obj.astype(str) # if passes this it should pass hepdata_lib conversion
        except:
            raise ValueError(f"Variable can be only either 1-D or 2-D list (and not a 1/2-D hybrid). Provided: {input_array}.")
        if(not (isinstance(name,str) or name is None)):
            raise TypeError(f"Variable's name has to be string (or None). It cannot be {type(name)} as provided with {name}.")
        if(obj.ndim>2):
            raise TypeError(f"Variable can be at most 2-D. The input {input_array} has dimension {obj.ndim}.")
        if(is_binned is None):
            # Auto-discover whether data is binned or not
            if(obj.ndim==1):
                is_binned=False
            else:
                is_binned=True
        # We might have variables that are lists for each value 
        if(obj.ndim==2 and not is_binned):
            input_array=["["+",".join(entry)+"]" for entry in input_array]
            obj = np.asarray(input_array).view(cls)

        obj.name = name
        obj.is_independent = is_independent
        obj.is_binned = is_binned
        obj.is_visible= is_visible
        obj.unit = unit
        obj.digits = digits

        if(var_steering):
            obj._var_steering=var_steering
            if( hasattr(var_steering, 'errors')):
                if(var_steering.errors):
                    for error_info in var_steering.errors:
                        current_local_variables=utils.merge_dictionaries(local_variables,{name:input_array},{var_err.name:var_err for var_err in obj.uncertainties})
                        unc=Uncertainty(unc_steering=error_info,local_variables=current_local_variables,global_variables=global_variables,data_root=data_root)
                        obj.add_uncertainty(unc)
            if(obj.multiplier):
                obj.qualifiers.append({"multiplier":obj.multiplier})
            if hasattr(var_steering, 'regions'):
                current_local_variables=utils.merge_dictionaries(local_variables,{name:input_array},{var_err.name:var_err for var_err in obj.uncertainties})
                obj.regions=get_matching_based_variables(var_steering.regions,global_variables,current_local_variables)
            if hasattr(var_steering, 'grids'):
                current_local_variables=utils.merge_dictionaries(local_variables,{name:input_array},{var_err.name:var_err for var_err in obj.uncertainties})
                obj.grids=get_matching_based_variables(var_steering.grids,global_variables,current_local_variables)
            if hasattr(var_steering, 'signal_names'):
                current_local_variables=utils.merge_dictionaries(local_variables,{name:input_array},{var_err.name:var_err for var_err in obj.uncertainties})
                obj.signal_names=get_matching_based_variables(var_steering.signal_names,global_variables,current_local_variables)

        # Finally, we must return the newly created object:
        return obj

    def __array_finalize__(self, obj):
        if obj is None: return
        self.name = getattr(obj, 'name', None)
        self.is_independent = getattr(obj, 'is_independent', True)
        self.is_binned = getattr(obj, 'is_binned', False)
        self.is_visble = getattr(obj, 'is_visible', True)
        self.qualifiers = getattr(obj, 'qualifiers', [])
        self.multiplier = getattr(obj, 'multiplier', None)
        self.unit = getattr(obj, 'unit', "")
        self._uncertainties = getattr(obj, 'uncertainties', [])
        self.region = getattr(obj,'region',np.array([[]]*len(obj)))
        self.grid = getattr(obj,'grid',np.array([[]]*len(obj)))
        self.signal = getattr(obj,'signal',np.array([[]]*len(obj)))
        self.digits = getattr(obj, 'digits', 5)
        self._var_steering=getattr(obj, 'var_steering', None)
    
    def _update_unc_steering(self,uncertainty):
        if(self._var_steering):
            err_name=uncertainty.name
            new_unc_steering=uncertainty.steering_file_snippet()
            if(err_name in self.get_uncertainty_names()):
                self._var_steering['errors'][self.uncertainty_index(err_name)]=new_unc_steering
            else:
                self._var_steering['errors'].append(new_unc_steering)
    def _delete_unc_steering(self,uncertainty):
        uncertainty_name=uncertainty.name
        if(self._var_steering):
            if(uncertainty_name not in self.get_uncertainty_names()):
                log.warning(f"You try to remove uncertainty {uncertainty_name} that is not found in the variable {self.name}.")
                return
            else:
                if(uncertainty_name not in self._var_steering['uncertainties']):
                    log.warning(f"The uncertainty {uncertainty_name} to be removed was not found in steering file of variable {self.name} however it is part of variables' uncertainties list... You probably use the code not as it was intended to be used!")
                    return
                else:
                    self._var_steering['uncertainties'].pop(self.uncertainty_index(uncertainty_name))
    def get_uncertainty_names(self):
        return [unc.name for unc in self.uncertainties]
    def _add_unc_to_dict_safely(self,uncertainty):
        if(not isinstance(uncertainty, Uncertainty)):
            raise TypeError("Unknown object type: {0}".format(str(type(uncertainty))))
        name=uncertainty.name
        if(name in self.__dict__):
            raise ValueError(f"You try to add uncertainty with name {name} to variable {self.name}. This name cannot be used as is already taken, see __dict__: {self.__dict__}.")
        self.__dict__[name]=uncertainty
    def add_uncertainty(self, uncertainty):
        """
        Add a uncertainty to the table
        :param uncertainty: Uncertainty to add.
        :type uncertainty: Uncertainty.
        """
        log.debug(f"Adding uncertainty to Variable {self.name}. Parameters passed: {locals()}")
        if isinstance(uncertainty, Uncertainty):
            if(self.size!=len(uncertainty)):
                raise ValueError(f"Uncertainty {uncertainty.name, ({uncertainty.tolist()})} has different dimention ({len(uncertainty)}) than the corresponding variable {self.name} ({self.tolist()},{self.size}).")
            if(uncertainty.name in self.get_uncertainty_names()):
                raise ValueError(f"Uncertainty {uncertainty.name} is already present in the variable variable {self.name}.")
            self.uncertainties.append(uncertainty)
            self._add_unc_to_dict_safely(uncertainty)
            self._update_unc_steering(uncertainty)
        else:
            raise TypeError("Unknown object type: {0}".format(str(type(uncertainty))))
    def update_uncertainty(self,new_unc):
        if not isinstance(new_unc, Uncertainty):
            raise TypeError(f"In order to update uncertainty for variable ({self.name}) one needs to provide an uncertainty. Here, unknown object of type: {type(new_unc)}")
        log.debug(f"Updating uncertainty {new_unc.name} of variable {self.name}. Parameters passed: {locals()}")
        no_matching=True
        for index,unc in enumerate(self.uncertainties):
            if(unc.name==new_unc.name):
                no_matching=False
                self.uncertainties[index]=new_unc
                self.__dict__[new_unc.name]=new_unc
                self._update_unc_steering(new_unc)
        if(no_matching):
            log.warning(f"You tried to update unc {new_unc.name} in variable {self.name}, but no uncertainty of such name found in the variable! Adding the uncertainty instead.")
            self.add_uncertainty(new_unc)
    def uncertainty_index(self,uncertainty_name):
        if(not isinstance(uncertainty_name,str)):
            raise TypeError(f"Uncertainty's name needs to be a string. Trying to find uncertainty based on object type ({type(uncertainty_name)}) failed!")
        return self.get_uncertainty_names().index(uncertainty_name)
    def delete_uncertainty(self,uncertainty_name):
        if(uncertainty_name not in self.get_uncertainty_names()):
            log.warning(f"You try to remove uncertainty {uncertainty_name} that is not found in the variable {self.name}.")
            return
        else:
            if(uncertainty_name not in self.__dict__):
                log.warning(f"The uncertainty {uncertainty_name} to be removed was not found in __dict__ of variable {self.name} however it is part of variables' uncertainties list... You probably use the code not as it was intended to be used!")
                # We nonetheless continue as the unc is present in the uncertainties()
            else:
                self.__dict__.pop(uncertainty_name)
            uncertainty=self.uncertainties[self.uncertainty_index(uncertainty_name)]
            self._delete_unc_steering(uncertainty)
            del self.uncertainties[self.uncertainty_index(uncertainty_name)]

    @property
    def uncertainties(self):
        """uncertainties getter."""
        return self._uncertainties

    @uncertainties.setter
    def uncertainties(self, uncertainties):
        """uncertainties setter."""
        
        # Remove names of the uncertainties already present in the instance's __dict__:
        for old_uncertainty in self.uncertainties:
            self._delete_unc_steering(old_uncertainty)
            if(old_uncertainty.name in self.__dict__):
                self.__dict__.pop(old_uncertainty.name)
            else:
                log.warning(f"Name of the uncertainty {old_uncertainty.name} to be removed was not found in __dict__ of variable {self.name}.")
        # Check that new tables are of correct type and update the instance's dict
        for uncertainty in uncertainties:
            if not isinstance(uncertainty, Uncertainty):
                raise TypeError("Unknown object type: {0}".format(str(type(uncertainty))))
            else:
                self._add_unc_to_dict_safely(uncertainty)
                self._update_unc_steering(uncertainty)
        # finally set the table list
        self._uncertainties = uncertainties
    def steering_file_snippet(self):
        if(self._var_steering): # a steering file was provided:
            return self._var_steering
        else:
            out_json={}
            out_json['name']=self.name
            out_json['is_visible']=self.is_visible
            out_json['digits']=self.digits
            out_json['transformations']=[self.tolist()]
            out_json['uncertainties']=[]
            for unc in self.uncertainties:
                out_json['uncertainties'].append(unc.steering_file_snippet())
            self._var_steering=out_json
            return out_json
class Table(object):
    """
    A table is a collection of variables.
    It also holds meta-data such as a general description,
    the location within the paper, etc.
    """
    
    def __init__(self, name='table',
                tab_steering=None,
                global_variables={},
                local_variables={},
                data_root='./'):
        if(tab_steering):
            if(not isinstance(tab_steering,utils.objdict)):
                # TODO Do we really want to go further with objdict?! Either allow (and automatically translate to dict) or just fall back to dict?
                if (isinstance(tab_steering,dict)):
                    tab_steering=utils.objdict(tab_steering)
                else:
                    raise TypeError("'tab_steering' needs to be of type utils.objdict or dict!")
            if( hasattr(tab_steering,'should_be_processed') and not tab_steering.should_be_processed):
                raise ValueError(rf"table {tab_steering.name} has 'should_be_processed' flag set to False. Class Table shoudl not see this flag at all (prune prior to constructor).")
            name=tab_steering.get('name',name)

        log.debug(f"Creating new Table: {name}")

        if(name is None or not isinstance(name,str)):
            raise TypeError(f"Table's name needs to be of type string, not {type(name)}.")
        self._name = None
        self.name = name
        self._variable_lenght=0
        self._variables = []
        self.title = ""
        self.location = ""
        self.keywords = {}
        #self.additional_resources = []
        self.images = []
        self._tab_steering={}
        if(tab_steering):
            self.tab_steering=tab_steering
            if( hasattr(tab_steering, 'images')):
                self.images=tab_steering.images
                for image_info in self.images:
                    current_image_path=utils.resolve_file_name(image_info['name'],data_root)
                    if(not os.path.isfile(current_image_path)):
                        raise ValueError(f"Cannot find image file of table '{name}' under the path '{current_image_path}'. Please check it!")
            if( hasattr(tab_steering, 'title')):
                potential_file_path=utils.resolve_file_name(tab_steering.title,data_root)
                if(os.path.isfile(potential_file_path)):
                    # Provide file with table title ( e.g. website out)
                    log.debug(f"Title field of table {name} points to a text file. Content of the file will be used as table title.")
                    self.title=open(potential_file_path).read()
                    print(repr(self.title))
                else:
                    log.debug(f"Title fielf of table {name} points to a text file. Content of the file will be used as table title.")
                    self.title=tab_steering.title
            if( hasattr(tab_steering, 'location')):
                self.location=tab_steering.location
            if( hasattr(tab_steering, 'keywords')):
                self.keywords=tab_steering.keywords
            if(hasattr(tab_steering,'variables')):
                for variable_info in tab_steering.variables:
                    local_variables=utils.merge_dictionaries(self.__dict__)
                    var=Variable(var_steering=variable_info,global_variables=global_variables,local_variables=local_variables,data_root=data_root)
                    self.add_variable(var)


    @property
    def name(self):
        """Name getter."""
        return self._name

    @name.setter
    def name(self, name):
        """Name setter."""
        if len(name) > 64:
            raise ValueError("Table name must not be longer than 64 characters.")
        self._name = name

    def _update_var_steering(self,variable):
        if(self._tab_steering):
            var_name=variable.name
            new_var_steering=variable.steering_file_snippet()
            if(var_name in self.get_variable_names()):
                self._tab_steering['variables'][self.variable_index(var_name)]=new_var_steering
            else:
                self._tab_steering['variables'].append(new_var_steering)
    def _delete_var_steering(self,variable):
        variable_name=variable.name
        if(self._tab_steering):
            if(variable_name not in self.get_variable_names()):
                log.warning(f"You try to remove variable {variable_name} that is not found in the table {self.name}.")
                return
            else:
                if(variable_name not in self._tab_steering['variables']):
                    log.warning(f"The variable {variable_name} to be removed was not found in steering file of table {self.name} however it is part of the table's variables list... You probably use the code not as it was intended to be used!")
                    return
                else:
                    self._tab_steering['variables'].pop(self.variable_index(variable_name))

    def get_variable_names(self):
        return [var.name for var in self.variables]

    def variable_index(self,variable_name):
        if(not isinstance(variable_name,str)):
            raise TypeError(f"Variable's name needs to be a string. Trying to find variable based on object type ({type(variable_name)}) failed!")
        return self.get_variable_names().index(variable_name)

    def _add_var_to_dict_safely(self,variable):
        if(not isinstance(variable, Variable)):
            raise TypeError("Unknown object type: {0}".format(str(type(variable))))
        name=variable.name
        if(name in self.__dict__):
            raise ValueError(f"You try to add variable with name {name} to table {self.name}. This name, however, cannot be used as is already taken, see __dict__:{self.__dict__}.")
        self.__dict__[name]=variable

    def add_variable(self, variable):
        """
        Add a variable to the table
        :param variable: Variable to add.
        :type variable: Variable.
        """
        if isinstance(variable, Variable):
            log.debug(f"Adding variable {variable.name} to the table {self.name}")
            if(self._variable_lenght!=0):
                if(self._variable_lenght!=len(variable) and variable.is_visible):
                    raise ValueError(f"Variable {variable.name} ({variable.tolist()}) has different number of parameters ({len(variable)}) than other variables in the table {self.name} ({self._variable_lenght}, as e.g. for {self.variables[0].name}, {self.variables[0].tolist()})")
            else:
                if(variable.is_visible):
                    self._variable_lenght=len(variable)
            self.variables.append(variable)
            self._add_var_to_dict_safely(variable)
            self._update_var_steering(variable)
        else:
            raise TypeError("Unknown object type: {0}".format(str(type(variable))))
    def update_variable(self,new_var):
        if(not isinstance(new_var, Variable)):
            raise TypeError("Table can be updated with a variable, not with object type: {0}".format(str(type(new_var))))
        log.debug(f"Updating variable {new_var.name} of variable {self.name}. Parameters passed: {locals()}")
        no_matching=True
        for index,var in enumerate(self.variables):
            if(var.name==new_var.name):
                no_matching=False
                self.variables[index]=new_var
                if(not new_var.name in self.__dict__):
                    log.warning(f"The variable {variable_name} to be updated was not found in __dict__ of table {self.name} however it should be there... You probably use the code not as it was intended to be used!")
                self.__dict__[new_var.name]=new_var # here we do not use _add_var_to_dict_safely as the variable name should already be in __dict__ (or not be there at all)
        if(no_matching):
            log.warning(f"You tried to update variable {new_var.name} in table {self.name}, but no variable of such name found in the table! Adding variable instead!")
            self.add_variable(new_var)
            self._update_var_steering(new_var)
    def delete_variable(self,variable_name):
        if(variable_name not in self.get_variable_names()):
            log.warning(f"You try to remove variable {variable_name} that is not found in the table {self.name}.")
            return
        else:
            if(variable_name not in self.__dict__):
                log.warning(f"The variable {variable_name} to be removed was not found in __dict__ of table {self.name} however it should be there... You probably use the code not as it was intended to be used!")
                # we continue nonetheless
            else:
                self.__dict__.pop(variable_name)
            self._delete_var_steering(self.variables[self.variable_index(variable_name)])
            del self.variables[self.variable_index(variable_name)]
    @property
    def variables(self):
        """variables getter."""
        return self._variables

    @variables.setter
    def variables(self, variables):
        """variables setter."""
        
        # Remove names of the variables already present in the instance's __dict__:
        for old_variable in self.variables:
            if(old_variable.name in self.__dict__):
                self.__dict__.pop(old_variable.name)
            else:
                log.warning(f"Name of the variable {old_variable.name} to be removed was not found in __dict__ of variable {self.name}.")
        # Check that new tables are of correct type and update the instance's dict
        for variable in variables:
            if not isinstance(variable, Variable):
                raise TypeError("Unknown object type: {0}".format(str(type(variable))))
            else:
                self._add_var_to_dict_safely(variable)
        # finally set the table list
        self._variables = variables

    def steering_file_snippet(self):
        if(self._tab_steering): # a steering file was provided:
            return self._tab_steering
        else:
            output_json={}
            output_json['name']=self.name
            output_json['title']=self.title
            output_json['location']=self.location
            output_json['keywords']=self.keywords
            output_json['images']=self.images
            output_json['variables']=[]
            for variable in self.variables:
                output_json['variables'].append(variable.steering_file_snippet())
            return output_json
        
def fix_zero_error(variable):
    tmp_need_zero_error_fix=(variable==np.zeros_like(variable))
    tmp_need_zero_error_fix=np.array([tmp_need_zero_error_fix,tmp_need_zero_error_fix]).T # translating to the (2,N) shape of errors
    tmp_need_zero_error_fix_sym=np.zeros_like(tmp_need_zero_error_fix)
    for error in variable.uncertainties:
        if(error.is_symmetric): # error is 1D np array. We need to expand it to 2D
            tmp_error=np.array([error,error]).T
        else: # error is already 2D
            tmp_error=error
        tmp_need_zero_error_fix=tmp_need_zero_error_fix&(tmp_error==np.zeros_like(tmp_need_zero_error_fix))
    need_zero_error_fix=tmp_need_zero_error_fix
    
    fixed_variables=[]

    # For assymetric case if one error is present we do not need to apply fix ( thus logical and for up-down pairs):
    need_zero_error_fix=np.repeat(np.logical_and.reduce(need_zero_error_fix,axis=1)[:,np.newaxis], 2, axis=1)
    
    for index,error in enumerate(variable.uncertainties):
        if(error.is_symmetric):
            fixed_variables.append(np.where(np.logical_and.reduce(need_zero_error_fix,axis=1),np.full_like(error,'',dtype=str),error))
        else:
            fixed_variables.append(np.where(need_zero_error_fix,np.full_like(error,['',''],dtype=str),error))
    return fixed_variables

def get_matching_based_variables(matchDefinitions,global_dict=None,local_dict=None):
    result=None
    for specification in matchDefinitions:
        var=specification.name
        cuts=specification.matching
        for cut in cuts:
            if(type(cut)==str):
                cutOutput=np.where(eval(cut,global_dict,local_dict),var,None)
                ToAppend=cutOutput.reshape(len(cutOutput),1)
                if(not result):
                    result=ToAppend
                else:
                    result=np.concatenate((result,ToAppend),axis=1)
            elif(type(cut)==int):
                if(cut>=len(cuts)):
                    raise RuntimeError("lenght of cut table smaller than required index.")
                else:
                    ToAppend=np.array([[None]]*len(Variable))
                    ToAppend[cut]=var
                if(not result):
                    result=ToAppend
                else:
                    result=np.concatenate((result,ToAppend),axis=1)
            else:
                raise TypeError("Variable cutDefinitions has improper content.")
    return result

class Resource():
    def __init__(self,location='',description='',res_steering=None,category=None,copy_file=None):
        if(res_steering):
            location=res_steering.get('location',location)
            description=res_steering.get('description',description)
            category=res_steering.get('category',category)
            copy_file=res_steering.get('copy_file',copy_file)
        self.location=location
        self.description=description=description
        if(copy_file is None):
            # try to figure out whether this is a link or a file
            if(validators.url(location) or validators.email(location)):
                copy_file=False
            else:
                copy_file=True
        self.copy_file=copy_file
    def steering_file_snippet(self):
        output_json={}
        output_json['location']=self.location
        output_json['description']=self.description
        return output_json
        
class Submission():
    
    def __init__(self):
        self._tables=[]
        self._resources=[]
        self._config={}
        self._has_loaded=False
        self.generate_table_of_content=False
    def get_table_names(self):
        return [tab.name for tab in self.tables]
    def table_index(self,table_name):
        if(not isinstance(table_name,str)):
            raise TypeError(f"Table's name needs to be a string. Trying to find uncertainty based on object type ({type(table_name)}) failed!")
        return self.get_table_names().index(table_name)
    def get_resource_names(self):
        return [res.name for res in self._resources]
    def resource_index(self,resource_location):
        if(not isinstance(resource_location,str)):
            raise TypeError(f"Resource location needs to be a string. Trying to find resource based on object type ({type(table_name)}) failed!")
        return self.get_resource_names().index(resource_location)
    def create_table_of_content(self):
        if ("overview" in self.get_table_names()):
            log.warning("Table named 'overview' is already defined. It is assumed that it contains the table of content and it will not be attempted to re-creating it. Rename/remove 'overview' in your steering file if you expect another behaviour.")
            return
        table_of_content_list=[]
        table_of_content_list.append(r"<b>- - - - - - - - Overview of HEPData Record - - - - - - - -</b>")
        table_of_content_list.append(r"<b>tables:</b><ul>")
        for table in self.tables:
            table_of_content_list.append(fr"<li><a href=?table={table.name}>{table.name}</a>")
        table_of_content_list.append(r"</ul>")
        toc=Table("overview")
        toc.title="\n".join(table_of_content_list)
        self.insert_table(0,toc)
    def read_table_config(self,
                          config_file_path: str=''):
        if(not os.path.isfile(config_file_path)):
            raise ValueError(f"Could not find config file {config_file_path}. Please check the path provided.")
        with open(config_file_path, 'r') as stream:
            print("file://"+os.path.abspath(os.path.dirname(config_file_path)),config_file_path)
            config_loaded = jsonref.load(stream,base_uri="file://"+os.path.abspath(os.path.dirname(config_file_path))+"/",object_pairs_hook=OrderedDict)
        self.config=config_loaded
    def load_table_config(self,data_root: str='./',selected_table_names=[]):
        if(self._has_loaded):
            log.warning("You have already loaded information from a(nother?) steering file. If any table names will be loaded again (without prior explicite deletions) expect errors being raised!")
        self._has_loaded=True

        if('generate_table_of_content' in self.config):
            self.generate_table_of_content=self.config['generate_table_of_content']
        # self._config should aready have the correct information as checked on schema check in read_table_config
        if('additional_resources' in self.config):
            for resource_info in [utils.objdict(x) for x in self.config['additional_resources']]:
                res=Resource(res_steering=resource_info)
                self.add_resource(res)
        if('tables' in self.config):
            for table_info in [utils.objdict(x) for x in self.config['tables']]:
                global_variables=utils.merge_dictionaries(self.__dict__,{"np":np},{"re":re},{"scipy.stats":scipy.stats},{"scipy.special":scipy.special},{"ufs":ufs})
                table_name=table_info.name
                if( hasattr(table_info,'should_be_processed') and not table_info.should_be_processed):
                    log.warning(rf"table {table_info.name} has should_be_processed flag set to False. Skipping.")
                    continue
                if(len(selected_table_names)>0 and (table_name not in selected_table_names)):
                    log.debug(f"skipping loading table {table_name} as not present in selected_table_names: {selected_table_names}")
                    continue
                console.rule(f"table {table_name}")
                table=Table(tab_steering=table_info,global_variables=global_variables,data_root=data_root)
                self.add_table(table)
            
    def create_hepdata_record(self,data_root:str='./',outdir='submission_files'):
        # Actual record creation based on information stored
        hepdata_submission = hepdata_lib.Submission()
        if(self.generate_table_of_content):
            self.create_table_of_content()
        for resource in self.resources:
            hepdata_submission.add_additional_resource(resource.description,resource.location,resource.copy_file)
        for table in self.tables:
            hepdata_table = hepdata_lib.Table(table.name)
            hepdata_table.description = table.title
            hepdata_table.location = table.location
            hepdata_table.keywords = table.keywords
            for image_info in table.images:
                hepdata_table.add_image(utils.resolve_file_name(image_info['name'],data_root))
            for variable in table.variables:
                if(variable.is_visible):
                    log.debug(f"Adding variable to table {table.name}; name(var)={variable.name}, is_independent={variable.is_independent},is_binned={variable.is_binned},unit={variable.unit},values={variable.tolist()}")
                    hepdata_variable=hepdata_lib.Variable(variable.name, is_independent=variable.is_independent, is_binned=variable.is_binned, units=variable.unit)
                    hepdata_variable.values=variable.tolist()
                    #
                    #HACK: Mind fixed_zero_variable is list of ndarray instead of Uncertenties/Variable... need to be fixed
                    #
                    fixed_zero_variable=fix_zero_error(variable)
                    #
                    for index,unc in enumerate(variable.uncertainties):
                        #print(type(unc),variable.uncertainties[index])
                        if(unc.is_visible):
                            #print(f"Adding {unc.name} to variable {variable.name}")
                            # Something does not work properly so for now assumed all errors are symmetric... 
                            #unc_is_symmetric=unc.is_error_symmetric()
                            
                            hepdata_unc = hepdata_lib.Uncertainty(unc.name, is_symmetric=unc.is_symmetric)
                            hepdata_unc.values=fixed_zero_variable[index].tolist()
                            hepdata_variable.add_uncertainty(hepdata_unc)
                    if(len(variable.qualifiers)!=0):
                        for entry in variable.qualifiers:
                            #print(entry)
                            for key,val in entry.items():
                                hepdata_variable.add_qualifier(key,val)
                    hepdata_table.add_variable(hepdata_variable)
            hepdata_submission.add_table(hepdata_table)
        hepdata_submission.create_files(outdir)
        if(os.path.isdir(outdir) and os.path.isfile('submission.tar.gz')):
            console.print(f"Submission files created and available under directory {outdir} and as a tarball in submission.tar.gz")

    def _add_tab_to_dict_safely(self,table):
        if(not isinstance(table, Table)):
            raise TypeError("Unknown object type: {0}".format(str(type(table))))
        name=table.name
        if(name in self.__dict__):
            raise ValueError(f"You try to add table with name '{name}'. This name, however, cannot be used as is already taken, see __dict__:{self.__dict__}.")
        self.__dict__[name]=table

    def insert_table(self,index, table):
        if isinstance(table, Table):
            log.debug(f"Adding table {table.name} to the submission")
            self.tables.insert(index,table)
            self._add_tab_to_dict_safely(table)
        else:
            raise TypeError("Unknown object type: {0}".format(str(type(table))))
        
    def add_table(self, table):
        """
        Add a table to the submission
        :param table: Table to add.
        :type table: Table.
        """
        if isinstance(table, Table):
            log.debug(f"Adding table {table.name} to the submission")
            self.tables.append(table)
            self._add_tab_to_dict_safely(table)
        else:
            raise TypeError("Unknown object type: {0}".format(str(type(table))))
    def update_table(self,new_tab):
        if not isinstance(new_tab, Table):
            raise TypeError(f"In order to update table in submission one needs to provide a table. Here, unknown object of type: {type(new_tab)}")
        log.debug(f"Updating table {new_tab.name}. Parameters passed: {locals()}")
        no_matching=True
        for index,tab in enumerate(self.tables):
            if(tab.name==new_tab.name):
                if(not no_matching):
                    raise ValueError(f"Table name '{tab.name}' appears twice in the submission while updating table. Fix this (hint, aren't you shallow-copy from another table that is in the submission?).")
                no_matching=False
                self.tables[index]=new_tab
                if(not new_tab.name in self.__dict__):
                    log.warning(f"The table {table_name} to be updated was not found in __dict__ of submission object however it should be there... You probably use the code not as it was intended to be used!")
                self.__dict__[new_tab.name]=new_tab # here we do not use _add_tab_to_dict_safely as the table name should already be in __dict__ (or not be there at all)
        if(no_matching):
            log.warning(f"You tried to update table {new_tab.name}, but no table of such name found in the table! Simply adding the table instead.")
            self.add_table(new_tab)
    def delete_table(self,table_name):
        if(table_name not in self.get_table_names()):
            log.warning(f"You try to remove table {table_name} that is not found in the submission object.")
            return
        else:
            if(table_name not in self.__dict__):
                log.warning(f"The table {table_name} to be removed was not found in __dict__ of submission object however it should be there... You probably use the code not as it was intended to be used!")
                # we continue nonetheless
            else:
                self.__dict__.pop(table_name)
            del self.tables[self.table_index(table_name)]

    def insert_resource(self,index, resource):
        if isinstance(resource, Resource):
            log.debug(f"Adding resource {resource.location} to the submission")
            self.resources.insert(index,resource)
        else:
            raise TypeError("Unknown object type: {0}".format(str(type(resource))))
        
    def add_resource(self, resource):
        """
        Add a resource to the submission
        :param resource: Resource to add.
        :type resource: Resource.
        """
        if isinstance(resource, Resource):
            log.debug(f"Adding resource {resource.location} to the submission")
            self.resources.append(resource)
        else:
            raise TypeError("Unknown object type: {0}".format(str(type(resource))))

    def delete_resource(self,resource_location):
        if(resource_location not in self.get_resource_locations()):
            log.warning(f"You try to remove resource {resource_location} that is not found in the submission object.")
            return
        else:
            del self.resources[self.resource_index(resource_location)]

    @property
    def config(self):
        """config getter."""
        return self._config

    @config.setter
    def config(self, config):
        """config setter."""
        # Check schema of the submission steering file:
        utils.check_schema(config,'steering_file.json')
        self._config=config
        
    @property
    def tables(self):
        """tables getter."""
        return self._tables

    @tables.setter
    def tables(self, tables):
        """tables setter."""
        
        # Remove names of the tables already present in the instance's dict:
        for old_table in self.tables:
            self.__dict__.pop(old_table.name)
        # Check that new tables are of correct type and update the instance's dict
        for table in tables:
            if not isinstance(table, Table):
                raise TypeError("Unknown object type: {0}".format(str(type(table))))
            else:
                self._add_tab_to_dict_safely(table)
        # finally set the table list
        self._tables = tables

    @property
    def resources(self):
        """resources getter."""
        return self._resources

    @resources.setter
    def resources(self, resources):
        """resources setter."""
        
        # Remove names of the resources already present in the instance's dict:
        for old_table in self.resources:
            self.__dict__.pop(old_table.name)
        # Check that new resources are of correct type and update the instance's dict
        for table in resources:
            if not isinstance(table, Table):
                raise TypeError("Unknown object type: {0}".format(str(type(table))))
            else:
                self._add_tab_to_dict_safely(table)
        # finally set the table list
        self._resources = resources

    def steering_file_snippet(self):
        output_json={}
        output_json['type']='steering'
        output_json["generate_table_of_content"]=self.generate_table_of_content
        json_tables=[]
        for table in self.tables:
            json_tables.append(table.steering_file_snippet())
        output_json['tables']=json_tables
        utils.check_schema(output_json,'steering_file.json')
        return output_json
