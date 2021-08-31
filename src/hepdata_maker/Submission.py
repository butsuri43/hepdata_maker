from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import numpy as np
import jsonref      # type: ignore
from collections import OrderedDict
from collections.abc import Iterable
import hepdata_lib  # type: ignore
import os.path
import regex as re  # type: ignore
import scipy.stats, scipy.special  # type: ignore
from . import variable_loading
from . import useful_functions as ufs
from . import utils
from .console import console
from .logs import logging
log = logging.getLogger(__name__)
import rich.panel
import rich.tree
import validators  # type: ignore
import jq          # type: ignore
import time
from typing import Optional,Any,List,Dict,TypeVar, Type, Literal,Union,Tuple

def is_name_correct(name:str)->bool:
    """
    Checking whether the 'name' field does not contain forbidden characters
    """
    if(name):
        return re.match("^([a-zA-Z0-9\\._;/+])*$",name) is not None
    else:
        return False

def perform_transformation(transformation:str,
                           submission_dict:Dict[str,Any],
                           local_vars:Dict[str,Any])->Iterable:
    """
    Function executing user-specified transformation of variables/errors loaded

    Args:
      transformation: numpy-style transformation returning a 1-D array/ndarray
      submission_dict: collections of variables and other known objects
        to be used in the transformation
      local_vars: yet another collection of variables known to be used in the transformation
    """
    try:
        global_vars=utils.merge_dictionaries(submission_dict,{"np":np},{"re":re},{"scipy.stats":scipy.stats},{"scipy.special":scipy.special},{"ufs":ufs},{"nan":np.nan})
        return eval(transformation,global_vars,local_vars)
    except Exception as exc:
        log.error(f"Transformation '{transformation}' has failed.")
        log.error(f"Make sure your numpy array data is of the correct type (by specifying 'data-type')!")
        log.error(f"You can use following global variables:")
        rich_highlight_dict_objects(global_vars,title="global variables")
        log.error(f"and local variables:")
        rich_highlight_dict_objects(local_vars,title="local variables")
        raise exc

def remove_none_from_uncertainty_array(in_list:Iterable)->np.ndarray:
    """
    Replace uncertainty values which are None with zeros matching type of other variables in the given array.
    This allows to work (with numpy arrays) easily with variables for which only some values have the corresponding error defined
    This is 'safe' as when translating to hepdata zero errors are converted to hepdata

    Args:
      in_list: list of error values (can be 1 or 2 dim)
    """
    not_none_entries=[x for x in in_list if x is not None]
    ndim=1
    if(len(not_none_entries)==0):
        return np.array([0]*len(list(in_list)))
    else:
        not_none=np.array(not_none_entries[0])
        if(not_none.size>2 or not_none.size==0):
            raise ValueError(f"Uncertainty cannot have such dimentionalities, {in_list}")
        if(not_none.size==2):
            ndim==2
        replacement= 0 if ndim==1 else [0.0]
        return np.array([x if x is not None else replacement for x in in_list],dtype=not_none.dtype)

