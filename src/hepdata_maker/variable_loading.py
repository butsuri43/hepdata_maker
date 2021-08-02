
from .logs import logging
log = logging.getLogger(__name__)
from .console import console
from . import useful_functions as ufs
import jq
import uproot
from hepdata_lib import RootFileReader
import csv
import pytest
import yaml
import copy
import numpy as np
import json
from TexSoup import TexSoup
import regex as re
import scipy.stats, scipy.special
from collections import OrderedDict

def get_array_from_csv(file_path,decode,delimiter=','):
    log.debug("--------- csv file read -------------")
    log.debug(f"Reading variable information from csv file {file_path}")
    log.debug(f"decode used: '{decode}'")
    log.debug(f"delimiter used: '{delimiter}'")
    with open(file_path) as csv_file:    
        csv_reader = csv.DictReader(csv_file,delimiter=delimiter)
        line_count = 0
        data=[]
        if(not decode):
            messages=[f"""You need to specify variable 'decode' which contains the column name you want from your csv file."""]
            messages.append(f"Available field names: {csv_reader.fieldnames}")
            raise TypeError("\n".join(messages))
        if(decode not in csv_reader.fieldnames):
            messages=[f"""Key {decode} not found in the csv table. Check the csv file and 'decode' variable."""]
            messages.append(f"Available field names: {csv_reader.fieldnames}")
            raise TypeError("\n".join(messages))
            
        for row in csv_reader:
            if line_count == 0:
                line_count += 1
            else:
                data.append(row[decode])
                line_count += 1
        return np.array(data)

def get_array_from_json(file_path,decode):
    log.debug("--------- json file read -------------")
    log.debug(f"Reading variable information from json file {file_path}")
    log.debug(f"decode used: '{decode}'")
    try:
        with open(file_path, 'r') as stream:
            data_loaded = json.load(stream,object_pairs_hook=OrderedDict)
    except json.JSONDecodeError as err:
        log.error(f"Error in reading json inside {file_path}. See error thrown for details.")
        raise err
    except Exception as err:
        log.error(f"Error in reading file {file_path}.")
        raise err
    
    if(not decode):
        raise TypeError("""You need to specify variable 'decode' which defines a jq filter (https://stedolan.github.io/jq/manual/) parsed by (https://pypi.org/project/jq/).
        The easiest way to start is to use jq command line interface ( need to be installed separately from hepdata_submission_maker). One can run for example:\n 
        jq \".[].xsec_exp_errHigh_pb\" submission_maker/examples/stop0L/rawFiles/hepdata_upperLimits/1D_LQ3upperlimit.json\n
        After a desired filter is found it can be copied to hepdata_submission_maker.""")

    # json (steering file) requires strings to be in double-quotes ("). So does jq. For higher readability and easiness of use users can define things like
    #			{
    #			    "name":"examples/stop0L/rawFiles/hepdata_ACCEFF/AccEff.json",
    #                       "decode":".['SRATT']|keys_unsorted[] | split('_')[1]"
    #                   }
    # in a steering file. The single quotes in decode there are replaced with double quotes. 
    return np.array(jq.all(decode.replace("'",'"'),data_loaded))

def get_array_from_yaml(file_path,decode):
    log.debug("--------- yaml file read -------------")
    log.debug(f"Reading variable information from yaml file {file_path}")
    log.debug(f"decode used: '{decode}'")
    try:
        with open(file_path, 'r') as stream:
            data_loaded = yaml.safe_load(stream)
    except Exception as err:
        log.debug(f"Error in reading file {file_path}.")
        raise err

    if(not decode):
        raise TypeError("""You need to specify variable 'decode' which defines a jq filter (https://stedolan.github.io/jq/manual/) to parse your input file.
        Internally python implementation of jq is used (https://pypi.org/project/jq/).\n
        The easiest way to start is to use yq(!, jq wrapper for yaml) command line interface ( need to be installed separately from hepdata_submission_maker). One can run for example:\n 
        yq ".[].\"Weighted yield\"" ../submission_maker/examples/stop0L/rawFiles/hepdata_cutflows/cutflow_SRATT.yaml\n
        After a desired filter is found it can be copied to hepdata_submission_maker.""")

    # json (steering file) requires strings to be in double-quotes ("). So does jq. For higher readability and easiness of use users can define things like
    #			{
    #			    "name":"examples/stop0L/rawFiles/hepdata_cutflows/cutflow_SRATT.yaml",
    #			    "decode":".[]['Cut']"
    #			}
    # in a steering file. The single quotes in decode there are replaced with double quotes. 
    return np.array(jq.all(decode.replace("'",'"'),data_loaded))

