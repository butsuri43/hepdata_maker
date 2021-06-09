from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import numpy as np
import pytest
import yaml
import copy
import json
from collections import OrderedDict
import collections
import hepdata_lib
import jq
import uproot
import awkward as awk
from hepdata_lib import RootFileReader
import logging
log = logging.getLogger("Submission")
import click

@click.command()
@click.argument('steering_script',type=click.Path(exists=True))

def main(steering_script):
    print(f"Creating submission file based on {steering_script}:")
    submission=Submission()
    submission.load_table_config(steering_script)
    submission.implement_table_config()
    submission.create_hepdata_record()
    print("Submission created in test_submission")

class objdict(collections.OrderedDict):
    def __init__(self, d):
        new_dict=collections.OrderedDict()
        for key, value in d.items():
            if(isinstance(value, collections.abc.Mapping)):
                new_dict[key]=objdict(value)
            elif(isinstance(value, collections.abc.Iterable) and type(value)!=str):
                new_dict[key]=[objdict(entry) if (isinstance(entry, collections.abc.Mapping) and type(value)!=str) else entry for entry in value]
            else:
                new_dict[key]=value
        super().__init__(d)
        self.__dict__.update(new_dict)

class objdict_np(collections.OrderedDict):
    def __init__(self, d):
        new_dict=collections.OrderedDict()
        for key, value in d.items():
            if(isinstance(value, collections.abc.Mapping)):
                new_dict[key]=objdict(value)
            elif(isinstance(value, collections.abc.Iterable) and type(value)!=str):
                new_dict[key]=np.array([objdict(entry) if isinstance(entry, collections.abc.Mapping) else entry for entry in value])
            else:
                new_dict[key]=value
        super().__init__(d)
        self.__dict__.update(new_dict)

class Uncertainty(np.ndarray):
    def __new__(cls, input_array, name, is_visible=True, digits=5):
        # Input array is an already formed ndarray instance
        # We first cast to be our class type
        #print("In Uncertainty new")
        tmp_array=np.asarray(input_array)
        if(len(tmp_array.shape)==2):
            obj = tmp_array.view(cls)
        elif(len(tmp_array.shape)==1):
            #  TODO: Problem if we have str given! 
            obj=np.asarray([tmp_array,-1*tmp_array]).T.view(cls)
        else:
            raise ValueError("Uncertainty can only be either one or two dimensional.")
        # add the new attribute to the created instance
        obj.name = name
        obj.is_visible = is_visible
        obj.digits = digits
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
        obj = np.asarray(input_array).view(cls)
        # add the new attribute to the created instance
        obj.name = name
        obj.is_independent = is_independent
        obj.is_binned = is_binned
        obj.is_visible= is_visible
        obj.qualifiers = []
        obj.unit = unit
        obj.uncertainties = []
        obj.regions=np.array([[]]*len(obj))
        obj.grids=np.array([[]]*len(obj))
        obj.signal_names=np.array([[]]*len(obj))
        obj.digits = digits
        # Finally, we must return the newly created object:
        return obj

    def __array_finalize__(self, obj):
        if obj is None: return
        #print("In array_finalise of Variable",type(obj))
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
        if isinstance(uncertainty, Uncertainty):
            if(self.size!=len(uncertainty)):
                raise ValueError(f"Uncertainty {uncertainty.name} has different dimention ({len(uncertainty)}) than the corresponding variable {self.name} ({self.size})")
            self.uncertainties.append(uncertainty)
            self.__dict__[uncertainty.name]=uncertainty
        else:
            raise TypeError("Unknown object type: {0}".format(str(type(uncertainty))))
    def update_unc(self,new_unc):
        no_matching=True
        for index,unc in enumerate(self.uncertainties):
            if(unc.name==new_unc.name):
                no_matching=False
                self.uncertainties[index]=new_unc
                self.__dict__[new_unc.name]=new_unc
        if(no_matching):
            # probably need to actually rise an error!
            print("<< You are proably doing something wrong here")
            self.add_uncertainty(new_unc)

class Table(object):
    """
    A table is a collection of variables.
    It also holds meta-data such as a general description,
    the location within the paper, etc.
    """
    
    def __init__(self, name):
        self._name = None
        self.name = name
        self._variable_lenght=0
        self.variables = []
        self.table_title = "Example description"
        self.table_location = "Example location"
        self.table_keywords = {}
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
        if isinstance(variable, Variable):
            if(self._variable_lenght!=0):
                if(self._variable_lenght!=len(variable)):
                    raise ValueError(f"Variable {variable.name} has different number of parameters ({len(variable)}) than other variables in the table {self.name} (self._variable_lenght)")
            else:
                self._variable_lenght=len(variable)
            self.variables.append(variable)
            self.__dict__[variable.name]=variable
        else:
            raise TypeError("Unknown object type: {0}".format(str(type(variable))))