ndarray_super_type = TypeVar('ndarray_super_type', bound=np.ndarray)
class Uncertainty(np.ndarray):
    """
        Uncertainty is a 1 or 2 dimentional numpy-array-like table describing one source of uncertainty.

        Can be created an the following way:

        1) data array (could be 1 or 2-dim) and name of error,
        unc=Uncertainty([1,2,3],'my_name')

        2) providing dictionary following src/hepdata_maker/schemas/0.0.0/uncertainty.json schema.
        unc=Uncertainty(unc_steering={"name":"my_name","transformations":[1,2,3]})

        If unc_steering is given, it takes precedence over other arguments.
        """

    def __new__(cls:Type[ndarray_super_type],
                input_array:Iterable=[],
                name:str="unc",
                fancy_name:str="",
                is_visible:bool=True,
                digits:int=5,
                unc_steering:Optional[Dict[str,Any]]=None,
                global_variables:Dict[str,Any]={},
                local_variables:Dict[str,Any]={},
                data_root:str='./'):
        ## Time the execution
        start=time.time()

        # First we want to get the name (potentially from steering file) to display it in debug.
        # We do not want to read all the variables and transformations here as these are more error prone
        if(unc_steering):
            if(not isinstance(unc_steering,utils.objdict)):
                # TODO Do we really want to go further with objdict?! Either allow (and automatically translate to dict) or just fall back to dict?
                if (isinstance(unc_steering,dict)):
                    unc_steering=utils.objdict(unc_steering)
                else:
                    raise TypeError("'unc_steering' needs to be of type utils.objdict or dict!")
            name=unc_steering.get('name',name)
            fancy_name=unc_steering.get('fancy_name','')
            is_visible=unc_steering.get('is_visible',is_visible)
            digits=unc_steering.get('digits',digits)
            cls.steering_info=unc_steering

        log.debug(f"Creating new Uncertainty object: {name}")
        log.debug(f"   parameters passed {locals()}")
        
        if(unc_steering):
            input_array=[]
            for in_file in getattr(unc_steering,'in_files',[]):
                tmp_values=tmp_values_up=tmp_values_down=np.empty(0)
                extra_args={k: in_file[k] for k in ('delimiter', 'file_type', 'replace_dict', 'tabular_loc_decode') if hasattr(in_file,k)}

                # if decode is present we have either 2-dim specification of [up,down] or 1-dim symmetric error
                if( hasattr(in_file, 'decode')):
                    tmp_values=variable_loading.read_data_file(utils.resolve_file_name(in_file.name,data_root),in_file.decode,**extra_args)
                    tmp_values=remove_none_from_uncertainty_array(tmp_values)
                # if decode_up is present we have either 2-dim specification of [decode_up,decode_down] or [decode_up,None]
                if( hasattr(in_file, 'decode_up')):
                    tmp_values_up=variable_loading.read_data_file(utils.resolve_file_name(in_file.name,data_root),in_file.decode_up,**extra_args)
                    tmp_values_up=remove_none_from_uncertainty_array(tmp_values_up)

                # if decode_down is present we have either 2-dim specification of [decode_up,decode_down] or [None,decode_down]
                if( hasattr(in_file, 'decode_down')):
                    tmp_values_down=variable_loading.read_data_file(utils.resolve_file_name(in_file.name,data_root),in_file.decode_down,**extra_args)
                    tmp_values_down=remove_none_from_uncertainty_array(tmp_values_down)

                if(tmp_values_up.size>0 or tmp_values_down.size>0):
                    if(not tmp_values_down.size>0):
                        tmp_values_down=np.full_like(tmp_values_up,np.nan)
                    if(not tmp_values_up.size>0):
                        tmp_values_up=np.full_like(tmp_values_down,np.nan)
                    tmp_values=np.array([tmp_values_up,tmp_values_down]).T

                if(not (tmp_values_up.size>0 or tmp_values_down.size>0 or tmp_values.size>0)):
                    raise TypeError("Something went wrong. Could not read errors")
                
                if(len(list(input_array))>0): # append to already existing data
                    input_array=np.concatenate((input_array,tmp_values))
                else: # overwrite empty array, with the numpy object of the correct dimentionality and dtype
                    input_array=tmp_values

            data_type=getattr(unc_steering,'data_type',None)
            if(data_type is not None and data_type!=''):
                    input_array=np.array(input_array).astype(data_type)

            transformations=getattr(unc_steering,'transformations',[])
            if(isinstance(transformations,str)):
                raise ValueError(f"Parameter 'transformations needs to be a list of transformations(strings), not string.'")
            if(not isinstance(transformations,Iterable)):
                raise ValueError(f"Parameter 'transformations needs to be a list (!) of transformations(strings).'")
            for transformation in transformations:
                input_array=perform_transformation(transformation,global_variables,utils.merge_dictionaries(local_variables,{name:input_array}))
            log.debug(f"this is what we got for uncertainty {name} after reading data: {input_array}, {type(input_array)}, {np.array(input_array).dtype}")

        # Populate underlying numpy_array with 'input_array' and decorate with additional atributes
        obj=np.asarray(input_array).view(cls)
        obj.name = name
        obj.fancy_name = fancy_name
        obj.is_visible = is_visible
        obj.digits = digits
        obj._unc_steering=unc_steering
        if(obj.ndim==2):
            obj.is_symmetric=False
        elif(obj.ndim==1):
            obj.is_symmetric=True
        else:
            raise TypeError(f"Uncertainty can only be either one or two dimensional (is: ndim={obj.ndim}). Provided: {input_array} of type {type(input_array)}.")
        if(obj.dtype=='object'):
            # TODO: Motivation here is to check that no crazy things like [1,2,[3,4],5] (hybrid 1&2-dim) objetcts are provided
            # For now checking that type of ndarray is not an object but that might be problematic if we have mixed types (e.g. [1,'2'])
            # Is this really an issue with astype and transformations available? Need to think it through
            raise TypeError(f"Uncertainty can be only either 1-D or 2-D list (and not a 1/2-D hybrid). Provided: {input_array}.")
        if(not (isinstance(name,str) or name is None)):
            raise TypeError(f"Uncertainty's name has to be string (or None). It cannot be {type(name)} as provided with {name}.")

        ## Timing 
        stop=time.time()
        log.debug(f"It took {stop-start} seconds to create uncertainty {name}")
        
        # Finally, we must return the newly created object:
        return obj

    def __array_finalize__(self, obj):
        if obj is None: return
        if(obj.ndim>2):
            raise TypeError(f"Uncertainty can only be either one or two dimensional (is: ndim={obj.ndim}).")
        self.name = getattr(obj, 'name', None)
        self.fancy_name = getattr(obj, 'name', '')
        self.is_visible = getattr(obj, 'is_visible', True)        
        self.digits = getattr(obj, 'digits', 5)        
        self.is_symmetric = getattr(obj, 'is_symmetric', obj.ndim==1)        
        self._unc_steering = getattr(obj, 'unc_steering', None)
        
    def steering_file_snippet(self):
        #
        # Get the steering file for the Uncertainty object
        #
        if(self._unc_steering): # a steering file was provided:
            log.debug("steering used")
            return self._unc_steering
        else:
            log.debug("creating steering")
            out_json={}
            out_json['name']=self.name
            if(self.fancy_name!=''):
                out_json['fancy_name']=self.fancy_name
            out_json['is_visible']=self.is_visible
            out_json['digits']=self.digits
            out_json['transformations']=[str(self.tolist())]
            return out_json


