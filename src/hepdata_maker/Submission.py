from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import numpy as np
import json
from collections import OrderedDict
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
from . import variable_loading

class Uncertainty(np.ndarray):
    def __new__(cls, input_array, name, is_visible=True, digits=5):
        # Input array is an already formed ndarray instance
        # We first cast to be our class type
        #print("In Uncertainty new")
        #tmp_array=np.asarray(input_array)
        #if(len(tmp_array.shape)==2):
        #    obj = tmp_array.view(cls)
        #elif(len(tmp_array.shape)==1):
        #    #  TODO: Problem if we have str given! 
        #    obj=np.asarray([tmp_array,-1*tmp_array]).T.view(cls)
        #else:
        #    raise ValueError("Uncertainty can only be either one or two dimensional.")
        # add the new attribute to the created instance
        log.debug(f"Creating new Uncertainty object: {name}")
        log.debug(f"   parameters passed {locals()}")
        obj=np.asarray(input_array).view(cls)
        obj.name = name
        obj.is_visible = is_visible
        obj.digits = digits
        if(obj.ndim==2):
            obj.is_symmetric=False
        elif(obj.ndim==1):
            obj.is_symmetric=True
        else:
            raise ValueError("Uncertainty can only be either one or two dimensional.")
        
        # Finally, we must return the newly created object:
        return obj

    def __array_finalize__(self, obj):
        if obj is None: return
        self.name = getattr(obj, 'name', None)
        self.is_visible = getattr(obj, 'is_visible', True)        
        self.digits = getattr(obj, 'digits', 5)        
    def is_error_symmetric(self):
        return pytest.approx(self[:,0])==-self[:,1]

class Variable(np.ndarray):
    def __new__(cls, input_array,name, is_independent=True, is_binned=False, is_visible=True, unit="", values=None,digits=5):
        # Input array is an already formed ndarray instance
        # We first cast to be our class type
        log.debug(f"Creating new Variable (np.ndarray derived) object: {name}")
        log.debug(f"parameters passed:")
        log.debug(f"{locals()}")
        obj = np.asarray(input_array).view(cls)
        # add the new attribute to the created instance
        obj.name = name
        obj.is_independent = is_independent
        obj.is_binned = is_binned
        obj.is_visible= is_visible
        obj.qualifiers = []
        obj.unit = unit
        obj.multiplier=None
        obj.uncertainties = []
        obj.regions=np.array([[]]*len(obj))
        obj.grids=np.array([[]]*len(obj))
        obj.signal_names=np.array([[]]*len(obj))
        obj.digits = digits
        # Finally, we must return the newly created object:
        return obj

    def __array_finalize__(self, obj):
        if obj is None: return
        self.name = getattr(obj, 'name', None)
        self.is_independent = getattr(obj, 'is_independent', True)
        self.is_binned = getattr(obj, 'is_binned', True)
        self.is_visble = getattr(obj, 'is_visible', True)
        self.qualifiers = getattr(obj, 'qualifiers', [])
        self.unit = getattr(obj, 'unit', "")
        self.uncertainties = getattr(obj, 'uncertainties', [])
        self.region = getattr(obj,'region',np.array([[]]*len(self)))
        self.grid = getattr(obj,'grid',np.array([[]]*len(self)))
        self.signal = getattr(obj,'signal',np.array([[]]*len(self)))
        self.digits = getattr(obj, 'digits', 5)  
    def add_uncertainty(self, uncertainty):
        """
        Add a uncertainty to the table
        :param uncertainty: Uncertainty to add.
        :type uncertainty: Uncertainty.
        """
        log.debug(f"Adding uncertainty to Variable {self.name}. Parameters passed: {locals()}")
        if isinstance(uncertainty, Uncertainty):
            if(self.size!=len(uncertainty)):
                raise ValueError(f"Uncertainty {uncertainty.name} has different dimention ({len(uncertainty)}) than the corresponding variable {self.name} ({self.size})")
            self.uncertainties.append(uncertainty)
            self.__dict__[uncertainty.name]=uncertainty
        else:
            raise TypeError("Unknown object type: {0}".format(str(type(uncertainty))))
    def update_unc(self,new_unc):
        log.debug(f"Updating uncertainty {new_unc.name} of variable {self.name}. Parameters passed: {locals()}")
        no_matching=True
        for index,unc in enumerate(self.uncertainties):
            if(unc.name==new_unc.name):
                no_matching=False
                self.uncertainties[index]=new_unc
                self.__dict__[new_unc.name]=new_unc
        if(no_matching):
            raise ValueError(f"You tried to update unc {new_unc.name} in variable {self.name}, but no uncertainty of such name found in the variable!")