def get_array_from_json(file_path,decode):
    print(file_path)
    with open(file_path, 'r') as stream:
        data_loaded = json.load(stream,object_pairs_hook=OrderedDict)
    # TODO exception handling
    return np.array(jq.all(decode.replace("'",'"'),data_loaded))

def get_array_from_yaml(file_path,decode):
    print(file_path)
    with open(file_path, 'r') as stream:
        data_loaded = yaml.safe_load(stream)
    # TODO exception handling
    return np.array(jq.all(decode.replace("'",'"'),data_loaded))

def get_array_from_root(object_path,decode):
    print(object_path)
    file_path=object_path.split(":")[0]
    root_object_path=object_path.split(':')[1]
    
    rreader=RootFileReader(file_path)
    loaded_object_hepdata_lib=None
    
    # need to get information about object type from uproot:
    object_to_be_loaded=uproot.open(file_path).get(root_object_path)
    if( "TH1" in object_to_be_loaded.classname):
        loaded_object_hepdata_lib=rreader.read_hist_1d(root_object_path)
        return np.array(loaded_object_hepdata_lib[decode])
    elif( "TH2" in object_to_be_loaded.classname):
        loaded_object_hepdata_lib=rreader.read_hist_2d(root_object_path)
        return np.array(loaded_object_hepdata_lib[decode])
    elif("RooHist" in object_to_be_loaded.classname or "TGraph" in object_to_be_loaded.classname):
        loaded_object_hepdata_lib=rreader.read_graph(root_object_path)
        return np.array(loaded_object_hepdata_lib[decode])
    else:
        # TODO come up with way to work with general root objects (this is what is returned here).
        #loaded_object_hepdata_lib=rreader.retrieve_object(root_object_path)
        #return loaded_object_hepdata_lib[decode]
        return np.array([])

def get_cut_defined_variables(cutDefinitions,global_dict=None,local_dict=None):
    result=None
    for var,cuts in cutDefinitions.items():
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

def read_data_file(file_name,decode):
    tmp_values=None
    if file_name.lower().endswith(".json"):
        tmp_values=get_array_from_json(file_name,decode)
    elif file_name.lower().endswith(".yaml"):
        tmp_values=get_array_from_yaml(file_name,decode)
    elif file_name.split(":")[0].lower().endswith(".root"):
        tmp_values=get_array_from_root(file_name,decode)
    else:
        raise TypeError(f"File {file_name}: unsuported file type!")
    return tmp_values

def fix_zero_error(variable):
    tmp_need_zero_error_fix=(variable==np.zeros_like(variable))
    tmp_need_zero_error_fix=np.array([tmp_need_zero_error_fix,tmp_need_zero_error_fix]).T # translating to the (2,N) shape of errors
    for error in variable.uncertainties:
        tmp_need_zero_error_fix=tmp_need_zero_error_fix&(error==np.zeros_like(error))
    need_zero_error_fix=tmp_need_zero_error_fix
    
    fixed_variables=[]
    for index,error in enumerate(variable.uncertainties):
        fixed_variables.append(np.where(need_zero_error_fix,np.full_like(error,['',''],dtype=str),error))
    return fixed_variables