class Variable(np.ndarray):
    """
    Variable is 1 or 2 dimentional numpy-array-like list containing information about a single variable.
    It represent one column in a single HEPData table.

    When 1-dimensional array is provided, the variable is unbinned,
    while is binned when 2-dimensional array is given


    Variable has to have a non-empty name.

    Variable be created an the following way:

      1) data array (could be 1 or 2-dim) and name of the variable,
      var=Variable([1,2,3],'my_name')

      2) providing dictionary following src/hepdata_maker/schemas/0.0.0/variable.json schema.
      var=Variable(var_steering={"name":"my_name","transformations":[1,2,3]})

    If var_steering is given, it takes precedence over other arguments.
    """
    def __new__(cls:Type[ndarray_super_type],
                input_array:Iterable=[],
                name:str="var",
                is_independent:bool=True,
                is_binned:Optional[bool]=None,
                is_visible:bool=True,
                units:str="",
                digits:int=5,
                var_steering:Optional[Dict[str,Any]]=None,
                global_variables:Dict[str,Any]={},
                local_variables:Dict[str,Any]={},
                data_root:str='./'):

        ## Time the execution
        start=time.time()

        # First we want to get the name (potentially from steering file) to display it in log.debug.
        # We do not want to read all the variables and transformations here as these are more error prone
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
            units=var_steering.get('units',units)
            is_visible=var_steering.get('is_visible',is_visible)
            digits=var_steering.get('digits',digits)

        log.debug(f"Creating new Variable (np.ndarray derived) object: {name}")
        log.debug(f"parameters passed:")
        log.debug(f"{locals()}")

        ## As the second step we read the steering file to get values for actual variable (and not yet the associated errors)
        if(var_steering):
            input_array=[] # Steering files overrides arguments
            in_files=getattr(var_steering,'in_files',[])
            for in_file in in_files:
                extra_args={k: in_file[k] for k in ('delimiter', 'file_type', 'replace_dict', 'tabular_loc_decode') if k in in_file}
                tmp_values=variable_loading.read_data_file(utils.resolve_file_name(in_file.name,data_root),in_file.decode,**extra_args)
                if(len(list(input_array))>0): # array already filled, just expand
                    input_array=np.concatenate((input_array,tmp_values))
                else:
                    input_array=tmp_values

            data_type=getattr(var_steering,'data_type',None)
            if(data_type is not None and data_type!=''):
                input_array=np.array(input_array).astype(data_type)
            transformations=getattr(var_steering,'transformations',[])
            for transformation in transformations:
                input_array=perform_transformation(transformation,global_variables,utils.merge_dictionaries(local_variables,{name:input_array}))

        # Populate underlying numpy_array with 'input_array'
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
        obj.units = units
        obj.digits = digits
        
        ## Finally we can read the steering file to get values for associated errors)
        if(var_steering):
            obj.fancy_name=var_steering.get('fancy_name','')
            obj._var_steering=var_steering
            obj.qualifiers=getattr(var_steering,'qualifiers',[])
            errors=getattr(var_steering,'errors',[])
            for error_info in errors:
                current_local_variables=utils.merge_dictionaries(local_variables,{name:input_array},{var_err.name:var_err for var_err in obj.uncertainties})
                unc=Uncertainty(unc_steering=error_info,local_variables=current_local_variables,global_variables=global_variables,data_root=data_root)
                obj.add_uncertainty(unc)
            if(obj.multiplier):
                ## TODO: think what we want to do with multipliers consistently
                obj.qualifiers.append({"multiplier":obj.multiplier})
            
            if hasattr(var_steering, 'regions'):
                current_local_variables=utils.merge_dictionaries(local_variables,{name:input_array},{var_err.name:var_err for var_err in obj.uncertainties})
                obj.regions=get_matching_based_variables(var_steering.regions,global_variables,current_local_variables,var_lenght=obj.size) # type: ignore
            if hasattr(var_steering, 'grids'):
                current_local_variables=utils.merge_dictionaries(local_variables,{name:input_array},{var_err.name:var_err for var_err in obj.uncertainties})
                obj.grids=get_matching_based_variables(var_steering.grids,global_variables,current_local_variables,var_lenght=obj.size) # type: ignore
            if hasattr(var_steering, 'signal_names'):
                current_local_variables=utils.merge_dictionaries(local_variables,{name:input_array},{var_err.name:var_err for var_err in obj.uncertainties})
                obj.signal_names=get_matching_based_variables(var_steering.signal_names,global_variables,current_local_variables,var_lenght=obj.size) # type: ignore

        ## Timing        
        stop=time.time()
        log.debug(f"It took {stop-start} seconds to create variable {name}")

        return obj

    def __array_finalize__(self, obj):
        if obj is None: return
        if(obj.ndim>2):
            raise TypeError(f"Variable can only be either one or two dimensional (is: ndim={obj.ndim}).")
        self.name = getattr(obj, 'name', None)
        self.fancy_name = getattr(obj, 'fancy_name', '')
        self.is_independent = getattr(obj, 'is_independent', True)
        self.is_binned = getattr(obj, 'is_binned', obj.ndim==2)
        self.is_visible = getattr(obj, 'is_visible', True)
        self.qualifiers = getattr(obj, 'qualifiers',[])
        self.multiplier = getattr(obj, 'multiplier', None)
        self.units = getattr(obj, 'units', "")
        self._uncertainties = getattr(obj, 'uncertainties', [])
        self.region = getattr(obj,'region',np.array([[]]*len(obj)))
        self.grid = getattr(obj,'grid',np.array([[]]*len(obj)))
        self.signal = getattr(obj,'signal',np.array([[]]*len(obj)))
        self.digits = getattr(obj, 'digits', 5)
        self._var_steering=getattr(obj, 'var_steering', None)
    
    def _steering_unc_names(self)->List[str]:
        if(self._var_steering is None or 'errors' not in self._var_steering):
            return []
        else:
            return [x['name'] for x in self._var_steering['errors']]
    def _update_unc_steering(self,uncertainty):
        if(self._var_steering):
            err_name=uncertainty.name
            new_unc_steering=uncertainty.steering_file_snippet()
            if 'errors' not in self._var_steering:
                self._var_steering['errors']=[]
            if(err_name in self._steering_unc_names()):
                self._var_steering['errors'][self._steering_unc_names().index(err_name)]=new_unc_steering
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
                    self._var_steering['errors'].pop(self.uncertainty_index(uncertainty_name))

    def get_uncertainty_names(self):
        return [unc.name for unc in self.uncertainties]

    def _add_unc_to_dict_safely(self,uncertainty):
        ## TODO: currently uncertainty can have empty string ('') as a name
        ##       this means that it will not be accesible. Can we do something about it?
        if(not isinstance(uncertainty, Uncertainty)):
            raise TypeError("Unknown object type: {0}".format(str(type(uncertainty))))
        name=uncertainty.name
        if(name in self.__dict__):
            raise ValueError(f"You try to add uncertainty with name {name} to variable {self.name}. This name cannot be used as is already taken, see __dict__: {self.__dict__}.")
        self.__dict__[name]=uncertainty

    def add_uncertainty(self,
                        uncertainty:Uncertainty)->None: 
        """
        Add an uncertainty to the variable.
        This updates variable's uncertainties table as well as
        __dict__ dictionary.

        Args:
          uncertainty: uncertainty (of type Uncertainty) to add
        """
        log.debug(f"Adding uncertainty to Variable {self.name}. Parameters passed: {locals()}")
        if isinstance(uncertainty, Uncertainty):
            if(self.size!=len(uncertainty)):
                raise ValueError(f"Uncertainty {uncertainty.name, (uncertainty.tolist())} has different dimention ({len(uncertainty)}) than the corresponding variable {self.name} ({self.tolist()},{self.size}).")
            if(uncertainty.name in self.get_uncertainty_names()):
                raise ValueError(f"Uncertainty {uncertainty.name} is already present in the variable variable {self.name}.")
            self.uncertainties.append(uncertainty)
            self._add_unc_to_dict_safely(uncertainty)
            self._update_unc_steering(uncertainty)
        else:
            raise TypeError("Unknown object type: {0}".format(str(type(uncertainty))))
        
    def update_uncertainty(self,
                           new_unc:Uncertainty) ->None:
        """
        Update uncertainty with a new one.
        Uncertainty which name matches the new one is being replaced.
        If no uncertainty of that name is present, the uncertainty is added
        This updates variable's 'uncertainties' as well as
        __dict__ dictionary.

        Args:
          new_unc: uncertainty (of type Uncertainty) to add
        """
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

    def uncertainty_index(self,uncertainty_name:str)->int:
        """
        Get the index of the uncertainty in the variable's uncertainties table

        Args:
          uncertainty_name -- name of the uncertainty to look for
        """
        if(not isinstance(uncertainty_name,str)):
            raise TypeError(f"Uncertainty's name needs to be a string. Trying to find uncertainty based on object type ({type(uncertainty_name)}) failed!")
        return self.get_uncertainty_names().index(uncertainty_name)
    
    def delete_uncertainty(self,uncertainty_name:str)->None:
        """
        Delete the uncertainty
        This updates variable's uncertainties table as well as
        __dict__ dictionary.

        Args:
          uncertainty_name -- name of the uncertainty to remove
        """
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
    def uncertainties(self,uncertainties:List[Uncertainty])->None:
        """uncertainties setter that updates __dict__"""
        
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
        """
        Get the steering file for the Variable object
        """
        if(self._var_steering): # a steering file was provided:
            return self._var_steering
        else:
            out_json={}
            out_json['name']=self.name
            if(self.fancy_name!=''):
                out_json['fancy_name']=self.fancy_name
            out_json['is_visible']=self.is_visible
            out_json['digits']=self.digits
            out_json['transformations']=[self.tolist()]
            out_json['uncertainties']=[]
            for unc in self.uncertainties:
                out_json['uncertainties'].append(unc.steering_file_snippet())
            self._var_steering=out_json
            return out_json