def get_list_of_objects_in_root_file(file_path):
    result=[]
    try:
        rfile=uproot.open(file_path)
        return rfile.items()
    except ValueError as exc:
        exc.args=(f"file 'file_path'({file_path}) does not seem to be a readable root file!!\n"+"(orig exception): "+exc.args[0],)
        raise exc
    except Exception as exc:
        log.debug(f"file 'file_path'({file_path}) does not seem to be a readable root file!!")
        raise exc

def string_list_available_objects_in_root_file(file_path):
    result=[]
    av_items=get_list_of_objects_in_root_file(file_path)
    av_item_names_no_cycle=[name.split(';')[0] for name,_ in av_items]
    av_item_cycle_numbers={name:av_item_names_no_cycle.count(name) for name in av_item_names_no_cycle}
    result.append(f"Available objects inside root file '{file_path}':")
    for key,item in av_items:
        base_name=key.split(';')[0]
        cycle_number=key.split(';')[1]
        name_to_print=base_name if (av_item_cycle_numbers[base_name]==1  or av_item_cycle_numbers[base_name]==int(cycle_number)) else key
        result.append(f"-- '{name_to_print}' of type {item.classname if hasattr(item,'classname') else None}")
    return result

def get_array_from_root(object_path,decode):
    log.debug("--------- root file read -------------")
    log.debug(f"Reading variable information from root file {object_path}")
    log.debug(f"decode used: '{decode}'")

    obj_path_split=object_path.split(":")
    if(len(obj_path_split)!=2):
        # Wrong input
        log.debug(f"For root file 'in_file' input needs to be composed of two parts separated by ':'(colon). Parts available: {len(obj_path_split)}")
        ErrorMessages_wrong_path=[]
        ErrorMessages_wrong_path.append("'in_file' for root files need to be compised of two parts separated by ':'(colon), e.g. 'stopZh/rawFiles/CRTZ_njet30_SRL.root:CRTZ_njet30'. First is the relative or absolute path pointing to the root file, and second is the path inside root-file to the object you wish to read.")
        if(len(obj_path_split)>0):
            # We try to read root file and print objects contained in it to help user
            ErrorMessages_wrong_path=ErrorMessages_wrong_path+string_list_available_objects_in_root_file(obj_path_split[0])
        raise TypeError("\n".join(ErrorMessages_wrong_path))

    # At this point obj_path_split has the required lenght of 2
    file_path=obj_path_split[0]
    root_object_path=obj_path_split[1]
    
    # Main reader of root files (from hepdata_lib)
    rreader=RootFileReader(file_path)
    # but, need to get information about object type from uproot:
    object_to_be_loaded=uproot.open(file_path).get(root_object_path)
    loaded_object_hepdata_lib=None    
    if(not object_to_be_loaded):
        Error_messages=[f"Cannot find object '{root_object_path}' inside '{file_path}'. Check this file."]+string_list_available_objects_in_root_file(file_path)
        raise TypeError("\n".join(Error_messages))

    item_classname= object_to_be_loaded.classname if hasattr(object_to_be_loaded,'classname') else ''
    if( "TH1" in item_classname):
        loaded_object_hepdata_lib=rreader.read_hist_1d(root_object_path)
    elif( "TH2" in item_classname):
        loaded_object_hepdata_lib=rreader.read_hist_2d(root_object_path)
    elif("RooHist" in item_classname or "TGraph" in item_classname):
        loaded_object_hepdata_lib=rreader.read_graph(root_object_path)
    else:
        # TODO come up with way to work with general root objects (this is what is returned here).
        #loaded_object_hepdata_lib=rreader.retrieve_object(root_object_path)
        #return loaded_object_hepdata_lib[decode]
        log.warning(f"Unfortunately class '{item_classname}' of {root_object_path} inside root file {file_path} is unknown to hepdata_maker. Data cannot be read and is left blank!")
        return np.array([])

    if(not decode or decode not in loaded_object_hepdata_lib):
        Error_messages=[]
        Error_messages.append(f"'decode' key ({decode}) not found in the object '{root_object_path}' inside the root file '{file_path}'")
        Error_messages.append(f"Available key options: {list(loaded_object_hepdata_lib.keys())} corresponding to the following objects:")
        for key,item in  loaded_object_hepdata_lib.items():
            Error_messages.append(f"--> '{key}': {item}")
        raise TypeError("\n".join(Error_messages))

    return np.array(loaded_object_hepdata_lib[decode])
    