class Table(object):
    """
    A table is a collection of variables.
    It also holds meta-data such as a general description,
    the location within the paper, etc.
    """
    
    def __init__(self, name):
        log.debug(f"Creating new Table: {name}")
        self._name = None
        self.name = name
        self._variable_lenght=0
        self.variables = []
        self.title = "Example description"
        self.location = "Example location"
        self.keywords = {}
        #self.additional_resources = []
        self.image_files = []

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

    def add_variable(self, variable):
        """
        Add a variable to the table
        :param variable: Variable to add.
        :type variable: Variable.
        """
        log.debug(f"Adding variable {variable.name} to the table {self.name}")
        if isinstance(variable, Variable):
            if(self._variable_lenght!=0):
                if(self._variable_lenght!=len(variable)):
                    raise ValueError(f"Variable {variable.name} has different number of parameters ({len(variable)}) than other variables in the table {self.name} ({self._variable_lenght})")
            else:
                if(variable.is_visible):
                    self._variable_lenght=len(variable)
            self.variables.append(variable)
            self.__dict__[variable.name]=variable
        else:
            raise TypeError("Unknown object type: {0}".format(str(type(variable))))

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

class Submission():
    
    def __init__(self):
        self._tables=[]
        self._config=[]
    #__init__(self) -- automatic initialisation from hepdata_lib
    def load_table_config(self,
                          config_file_path: str=''):
        # TODO check config_file_path
        with open(config_file_path, 'r') as stream:
            config_loaded = json.load(stream,object_pairs_hook=OrderedDict)
        
        # TODO check loaded config
        
        self._config=config_loaded
    def implement_table_config(self,data_root: str='./',selected_table_names=[]):
        # TODO check not to do the config multiple times
        for table_info in [utils.objdict(x) for x in self._config['tables']]:
            # TODO verify table_info here?
            table_name=table_info.name
            if( not table_info.should_be_processed):
                log.warning(rf"table {table_info.name} has should_be_processed flag set to False. Skipping.")
                continue
            if(len(selected_table_names)>0 and (table_name not in selected_table_names)):
                log.debug(f"skipping loading table {table_name} as not present in selected_table_names: {selected_table_names}")
                continue
            console.rule(f"table {table_name}")
            table=Table(table_name)
            if( hasattr(table_info, 'images')):
                table.images=table_info.images
            if( hasattr(table_info, 'title')):
                if(os.path.isfile(table_info.title)):
                   # Provide file with table title ( e.g. website out)
                   table.title=open(utils.resolve_file_name(table_info.title,data_root)).read()
                else:
                   table.title=table_info.title
            if( hasattr(table_info, 'location')):
                table.location=table_info.location
            if( hasattr(table_info, 'keywords')):
                table.keywords=table_info.keywords
            for variable_info in table_info.variables:
                #print(f"Adding variable: {variable_info.name}")
                ## TODO check that var_name does not contain any special characters (special characters allowe only in fancy names)
                var_name=variable_info.name
                transformations=getattr(variable_info,'transformations',None)
                var_values=None

                for in_file in variable_info.in_files:
                    extra_args={k: in_file[k] for k in ('delimiter', 'file_type', 'replace_dict', 'tabular_loc_decode') if k in in_file}
                    tmp_values=variable_loading.read_data_file(utils.resolve_file_name(in_file.name,data_root),in_file.decode,**extra_args)
                    if(var_values):
                        var_values=np.concatenate((var_values,tmp_values))
                    else:
                        var_values=tmp_values
                if( hasattr(variable_info, 'data_type')):
                    if(variable_info.data_type!='' and var_values is not None):
                        var_values=var_values.astype(variable_info.data_type)
                if(transformations):
                    for transformation in transformations:
                        var_values=variable_loading.perform_transformation(transformation,self.__dict__,table.__dict__|{var_name:var_values})

                #print("Variable: ",var_name,var_values)
                var=Variable(var_values,var_name)
                if( hasattr(variable_info, 'is_visible')):
                        var.is_visible=variable_info.is_visible
                if( hasattr(variable_info, 'is_independent')):
                        var.is_independent=variable_info.is_independent
                if( hasattr(variable_info, 'is_binned')):
                        var.is_binned=variable_info.is_binned
                if( hasattr(variable_info, 'unit')):
                        var.unit=variable_info.unit
                if( hasattr(variable_info, 'multiplier')):
                        var.multiplier=variable_info.multiplier
                if( hasattr(variable_info, 'errors')):
                    if(variable_info.errors):
                        for error_info in variable_info.errors:
                            err_name=error_info.name
                            err_is_visible=error_info.is_visible
                            err_values=None
                            for in_file in error_info.in_files:
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
                                if(err_values):
                                    err_values=np.concatenate((err_values,tmp_values))
                                else:
                                    err_values=tmp_values
                            if( hasattr(error_info, 'data_type')):
                                if(error_info.data_type!='' and error_info.data_type and err_values is not None):
                                    err_values=err_values.astype(error_info.data_type)
                            if( hasattr(error_info, 'transformations')):
                                for transformation in error_info.transformations:
                                    err_values=variable_loading.perform_transformation(transformation,self.__dict__,table.__dict__|{var_name:var_values,err_name:err_values}|{var_err.name:var_err for var_err in var.uncertainties})
                            unc=Uncertainty(err_values,name=err_name,is_visible=err_is_visible)
                            var.add_uncertainty(unc)
                if(var.multiplier):
                    #print(var,var.multiplier)
                    var.qualifiers.append({"multiplier":var.multiplier})
                table.add_variable(var)
                if hasattr(variable_info, 'regions'):
                    var.regions=get_matching_based_variables(variable_info.regions,table.__dict__|{"np":np},local_dict=None)
                if hasattr(variable_info, 'grids'):
                    var.grids=get_matching_based_variables(variable_info.grids,table.__dict__|{"np":np},local_dict=None)
                if hasattr(variable_info, 'signal_names'):
                    var.signal_names=get_matching_based_variables(variable_info.signal_names,table.__dict__|{"np":np},local_dict=None)
                #print(f"added variable {var_name} to table {table.name}")
                
            self.tables.append(table)
            #TODO give warning when name already in the dictionary
            self.__dict__[table_name]=table
            
    def create_hepdata_record(self,data_root:str='./',outdir='submission_files'):
        # Actual record creation based on information stored
        hepdata_submission = hepdata_lib.Submission()
        # TO DO additional resources
        for table in self.tables:
            hepdata_table = hepdata_lib.Table(table.name)
            hepdata_table.description = table.title
            hepdata_table.location = table.location
            hepdata_table.keywords = table.keywords
            for image_info in table.images:
                hepdata_table.add_image(utils.resolve_file_name(image_info['name'],data_root))
            for variable in table.variables:
                if(variable.is_visible):
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
                #TODO give warning when name already in the dictionary
                self.__dict__[table.name]=table
        # finally set the table list
        self._tables = tables