class Resource():
    """
    A class containing informations on additional resource,
    like tarball/image etc., attached to the HEPData record.
    """
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
        output_json['copy_file']=self.copy_file
        return output_json


class Table(object):
    """
    A table is a collection of variables.

    It also holds meta-data such as a general description,
    the location within the paper, etc.

    Table has to have a non-empty name.
    """
    
    def __init__(self,
                 name:str='table',
                tab_steering:Optional[Dict[str,Any]]=None,
                global_variables:Dict[str,Any]={},
                local_variables:Dict[str,Any]={},
                data_root:str='./'):

        ## Time execution
        start=time.time()

        if(tab_steering):
            if(not isinstance(tab_steering,utils.objdict)):
                # TODO Do we really want to go further with objdict?! Either allow (and automatically translate to dict) or just fall back to dict?
                if (isinstance(tab_steering,dict)):
                    tab_steering=utils.objdict(tab_steering)
                else:
                    raise TypeError("'tab_steering' needs to be of type utils.objdict or dict!")
            name=tab_steering.get('name',name)
            should_be_processed=getattr(tab_steering,'should_be_processed',True)
            if(not should_be_processed):
                raise ValueError(rf"table {name} has 'should_be_processed' flag set to False. Class Table should not see this flag at all (prune prior to constructor).")

        log.debug(f"Creating new Table: {name}")

        if(name is None or not isinstance(name,str)):
            raise TypeError(f"Table's name needs to be of type string, not {type(name)}.")
        self._name = None
        self.name = name
        self.fancy_name = ''
        self._variable_lenght=0
        self._variables:List[Variable] = []
        self.title = ""
        self.location = ""
        self.keywords = {}
        self._resources:List[Resource] = []
        self.images:List[Dict[str,Any]] = []
        # TODO: Unify treatment of images and resources
        self._tab_steering:Optional[Dict[str,Any]]=None
        if(tab_steering):
            self._tab_steering=tab_steering
            self.images=getattr(tab_steering,'images',[])
            for image_info in self.images:
                current_image_path=utils.resolve_file_name(image_info['name'],data_root)
                if(not os.path.isfile(current_image_path)):
                    raise ValueError(f"Cannot find image file of table '{name}' under the path '{current_image_path}'. Please check it!")
            additional_resources=getattr(tab_steering,'additional_resources',[])
            for resource_info in additional_resources:
                res=Resource(res_steering=resource_info)
                self._resources.append(res)
                current_resource_path=utils.resolve_file_name(resource_info['location'],data_root)
                if(res.copy_file and not os.path.isfile(current_resource_path)):
                    raise ValueError(f"Cannot find additional_resource with description \'{resource_info['description']}\' under the path '{current_resource_path}'. Please check it!")
            title=getattr(tab_steering,'title',None)
            if( title is not None):
                potential_file_path=utils.resolve_file_name(title,data_root)
                if(os.path.isfile(potential_file_path)):
                    # Provide file with table title ( e.g. website output)
                    log.debug(f"Title field of table {name} points to a text file. Content of the file will be used as table title.")
                    self.title=open(potential_file_path).read()
                else:
                    log.debug(f"Title fielf of table {name} points to a text file. Content of the file will be used as table title.")
                    self.title=title
            if( hasattr(tab_steering, 'location')):
                self.location=tab_steering.get('location','')
            if( hasattr(tab_steering, 'keywords')):
                self.keywords=tab_steering.get('keywords','')

            variables=getattr(tab_steering,'variables',[])
            for variable_info in variables:
                local_variables=utils.merge_dictionaries(self.__dict__)
                var=Variable(var_steering=variable_info,global_variables=global_variables,local_variables=local_variables,data_root=data_root)
                self.add_variable(var)
            self.fancy_name=getattr(tab_steering,'fancy_name',None)

        ## Timing
        stop=time.time()
        print(f"It took {stop-start} seconds to create table {name}.")

    @property
    def name(self):
        """Name getter."""
        return self._name

    @name.setter
    def name(self, name:str):
        """Name setter."""
        if len(name) > 64:
            raise ValueError("Table name must not be longer than 64 characters.")
        self._name = name

    def _steering_var_names(self)->List[str]:
        if(self._tab_steering is None or 'variables' not in self._tab_steering):
            return []
        else:
            return [x['name'] for x in self._tab_steering['variables']]
    def _update_var_steering(self,variable:Variable)->None:
        #
        # update steering file when variable is being added/updated
        #
        if(self._tab_steering):
            var_name=variable.name
            new_var_steering=variable.steering_file_snippet()
            if('variables' not in self._tab_steering):
                self._tab_steering['variables']=[]
            if(var_name in self._steering_var_names()):
                self._tab_steering['variables'][self._steering_var_names().index(var_name)]=new_var_steering
            else:
                self._tab_steering['variables'].append(new_var_steering)
    def _delete_var_steering(self,variable:Variable)->None:
        #
        # delete variable from steering file when variable is being deleted
        #
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

    def get_variable_names(self)->List[str]:
        return [var.name for var in self.variables]

    def variable_index(self,variable_name:str)->int:
        """
        Get the index of the variable in the table's variables table

        Args:
          variable_name: name of the variable to look for
        """
        if(not isinstance(variable_name,str)):
            raise TypeError(f"Variable's name needs to be a string. Trying to find variable based on object type ({type(variable_name)}) failed!")
        return self.get_variable_names().index(variable_name)

    def _add_var_to_dict_safely(self,variable:Variable)->None:
        if(not isinstance(variable, Variable)):
            raise TypeError("Unknown object type: {0}".format(str(type(variable))))
        name=variable.name
        if(name in self.__dict__):
            raise ValueError(f"You try to add variable with name {name} to table {self.name}. This name, however, cannot be used as is already taken, see __dict__:{self.__dict__}.")
        self.__dict__[name]=variable

    def add_variable(self, variable:Variable)->None:
        """
        Add a variable to the table.
        This updates table's variables table as well as
        __dict__ dictionary.

        Args:
          variable: variable (of type Variable) to add
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

    def update_variable(self,new_var:Variable)->None:
        """
        Update variable with a new one.
        Variable which name matches the new one is being replaced.
        If no variable of that name is present, the variable is added
        This updates table's 'variables' as well as
        __dict__ dictionary.

        Args:
          new_var: variable (of type Variable) to add
        """
        if(not isinstance(new_var, Variable)):
            raise TypeError("Table can be updated with a variable, not with object type: {0}".format(str(type(new_var))))
        log.debug(f"Updating variable {new_var.name} of variable {self.name}. Parameters passed: {locals()}")
        no_matching=True
        for index,var in enumerate(self.variables):
            if(var.name==new_var.name):
                no_matching=False
                self.variables[index]=new_var
                if(not new_var.name in self.__dict__):
                    log.warning(f"The variable {new_var.name} to be updated was not found in __dict__ of table {self.name} however it should be there... You probably use the code not as it was intended to be used!")
                self.__dict__[new_var.name]=new_var # here we do not use _add_var_to_dict_safely as the variable name should already be in __dict__ (or not be there at all)
        if(no_matching):
            log.warning(f"You tried to update variable {new_var.name} in table {self.name}, but no variable of such name found in the table! Adding variable instead!")
            self.add_variable(new_var)
            self._update_var_steering(new_var)

    def delete_variable(self,variable_name:str)->None:
        """
        Delete the variable
        This removes the variable from tables's variables table as well as
        __dict__ dictionary.

        Args:
          variable_name -- name of the variable to remove
        """
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
        return self._variables

    @variables.setter
    def variables(self, variables:List[Variable]):
        
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

    @property
    def resources(self):
        return self._resources

    ### TODO: We probably do not need a setter for resources...
    
    def steering_file_snippet(self)->Dict[str,Any]:
        """
        Get the steering file for the Table object.
        """
        if(self._tab_steering): # a steering file was provided:
            return self._tab_steering
        else:
            output_json={}
            output_json['name']=self.name
            output_json['title']=self.title
            output_json['location']=self.location
            output_json['keywords']=dict(self.keywords)
            output_json['images']=self.images
            output_json['resources']=self.resources
            output_json['variables']=[]
            for variable in self.variables:
                output_json['variables'].append(variable.steering_file_snippet())
            return output_json
        
def fix_zero_error(variable:Variable)->List[np.ndarray]:
    """
    This function replaces null errors with '' for the cases when variable is zero

    Args:
      variable: variable (of type Variable) to go through

    Returns:
      list of numpy arrays with updated error values
    """
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
    
    fixed_errors=[]

    # For assymetric case if one error is present we do not need to apply fix ( thus logical and for up-down pairs):
    need_zero_error_fix=np.repeat(np.logical_and.reduce(need_zero_error_fix,axis=1)[:,np.newaxis], 2, axis=1)
    
    for index,error in enumerate(variable.uncertainties):
        if(error.is_symmetric):
            fixed_errors.append(np.where(np.logical_and.reduce(need_zero_error_fix,axis=1),np.full_like(error,'',dtype=str),error))
        else:
            fixed_errors.append(np.where(need_zero_error_fix,np.full_like(error,['',''],dtype=str),error))
    return fixed_errors

def get_matching_based_variables(match_definitions:List[Dict[Literal['name', 'matching'],Any]],
                                 global_dict=None,
                                 local_dict=None,
                                 var_lenght=0):
    """
    Function to construct an array with values depending on the condition provided by user

    The idea is to define things like, for example, 'region' for a table,
    indicating which analysis region is used.

    Example:
      Assume we want to have region="SRB" when "MET>100 && mt2<450".
      For ``MET=[50 ,150,250]`` and ``mt2=[300,400,500]``,
      when provided with argument
      ``matching_definitions=[{name:"SRB","matching":["np.logical_and(MET>100,mt2<450)"]}]``
      will give output of ``[None,SRB, None]``.

    Args:
      match_definitions: list of dictionaries defining matching conditions and
        the value associated with the match.

        Each dictionary has to have field 'name' (value of variable when condition is met)
        and 'matching' -- list of cuts and indices for which the condition is met.

        Conditions are concacanated to each other.

        In the example above ``matching_definitions=[{name:"SRB","matching":["np.logical_and(MET>100,mt2<450)"]}``
        is equivalent to  ``matching_definitions=[{name:"SRB","matching":[1]}`` (index specifying position that matches)

      submission_dict: collections of variables and other known objects to be used in the transformation
      local_vars: yet another collection of variables known to be used in the transformation
      var_lenght: lenght of the corresponding variable/table (in case index is is chosen for matching specification)
    """
    result=None
    for specification in match_definitions:
        var=specification.get('name',None)
        if(var is None):
            raise ValueError(f"matching_definitions have to have name for each specification.")
        cuts=specification.get('matching',[])
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
                    ToAppend=np.array([[None]]*len(var_lenght))
                    ToAppend[cut]=var
                if(not result):
                    result=ToAppend
                else:
                    result=np.concatenate((result,ToAppend),axis=1)
            else:
                raise TypeError("Variable cutDefinitions has improper content.")
    return result

def get_name(obj:Union[Uncertainty,Variable,Table],
             use_fancy_names:bool)->str:
    """
    Function to select name of Uncertainty/Variable/Table depending on
    whether fancy_name is present and flag to use it is specified.
    """
    if(not hasattr(obj,"name")):
        raise TypeError("objected provided does not contain 'name' field")
    name=obj.name
    if(use_fancy_names):
        fancy_name=getattr(obj,'fancy_name','')
        if(fancy_name!=''):
            name=fancy_name
        else:
            log.info(f"fancy name was requested but it is empty for object {obj.name} of {type(obj)}.")
    return name

class Submission():
    """
    Submission collects all information required to make hepdata submission (and more!).
    """
    def __init__(self):
        self._tables:List[Table]=[]
        self._resources:List[Resource]=[]
        self._config:Dict[str,Any]={}
        self._has_loaded=False
        self.comment=""
        self.record_ids:List[str]=[]
        self.data_license:Dict[str,Any]={}
        self.generate_table_of_content=False

    def get_table_names(self)->List[str]:
        return [tab.name for tab in self.tables]

    def table_index(self,table_name:str)->int:
        """
        Get the index of the table in the submission
        Args:
          table_name: name of the uncertainty to look for
        """
        if(not isinstance(table_name,str)):
            raise TypeError(f"Table's name needs to be a string. Trying to find uncertainty based on object type ({type(table_name)}) failed!")
        return self.get_table_names().index(table_name)

    def get_resource_locations(self)->List[str]:
        """
        Get the 'location' of the additional_resource in the submission.
        For resources there is no name, so location (link or path to file)
        is what differenciate one from another.
        """
        return [res.location for res in self._resources]

    def resource_index(self,resource_location:str)->int:
        """
        Get the index of the additional_resource in the submission

        Args:
          resource_location: location (link/path) of the resource to look for
        """
        if(not isinstance(resource_location,str)):
            raise TypeError(f"Resource location needs to be a string. Trying to find resource based on object type ({type(resource_location)}) failed!")
        return self.get_resource_locations().index(resource_location)

    def create_table_of_content(self)->None:
        """
        Create table of content based on the matterial available.

        The created table of content is put into comment for a table 'overview.yaml' (a dummy one),
        this comment can be changed if requred.

        If overview.yaml already exisits, the table of content will NOT be recreated
        """
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
                          config_file_path: str='')->None:
        """
        Function to read steering file (just read with dereferencing jsonrefs, nothing more).
        Please use load_table_config to implement the steering_file information.

        Args:
          config_file_path: path to the steering_file that should be used
        """
        if(not os.path.isfile(config_file_path)):
            raise ValueError(f"Could not find config file {config_file_path}. Please check the path provided.")
        with open(config_file_path, 'r') as stream:
            #print("file://"+os.path.abspath(os.path.dirname(config_file_path)),config_file_path)
            config_loaded = jsonref.load(stream,base_uri="file://"+os.path.abspath(os.path.dirname(config_file_path))+"/",object_pairs_hook=OrderedDict)
        self.config=config_loaded
        
    def load_table_config(self,
                          data_root: str='./',
                          selected_table_names:List[Tuple[str,bool]]=[])->None:
        """
        Function to populate information in Submission from
        already read steering file (see also 'read_table_config').

        Args:
          config_file_path: path to the steering_file that should be used
          selected_table_names: names of the tables to be loaded. If empty, all are loaded.
        """
        if(self._has_loaded):
            log.warning("You have already loaded information from a(nother?) steering file. If any table names will be loaded again (without prior explicite deletions) expect errors being raised!")
        self._has_loaded=True

        if('generate_table_of_content' in self.config):
            self.generate_table_of_content=self.config['generate_table_of_content']
        # self.config should aready have the correct information as checked on schema check in config setter 
        if('additional_resources' in self.config):
            for resource_info in [utils.objdict(x) for x in self.config['additional_resources']]:
                res=Resource(res_steering=resource_info)
                self.add_resource(res)
        if('tables' in self.config):
            for table_info in [utils.objdict(x) for x in self.config['tables']]:
                global_variables=utils.merge_dictionaries(self.__dict__,{"np":np},{"re":re},{"scipy.stats":scipy.stats},{"scipy.special":scipy.special},{"ufs":ufs})
                table_name=table_info.get('name',None)
                if(table_name is None):
                    raise ValueError("In {self.config} table needs to have a name specified!")
                should_be_processed=getattr(table_info,'should_be_processed',True)
                if(not should_be_processed):
                    log.warning(rf"table {table_name} has 'should_be_processed' flag set to False. Skipping.")
                    continue
                if(len(selected_table_names)>0 and (table_name not in [pair[0] for pair in selected_table_names])):
                    log.debug(f"skipping loading table {table_name} as not present in selected_table_names: {selected_table_names}")
                    continue
                console.rule(f"table {table_name}")
                table=Table(tab_steering=table_info,global_variables=global_variables,data_root=data_root)
                self.add_table(table)
        self.comment=self.config.get('comment',"")
        self.record_ids=self.config.get('record_ids',[])
        self.data_license=self.config.get('data_license',{})

    def create_hepdata_record(self,
                              data_root:str='./',
                              outdir:str='submission_files',
                              use_fancy_names:bool=False)->None:
        """
        Actual record creation based on information stored
        """
        hepdata_submission = hepdata_lib.Submission()
        hepdata_submission.comment=self.comment
        hepdata_submission.record_ids=self.record_ids
        hepdata_submission.data_license=self.data_license

        if(self.generate_table_of_content):
            self.create_table_of_content()

        for resource in self.resources:
            hepdata_submission.add_additional_resource(resource.description,utils.resolve_file_name(resource.location,data_root),resource.copy_file)
        for table in self.tables:
            table_name=get_name(table,use_fancy_names)

            hepdata_table = hepdata_lib.Table(table_name)
            hepdata_table.description = table.title
            hepdata_table.location = table.location
            hepdata_table.keywords = table.keywords
            #print("hepdata_table keywords",hepdata_table.keywords)
            for image_info in table.images:
                hepdata_table.add_image(utils.resolve_file_name(image_info['name'],data_root))
            for resource_info in table.resources:
                #print(resource_info)
                hepdata_table.add_additional_resource(resource_info.description,utils.resolve_file_name(resource_info.location,data_root),resource_info.copy_file)
            for variable in table.variables:
                if(variable.is_visible):
                    variable_name=get_name(variable,use_fancy_names)
                    #print(f"hepdata_creating with {variable_name}",use_fancy_names,variable.name,variable.fancy_name)
                    log.debug(f"Adding variable to table {table_name}; name(var)={variable_name}, is_independent={variable.is_independent},is_binned={variable.is_binned},units={variable.units},values={variable.tolist()}")
                    hepdata_variable=hepdata_lib.Variable(variable_name, is_independent=variable.is_independent, is_binned=variable.is_binned, units=variable.units)
                    hepdata_variable.values=variable.tolist()
                    hepdata_variable.digits=variable.digits
                    #
                    #HACK: Mind fixed_zero_variable is list of ndarray instead of Uncertenties/Variable... need to be fixed (TODO)
                    #
                    fixed_zero_variable=fix_zero_error(variable)
                    #
                    for index,unc in enumerate(variable.uncertainties):
                        #print(type(unc),variable.uncertainties[index])
                        if(unc.is_visible):
                            unc_name=get_name(unc,use_fancy_names)
                            hepdata_unc = hepdata_lib.Uncertainty(None if unc_name=='' else unc_name, is_symmetric=unc.is_symmetric)
                            hepdata_unc.values=fixed_zero_variable[index].tolist()
                            #hepdata_unc.digits=unc.digits -- not supported by hepdata_lib
                            hepdata_variable.add_uncertainty(hepdata_unc)
                    if(len(variable.qualifiers)!=0):
                        for qualifier in variable.qualifiers:
                            hepdata_variable.add_qualifier(qualifier['name'],qualifier['value'],qualifier.get('units',''))
                    hepdata_table.add_variable(hepdata_variable)
            hepdata_submission.add_table(hepdata_table)
        hepdata_submission.create_files(outdir)
        if(os.path.isdir(outdir) and os.path.isfile('submission.tar.gz')):
            console.print(f"Submission files created and available under directory {outdir} and as a tarball in submission.tar.gz")

    def _add_tab_to_dict_safely(self,table:Table)->None:
        if(not isinstance(table, Table)):
            raise TypeError("Unknown object type: {0}".format(str(type(table))))
        name=table.name
        if(name in self.__dict__):
            raise ValueError(f"You try to add table with name '{name}'. This name, however, cannot be used as is already taken, see __dict__:{self.__dict__}.")
        self.__dict__[name]=table

    def insert_table(self,index:int, table:Table)->None:
        """
        Insert a table in to position 'index' in the submission.
        This updates submission's 'tables' as well as
        __dict__ dictionary.

        Args:
          index: position where to insert the table
          table: table (of type Table) to add
        """
        if isinstance(table, Table):
            log.debug(f"Adding table {table.name} to the submission")
            self.tables.insert(index,table)
            self._add_tab_to_dict_safely(table)
        else:
            raise TypeError("Unknown object type: {0}".format(str(type(table))))
        
    def add_table(self, table:Table)->None:
        """
        Add a table to the submission.
        This updates submission's 'tables' as well as
        __dict__ dictionary.

        Args:
          table: table (of type Table) to add
        """
        if isinstance(table, Table):
            log.debug(f"Adding table {table.name} to the submission")
            self.tables.append(table)
            self._add_tab_to_dict_safely(table)
        else:
            raise TypeError("Unknown object type: {0}".format(str(type(table))))
        
    def update_table(self,new_tab:Table)->None:
        """
        Update table with a new one.
        Table which name matches the new one is being replaced.
        If no table of that name is present, the table is simply added

        This updates submission's 'tables' as well as
         __dict__ dictionary.

        Args:
          new_tab: table (of type Table) to add
        """
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
                    log.warning(f"The table {new_tab.name} to be updated was not found in __dict__ of submission object however it should be there... You probably use the code not as it was intended to be used!")
                self.__dict__[new_tab.name]=new_tab # here we do not use _add_tab_to_dict_safely as the table name should already be in __dict__ (or not be there at all)
        if(no_matching):
            log.warning(f"You tried to update table {new_tab.name}, but no table of such name found in the table! Simply adding the table instead.")
            self.add_table(new_tab)
            
    def delete_table(self,table_name:str)->None:
        """
        Delete the table
        This updates submission's 'tables' as well as
        __dict__ dictionary.

        Args:
          table_name: name of the table to remove
        """
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

    def insert_resource(self,index:int, resource:Resource)->None:
        """
        Insert a resource in to position 'index' in the submission.

        Args:
          index    -- position where to insert the resource
          resource -- resource (of type Resource) to add
        """
        if isinstance(resource, Resource):
            log.debug(f"Adding resource {resource.location} to the submission")
            self.resources.insert(index,resource)
        else:
            raise TypeError("Unknown object type: {0}".format(str(type(resource))))
        
    def add_resource(self, resource:Resource)->None:
        """
        Add a resource in the submission.

        Input variables:
         resource -- resource (of type Resource) to add
        """
        if isinstance(resource, Resource):
            log.debug(f"Adding resource {resource.location} to the submission")
            self.resources.append(resource)
        else:
            raise TypeError("Unknown object type: {0}".format(str(type(resource))))

    def delete_resource(self,resource_location:str)->None:
        """
        Delete the resource from the submission

        Args:
          resource_location -- location of the resource to remove
        """
        if(resource_location not in self.get_resource_locations()):
            log.warning(f"You try to remove resource {resource_location} that is not found in the submission object.")
            return
        else:
            del self.resources[self.resource_index(resource_location)]

    @property
    def config(self)->Dict[str,Any]:
        return self._config

    @config.setter
    def config(self, config:Dict[str,Any])->None:
        # Check schema of the submission steering file:
        utils.check_schema(config,'steering_file.json')
        self._config=config
        
    @property
    def tables(self)->List[Table]:
        return self._tables

    @tables.setter
    def tables(self, tables:List[Table])->None:
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
    def resources(self)->List[Resource]:
        return self._resources

    @resources.setter
    def resources(self, resources:List[Resource]):
        self._resources = resources

    def steering_file_snippet(self):
        """
        Get the steering file for the Submission
        Mind, that it is not the 'config' file that is being return, but
        instead it is rebuild from the actual information stored in the Submission
        This saves us from the need to update 'config' if a table is added or removed.
        """
        output_json={}
        output_json['type']='steering'
        if(self.comment!=''):
            output_json['comment']=self.comment
        output_json["generate_table_of_content"]=self.generate_table_of_content
        json_tables=[]
        for table in self.tables:
            json_tables.append(table.steering_file_snippet())
        output_json['tables']=json_tables
        utils.check_schema(output_json,'steering_file.json')
        return output_json


def add_rich_error_tree_from_var(variable:Variable,
                                 baseTree:Optional[rich.tree.Tree]=None)-> rich.tree.Tree:
    """
    Function to read all errors from a Variable object and
    attach them to rich.tree for nice visual effect
    """
    if(not isinstance(variable,Variable)):
        raise ValueError(f"arugument 'variable' needs to be of type Submission.Variable")
    if(baseTree is None):
        baseTree=rich.tree.Tree(variable.name+" (var)")
    if(not isinstance(baseTree,rich.tree.Tree)):
        raise ValueError(f"I require baseTree to be of type rich.tree.Tree (is: {type(baseTree)}).")
    if(len(variable.uncertainties)>0):
        baseTreeLabel=str(baseTree.label).split()[0]+'.' if len(str(baseTree.label))>0 else ''
        for err in variable.uncertainties:
            if(not hasattr(err,'name')):
                raise ValueError(f"I need error to has attribute name")
            baseTree.add(baseTreeLabel+err.name+" (err)")
    return baseTree

def add_rich_var_tree_from_table(table:Table,
                                 baseTree:rich.tree.Tree=None) -> rich.tree.Tree:
    """
    Function to read all variables from a Table object and
    attach them to rich.tree for nice visual effect
    """
    if(not isinstance(table,Table)):
        raise ValueError(f"arugument 'table' needs to be of type Submission.Table")
    if(baseTree is None):
        baseTree=rich.tree.Tree(table.name)
    if(not isinstance(baseTree,rich.tree.Tree)):
        raise ValueError(f"I require baseTree to be of type rich.tree.Tree (is: {type(baseTree)}).")
    if(len(table.variables)>0):
        baseTreeLabel=str(baseTree.label).split()[0]+'.' if len(str(baseTree.label))>0 else ''
        for var in table.variables:
            spec_var_tree=rich.tree.Tree(baseTreeLabel+str(var.name)+" (var)")
            spec_var_tree=add_rich_error_tree_from_var(var,spec_var_tree)
            baseTree.add(spec_var_tree)
    return baseTree

def rich_highlight_dict_objects(dictionary:Dict[str,Any],
                                             title:str='')->None:
    """
    Highlight Tables, Variables and Uncertainties that can be found in dictionary (with recursive search)
    The result is printed on the screen

    Args:
      dictionary: a dictionary containing Tables/Values or Uncertainties as values
      title: title for the rich.panel printing the information
    """
    log.debug("Inside 'rich_highlight_dict_objects' function")
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
            spec_tab_tree=add_rich_var_tree_from_table(value,spec_tab_tree)
            table_tree.add(spec_tab_tree)
        objects_to_show.append(table_tree)
    if(len(variable_list)>0):
        var_tree=rich.tree.Tree("[bold]Available variables:")
        for key,value in variable_list:
            spec_var_tree=rich.tree.Tree(key+" (var)")
            spec_var_tree=add_rich_error_tree_from_var(value,spec_var_tree)
            var_tree.add(spec_var_tree)
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


def decode_variable_from_hepdata(hepdata_variable:Dict[str,Any],
                                 in_file:str,
                                 is_independent:bool,
                                 var_index:int=0)->Dict[str,Any]:
    """
    Function to decode information on variable from subset of hepdata data-yaml
    It returns hepdata_maker-style variable steering snippet
    """
    
    tmp_name=hepdata_variable['header']['name']
    fancy_var_name=tmp_name
    var_name=tmp_name if is_name_correct(tmp_name) else f"var_{'ind' if is_independent else 'dep'}_{var_index}"
    var_units=hepdata_variable['header'].get('units',"")

    errors=[]
    base_var_field_name="independent_variables" if is_independent else "dependent_variables"
    qualifiers=hepdata_variable.get('qualifiers',[])
    if(len(hepdata_variable['values'])>0):
        error_names=list(OrderedDict.fromkeys(jq.all('.values[].errors?[]?.label',hepdata_variable)))
        #start=time.time()
        for err_index,tmp_name in enumerate(error_names):
            # Now, names can be omitted for uncertainties...
            if(tmp_name is None):
                lookup_name="null"
                err_name=''
                err_fancy_name=''
            else:
                lookup_name=f'"{tmp_name}"'
                err_name=tmp_name if is_name_correct(tmp_name) else f"err_{err_index}"
                err_fancy_name=tmp_name
            # Here we try to save some time in case error is present in the first entry.
            err=jq.all(f'.errors?[]?| select(.label=={lookup_name})',hepdata_variable['values'][0])
            if(err==[]):
                # if it is not, we need to loop over all entries (more time consuming)
                err=jq.first(f'.values[].errors?[]?| select(.label=="{lookup_name}")',hepdata_variable)
            else:
                err=err[0]
            
            if('asymerror' in err):
                err_decode=f".{base_var_field_name}[{var_index}].values[].errors| if .==null then [0,0] else .[] | select(.label=={lookup_name}) | .asymerror | [.minus,.plus] end"
            elif('symerror' in err):
                err_decode=f".{base_var_field_name}[{var_index}].values[].errors| if .==null then null else .[] | select(.label=={lookup_name}) | .symerror end"
            else:
                raise ValueError("I have not expected error that is not symerror not asymerror!")
            err_steering={"name":err_name,"fancy_name":err_fancy_name,"in_files":[{"name":in_file,"decode":err_decode}]} # No units are present for hepdata records as far as I am aware.
            errors.append(err_steering)
        #stop=time.time()
        #print(f"timing to get through {len(error_names)} errors={stop-start}")
        if('high' in hepdata_variable['values'][0]):
            decode=f".{base_var_field_name}[{var_index}].values[] | [.low,.high]"
        else:
            decode=f".{base_var_field_name}[{var_index}].values[].value"
        return {"in_files":[{"name":in_file,"decode":decode}],"name":var_name,'fancy_name':fancy_var_name,"is_independent":is_independent,"errors":errors,"qualifiers":qualifiers,"units":var_units}
    else:
        return {"name":var_name,"fancy_name":fancy_var_name,"is_independent":is_independent,"qualifiers":qualifiers,"units":var_units}