def get_array_from_tex(file_path,decode,tabular_loc_decode,replace_dict={}):
    log.debug("--------- tex file read -------------")
    log.debug(f"Reading variable information from tex file {file_path}")
    log.debug(f"decode used: '{decode}'")
    log.debug(f"tabular_loc_decode used: '{tabular_loc_decode}'")
    log.debug(f"replace_dict used: '{replace_dict}'")
    if(len(replace_dict)==0):
        log.debug("  You can specify 'replace_dict' to replace any regex appearing in tex file. Internally re.sub(key,value,text) is executed (see https://docs.python.org/3/library/re.html)")
    table= get_table_from_tex(file_path,tabular_loc_decode,replace_dict)

    if(not decode):
        raise TypeError(f"""You need to specify variable 'decode' which defines a transformation on a 2D numpy variable 'table' read from the specified tex-tabular table.
        One can use numpy(loaded as 'np'), re, scipy.ststs, scipy.special and functions inside useful_functions.py (loaded as 'ufs')

        For reference, 'table' (you should use in your 'decode') contains following information:
{table}""")
    try:
        result=eval(decode,{"np":np}|{'table':table}|{"re":re}|{"scipy.stats":scipy.stats}|{"scipy.special":scipy.special}|{"ufs":ufs})
    except Exception as exc:
        log.error(f"""Check your 'decode' settings!
Your 'table' looks the following:
{table}""")
        raise exc
    return result
def get_table_from_tex(file_path,tabular_loc_decode,replace_dict={}):
    try:
        soup = TexSoup(open(file_path))
    except Exception as exc:
        log.error(f"Issue reading file {file_path}.\nAre you sure it is a correctly formated tex file??")
        raise exc
    
    try:
        tabular_info=eval(tabular_loc_decode,{'latex':soup}).expr
    except Exception as exc:
        log.error("Issue with tabular decoding. Please check your 'tabular_loc_decode' variable!")
        raise exc
    tabular_info.string=re.sub('%.*','',tabular_info.string)
    for key,value in {**replace_dict, **{r'\hline':'',r'\n':'','\cline{.?}':''}}.items():
        tabular_info.string=re.sub(key.replace('\\','\\\\'),value,tabular_info.string)
    table=[[y.rstrip().strip() for y in x.split(r'&')] for x in tabular_info.string.replace(r'\hline','').replace('\n','').split(r'\\')]

    nrepeated_row_list=[{'n':0, 'item':''} for i in range(max([len(x) for x in table]))]
    new_table=[]
    for nrow in range(len(table)):
        row=[]
        ncol_offset=0
        for ncol in range(len(table[nrow])):
            matched_multicol=re.match("\\\\multicolumn\s?{\s?(\d+)\s?}\s?{.?}\s?{(.*)}",table[nrow][ncol])
            if(matched_multicol):
                n_repeat_col=int(matched_multicol.groups()[0])
                entry=matched_multicol.groups()[1]
            else:
                n_repeat_col=1
                entry=table[nrow][ncol]
            for col_repeat_index in range(n_repeat_col):
                if(col_repeat_index>0):
                    ncol_offset+=1
                matched_multirow=re.match("\\\\multirow\s?{\s?(\d+)\s?}\s?{.?}\s?{(.*)}",entry)
                if(matched_multirow):
                    nrepeated_row_list[ncol+ncol_offset]['n']=int(matched_multirow.groups()[0])
                    nrepeated_row_list[ncol+ncol_offset]['item']=matched_multirow.groups()[1]
                if(nrepeated_row_list[ncol+ncol_offset]['n']>0):
                    row.append(nrepeated_row_list[ncol+ncol_offset]['item'])
                    nrepeated_row_list[ncol+ncol_offset]['n']=nrepeated_row_list[ncol+ncol_offset]['n']-1
                else:
                    row.append(entry)
        new_table.append(row)
    new_table=np.array([x for x in new_table if (x!=[] and not all([(y=='' or y==None) for y in x]))],dtype=object)
    return new_table
    