class Submission():
    log = logging.getLogger("Submission")   
    
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
    
    def implement_table_config(self):
        # TODO check not to do the config multiple times
        for table_info in [objdict(x) for x in self._config['tables']]:
            # TODO verify table_info here?
            table_name=table_info.table_name
            #print(table_name)
            if( not table_info.should_be_processed):
                log.warning("table {table_info.table_name} has should_be_processed flag set to False. Skipping.")
                continue
            table=Table(table_name)
            if( hasattr(table_info, 'table_images')):
                table.table_images=table_info.table_images
            if( hasattr(table_info, 'table_title')):
                table.table_title=table_info.table_title
            if( hasattr(table_info, 'table_location')):
                table.table_location=table_info.table_location
            if( hasattr(table_info, 'table_keywords')):
                table.table_keywords=table_info.table_keywords
            for variable_info in table_info.variables:
                #print(f"Adding variable: {variable_info.variable_name}")
                ## TODO check that var_name does not contain any special characters (special characters allowe only in fancy names)
                var_name=variable_info.variable_name
                transformations=variable_info.transformation
                var_values=None
                for in_file in variable_info.in_files:
                    tmp_values=read_data_file(in_file.name,in_file.decode)
                    if(var_values):
                        var_values=np.concatenate((var_values,tmp_values))
                    else:
                        var_values=tmp_values
                if(transformations):
                    for transformation in transformations:
                        var_values=eval(transformation,self.__dict__|{"np":np},table.__dict__|{var_name:var_values})
                if( hasattr(variable_info, 'astype')):
                    if(variable_info.astype!=''):
                        var_values=var_values.astype(variable_info.astype)
                
                var=Variable(var_values,var_name)
                if( hasattr(variable_info, 'is_visible')):
                        var.is_visible=variable_info.is_visible
                if( hasattr(variable_info, 'is_independent')):
                        var.is_independent=variable_info.is_independent
                if( hasattr(variable_info, 'is_binned')):
                        var.is_binned=variable_info.is_binned
                if( hasattr(variable_info, 'unit')):
                        var.unit=variable_info.unit
                if( hasattr(variable_info, 'errors')):
                    if(variable_info.errors):
                        for error_info in variable_info.errors:
                            err_name=error_info.name
                            err_is_visible=error_info.is_visible
                            err_values=None
                            for in_file in error_info.in_files:
                                tmp_values=tmp_values_up=tmp_values_down=np.empty(0)
                                # if decode is present we have either 2-dim specification of [up,down] or 1-dim symmetric error
                                if( hasattr(in_file, 'decode')):
                                    tmp_values=read_data_file(in_file.name,in_file.decode)

                                # if decode_up is present we have either 2-dim specification of [decode_up,decode_down] or [decode_up,None]
                                if( hasattr(in_file, 'decode_up')):
                                    tmp_values_up=read_data_file(in_file.name,in_file.decode_up)

                                # if decode_down is present we have either 2-dim specification of [decode_up,decode_down] or [None,decode_down]
                                if( hasattr(in_file, 'decode_down')):
                                    tmp_values_up=read_data_file(in_file.name,in_file.decode_down)

                                if(tmp_values_up.size>0 or tmp_values_down.size>0):
                                    if(not tmp_values_down.size>0):
                                        tmp_values_down=np.full_like(tmp_values_up,np.nan)
                                    if(not tmp_values_up.size>0):
                                        tmp_values_up=np.full_like(tmp_values_down,np.nan)
                                    tmp_values=np.array([tmp_values_up,tmp_values_down]).T

                                if(not (tmp_values_up.size>0 or tmp_values_down.size>0 or tmp_values.size>0)):
                                    raise TypeError("Something went wrong. Could not read errors")
                                if(len(tmp_values.shape)==1):
                                        tmp_values=np.array([tmp_values,-1*tmp_values]).T
                                if(len(tmp_values.shape)>2):
                                        raise ValueError(f"Shape of error {err_name} for variable {var_name} is incorrect (needs to be 1 or 2-dimentional). Is {tmp.values.shape}.")
                                if(err_values):
                                    err_values=np.concatenate((err_values,tmp_values))
                                else:
                                    err_values=tmp_values
                            if( hasattr(error_info, 'transformations')):
                                for transformation in error_info.transformations:
                                    err_values=eval(transformation,self.__dict__|{"np":np},table.__dict__|{var_name:var_values,err_name:err_values}|{var_err.name:var_err for var_err in var.uncertainties})
                            if( hasattr(error_info, 'astype')):
                                if(error_info.astype!='' and error_info.astype):
                                    err_values=err_values.astype(error_info.astype)
                            unc=Uncertainty(err_values,name=err_name,is_visible=err_is_visible)
                            var.add_uncertainty(unc)
                table.add_variable(var)
                if hasattr(variable_info, 'regions'):
                    var.regions=get_cut_defined_variables(variable_info.regions,table.__dict__|{"np":np},local_dict=None)
                if hasattr(variable_info, 'grids'):
                    var.grids=get_cut_defined_variables(variable_info.grids,table.__dict__|{"np":np},local_dict=None)
                if hasattr(variable_info, 'signal_names'):
                    var.signal_names=get_cut_defined_variables(variable_info.signal_names,table.__dict__|{"np":np},local_dict=None)
                #print(f"added variable {var_name} to table {table.name}")
                
            self.tables.append(table)
            #TODO give warning when name already in the dictionary
            self.__dict__[table_name]=table
    def create_hepdata_record(self):
        # Actual record creation based on information stored
        hepdata_submission = hepdata_lib.Submission()
        # TO DO additional resources
        for table in self.tables:
            hepdata_table = hepdata_lib.Table(table.name)
            hepdata_table.description = table.table_title
            hepdata_table.location = table.table_location
            hepdata_table.keywords = table.table_keywords
            for image_info in table.table_images:
                hepdata_table.add_image(image_info['name'])
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
                            unc_is_symmetric=True
                            hepdata_unc = hepdata_lib.Uncertainty(unc.name, is_symmetric=unc_is_symmetric)
                            if(unc_is_symmetric):
                                #print(fixed_zero_variable[index][:,0])
                                hepdata_unc.values=fixed_zero_variable[index][:,0].tolist()
                            else:
                                hepdata_unc.values=fixed_zero_variable[index].tolist()
                            hepdata_variable.add_uncertainty(hepdata_unc)
                    hepdata_table.add_variable(hepdata_variable)
            hepdata_submission.add_table(hepdata_table)
        hepdata_submission.create_files("test_submission")
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


if __name__ == "__main__":
    main()