def read_data_file(file_name,decode,**extra_args):
    tmp_values=None
    delimiter=extra_args.get('delimiter',',')
    replace_dict=extra_args.get('replace_dict',{})
    tabular_loc_decode=extra_args.get('tabular_loc_decode',None)
    file_type=extra_args.get('file_type',None)
    log.debug(f"reading data file: {file_name} with following options provided:\n file_type='{file_type}', delimiter='{delimiter}', tabular_loc_decode (for .tex file)='{tabular_loc_decode}', replace_dict(for .tex files)='{replace_dict}'.")

    if file_type: # file_type is specified. It takes precedence over type-guessing
        log.debug(f"You specified file_type={file_type} for the input file and this will be used.")
    else:
        log.debug(f"You have not specified the type of the input file. It will be guess from the name.")
        file_type=file_name.split(":")[0].lower().split(".")[-1]

    if True:
        # Just for visual appeal of the code
        if(file_type=='json'):
            tmp_values=get_array_from_json(file_name,decode)
        elif(file_type=='yaml'):
            tmp_values=get_array_from_yaml(file_name,decode)
        elif(file_type=='root'):
            tmp_values=get_array_from_root(file_name,decode)
        elif(file_type=='csv'):
            tmp_values=get_array_from_csv(file_name,decode,delimiter)
        elif(file_type=='tex'):
            if(tabular_loc_decode):
                tmp_values=get_array_from_tex(file_name,decode,tabular_loc_decode=tabular_loc_decode,replace_dict=replace_dict)
            else:
                raise TypeError(f"""File {file_name}: when reading tex file, variable 'tabular_loc_decode' must be set!
                This variable should point to the tabular environment that is desired to be read. It should use information of TexSoup (https://texsoup.alvinwan.com/) object 'latex' 
                created from your input file. In most cases something along this line is sufficient:
                
                "tabular_loc_decode":"latex.find_all(['tabular*','tabular'])[0]".""")
        else:
            raise TypeError(f"""File {file_name}: unsuported file type (file type: '{file_type}')!
            If the file_type cannot be guest from the filename extention, you can use flag/field 'file_type' to have it set manually.""")            

    return tmp_values


def get_variable_steering_snipped(in_file,decode,data_type,transformations,**extra_args):
    delimiter=extra_args.get('delimiter',',')
    replace_dict=extra_args.get('replace_dict',{})
    tabular_loc_decode=extra_args.get('tabular_loc_decode',None)
    file_type=extra_args.get('file_type',None)
    log.debug(f"Inside 'get_variable_steering_snipped': {in_file} with following options provided:\n file_type='{file_type}', delimiter='{delimiter}', tabular_loc_decode (for .tex file)='{tabular_loc_decode}', replace_dict(for .tex files)='{replace_dict}'.")
    result_json={}
    result_json['name']="VAR"
    
    additional_properties={}
    if('delimiter' in extra_args):
        additional_properties['delimiter']=extra_args['delimiter']
    if('replace_dict' in extra_args and len(replace_dict)>0):
        additional_properties['replace_dict']=extra_args['replace_dict']
    if('tabular_loc_decode' in extra_args and tabular_loc_decode):
        additional_properties['tabular_loc_decode']=extra_args['tabular_loc_decode']
    if('file_type' in extra_args and file_type):
        additional_properties['file_type']=extra_args['file_type']
    result_json['in_files']=[{"name":in_file, "decode":decode}|additional_properties]
    
    if(data_type):
        result_json['data_type']=data_type
    if(transformations):
        result_json['transformations']=list(transformations)
    return result_json
