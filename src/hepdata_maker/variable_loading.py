from .logs import logging
log = logging.getLogger(__name__)
from . import useful_functions as ufs
from .utils import merge_dictionaries
import jq     # type: ignore
import uproot # type: ignore
from hepdata_lib import RootFileReader # type: ignore
import csv
import yaml   # type: ignore
import json
from TexSoup import TexSoup # type: ignore
import numpy as np
import regex as re # type: ignore
import scipy.stats,scipy.special # type: ignore
from collections import OrderedDict
from collections.abc import Iterable
from typing import Union,Dict,List,Any,Literal,Callable,TextIO
import os
import functools
import io

def check_if_file_exists_and_readable(file_path:str)->bool:
    """
    Verify that FILE_PATH is readable file.
    Following data formats are allowed:

      - json
      - yaml
      - root
      - csv
      - tex
      - txt --> used as table title!
    """
    # TODO: Adding file_type argument for ambiguous cases
    if(not os.path.exists(file_path)):
        return False
    file_type=file_path.split(".")[-1].lower()
    with open(file_path, 'r') as stream:
        if(file_type=='json'):
            try:
                json.load(stream,object_pairs_hook=OrderedDict)
            except ValueError as e:
                return False
        elif(file_type=='yaml'):
            try:
                yaml.safe_load(stream)
            except ValueError as e:
                return False
        elif(file_type=="csv"):
            try:
                csv.DictReader(stream)
            except ValueError as e:
                return False
        elif(file_type=='root'):
            try:
                uproot.open(file_path) # yes, it is file_path here
            except ValueError as exc:
                return False
        elif(file_type=='txt'):
            return True # formatting of text file is not checked
        elif(file_type=='tex'):
            try:
                TexSoup(stream)
            except ValueError as exc:
                return False
        else:
            # this type is not supported
            return False

        # If we get that far we were able to read the file fine!
        return True

#
##
## For data loading in particular we need to have order of yaml input preserved
## Since Python 3.7 it is more or less given for dict, however not quaranteed
## Therefore we need a bit of extra code to be on the safe side for yaml-loading
## code below adopted from Answer #1 in https://www.py4u.net/discuss/12785
def yaml_ordered_safe_load(stream:TextIO,
                           object_pairs_hook:Callable=OrderedDict)->OrderedDict:
    """
    Load single yaml document safely with loading order ensured to be the same all the times.
    Adopted from Answer #1 in https://www.py4u.net/discuss/12785
    """
    class OrderedLoader(yaml.SafeLoader):
        pass
    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return object_pairs_hook(loader.construct_pairs(node))
    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping)
    return yaml.load(stream, OrderedLoader)

def yaml_ordered_safe_load_all(stream:TextIO,
                               object_pairs_hook:Callable=OrderedDict)->OrderedDict:
    """
    Load multiple yaml documents safely with loading order ensured to be the same all the times.
    Adopted from Answer #1 in https://www.py4u.net/discuss/12785
    """
    class OrderedLoader(yaml.SafeLoader):
        pass
    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return object_pairs_hook(loader.construct_pairs(node))
    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping)
    return yaml.load_all(stream, OrderedLoader)
##
#


@functools.lru_cache(maxsize=16) 
def open_data_file(file_path:Union[str,os.PathLike],
                   file_type:Literal['yaml', 'json', 'csv', 'root','tex']) -> Any:
    """
    Opens and caches input file data.
    Please mind that the output has different type
    depending on the file_type of the input file.
    """
    log.debug(f"Opening uncached file {file_path}, type={file_type}.")
    data_loaded:Any=None
    try:
        if(file_type=="yaml"):
            with open(file_path, 'r') as stream:
                data_loaded = yaml_ordered_safe_load(stream)
        elif(file_type=='json'):
            with open(file_path, 'r') as stream:
                data_loaded = json.load(stream,object_pairs_hook=OrderedDict)
        elif(file_type=='csv'):
            with open(file_path, 'r') as stream:
                data_loaded = stream.read()
        elif(file_type=='root'):
            data_loaded=RootFileReader(file_path)
        elif(file_type=='tex'):
            data_loaded = TexSoup(open(file_path))
        else:
            raise ValueError(f"Unrecognised argument filetype={file_type}")
        return data_loaded
    except Exception as err:
        log.debug(f"Error in reading file {file_path}.")
        raise err
        
        
def get_array_from_csv(file_path:Union[str,os.PathLike],
                       decode:str,
                       delimiter:str=',') -> np.ndarray:
    """
    Read specific column of a csv file given.

    Args:
      file_path: path to the csv file to read
      decod: name of the column to use
      delimiter: what delimiter is used in the csv file -- default ','
    """
    log.debug("--------- csv file read -------------")
    log.debug(f"Reading variable information from csv file {file_path}")
    log.debug(f"decode used: '{decode}'")
    log.debug(f"delimiter used: '{delimiter}'")

    with io.StringIO(open_data_file(file_path,"csv")) as csv_file: # type: ignore
        csv_reader = csv.DictReader(csv_file,delimiter=delimiter)
        data=[]
        if(not decode):
            messages=[f"""You need to specify variable 'decode' which contains the column name you want from your csv file."""]
            messages.append(f"Available field names: {csv_reader.fieldnames}")
            raise TypeError("\n".join(messages))
        if(csv_reader.fieldnames is None or decode not in csv_reader.fieldnames):
            messages=[f"""Key {decode} not found in the csv table. Check the csv file and 'decode' variable."""]
            messages.append(f"Available field names: {csv_reader.fieldnames}")
            raise TypeError("\n".join(messages))
            
        for row in csv_reader:
            data.append(row[decode])
        return np.array(data)

def decode_json_array(json_array:Union[Dict[str,Any],List[Any]],decode:str)->np.ndarray:
    """
    Read information from json object using jq decoding.

    Args:
      json_array: json object (dict, or list),
      decod: jq command used for decoding.
    """
    log.debug(f"inside decode_json_array")
    if(not decode):
        raise TypeError("""You need to specify variable 'decode' which defines a jq filter (https://stedolan.github.io/jq/manual/) parsed by (https://pypi.org/project/jq/).
        The easiest way to start is to use jq command line interface ( need to be installed separately from hepdata_submission_maker). One can run for example:\n 
        jq \".[].xsec_exp_errHigh_pb\" submission_maker/examples/stop0L/rawFiles/hepdata_upperLimits/1D_LQ3upperlimit.json\n
        After a desired filter is found it can be copied to hepdata_submission_maker.""")

    # steering file being json requires strings to be in double-quotes ("). So does jq. For higher readability and easiness of use users can define things like
    #			{
    #			    "name":"examples/stop0L/rawFiles/hepdata_ACCEFF/AccEff.json",
    #                       "decode":".['SRATT']|keys_unsorted[] | split('_')[1]"
    #                   }
    # in steering files. The single quotes in decode are replaced with double quotes below. 
    jq_output=jq.all(decode.replace("'",'"'),json_array)

    ## pythonic jq does not have always same behaviour as bash-jq.
    ## One problem is that if jq command returns a (single-) table,
    ##   jq.all we use will give us [table] (so table of tables), e.g `jq 'keys' {"1":1,"2":2}` in bash returns 1,2,
    ##   while in jq.all [[1,2]]. In pythonic jq we need 'keys | .[]'==> [1,2].
    ## There is no much we can do about it (see also https://github.com/mwilliamson/jq.py/issues/67). We can only flag potential issues
    ##   and provide user with this information (they might want to use if they see errors along)
    if(len(jq_output)>0):
        jq_first=jq_output[0]
        if([jq_first]==jq_output and isinstance(jq_first,Iterable)):
            log.warning(f"It seems that you have a single-valued array of array: '{jq_output}'. If this was intended, ignore the warning. If an error was raised, you might want to add '| .[]' to your decode variable.")

    return np.array(jq_output)
    
def get_array_from_json(file_path:Union[str,os.PathLike],
                        decode:str) -> np.ndarray:
    """
    Read information from json file using jq decoding

    Args:
      file_path: path to the json file to read
      decod: jq command used for decoding
    """
    log.debug("--------- json file read -------------")
    log.debug(f"Reading variable information from json file {file_path}")
    log.debug(f"decode used: '{decode}'")

    data_loaded=open_data_file(file_path,"json")# type: ignore
    
    return decode_json_array(data_loaded,decode)

def get_array_from_yaml(file_path:Union[str,os.PathLike],
                        decode:str) -> np.ndarray:
    """
    Read information from yaml file using jq decoding

    Args:
      file_path: path to the yaml file to read
      decod: jq command used for decoding
    """
    log.debug("--------- yaml file read -------------")
    log.debug(f"Reading variable information from yaml file {file_path}")
    log.debug(f"decode used: '{decode}'")
    data_loaded=open_data_file(file_path,"yaml")# type: ignore 
            
    return decode_json_array(data_loaded,decode)

@functools.lru_cache(maxsize=16)
def get_list_of_objects_in_root_file(file_path:Union[str,os.PathLike]) -> Dict[str,str]:
    """
    Get names and class names of objects inside ROOT fie

    Args:
      file_path: path to the json file to read.

    Returns:
      Returns result from uproot's classnames().
    """
    log.debug(f"getting list of objects inside ROOT file {file_path}.")
    try:
        rfile=uproot.open(file_path)
        return rfile.classnames()
    except Exception as exc:
        log.debug(f"file 'file_path'({file_path}) does not seem to be a readable root file!!")
        raise exc

def string_list_available_objects_in_root_file(file_path:Union[str,os.PathLike]) -> List[str]:
    """
    Get beautified list of objects and class names inside a ROOT file.
    Results are in a ready to print list with
    cycle number removed if only one present.
    """
    result:List[str]=[]
    av_items=get_list_of_objects_in_root_file(file_path) # type: ignore 
    av_item_names_no_cycle=[name.split(';')[0] for name in av_items]
    av_item_cycle_numbers={name:av_item_names_no_cycle.count(name) for name in av_item_names_no_cycle}
    result.append(f"Available objects inside root file '{file_path}':")
    for key,classname in av_items.items():
        base_name=key.split(';')[0]
        cycle_number=key.split(';')[1]
        name_to_print=base_name if (av_item_cycle_numbers[base_name]==1  or av_item_cycle_numbers[base_name]==int(cycle_number)) else key
        result.append(f"-- '{name_to_print}' of type {classname}")
    return result

@functools.lru_cache(maxsize=128)
def get_object_class(file_path:Union[str,os.PathLike],
                     root_object_path:str)-> str:
    """
    Get class name of the object in the ROOT file

    Args:
      file_path: path to the ROOT file
      root_object_path: name of the object
    """
    object_to_be_loaded=uproot.open(file_path).get(root_object_path)
    if(not object_to_be_loaded):
        Error_messages=[f"Cannot find object '{root_object_path}' inside '{file_path}'. Check this file."]+string_list_available_objects_in_root_file(file_path)
        raise TypeError("\n".join(Error_messages))

    return object_to_be_loaded.classname if hasattr(object_to_be_loaded,'classname') else ''

def get_array_from_root(object_path:str,
                        decode:str)->np.ndarray:
    """
    Obtain a data array from an object inside ROOT file
    using hepdata_lib.RootFileReader

    Args:
      object_path: path to the ROOT file & path to the object to read (separated by ':'), e.g.:
        ``object_path="my_root_file.root:histogram_I_want_to_read"``

      decode: name of the data to be read from the file, this could be:

        - for TH1F: ``x`` (bin_centers), ``x_edges`` ((low,high) bin values), ``y`` (values), ``dy`` (value errors)
        - TH2F: ``x``/``y`` (bin_centers), ``x_edges``/``y_edges`` ((low,high) bin values), ``z`` (values), ``dy`` (value errors)
        - TGraph: ``x`` (x-values), ``y`` (y-values)
        - RooHist: same as TGraph
        - TGraphErrors/TGraphAssymetricErrors: ``x``/``y`` (x/y-values), ``dx``/``dy`` (errors on x/y-values when appropriate)

        See https://github.com/HEPData/hepdata_lib/blob/master/examples/reading_histograms.ipynb for more details.
    """
    log.debug("--------- root file read -------------")
    log.debug(f"Reading variable information from root file {object_path}")
    log.debug(f"decode used: '{decode}'")

    obj_path_split=object_path.split(":")
    if(len(obj_path_split)!=2):
        # Wrong input
        ErrorMessages_wrong_path=[]
        ErrorMessages_wrong_path.append("'in_file' for root files need to be compised of two parts separated by ':'(colon), e.g. 'stopZh/rawFiles/CRTZ_njet30_SRL.root:CRTZ_njet30'. First is the relative or absolute path pointing to the root file, and second is the path inside root-file to the object you wish to read.")
        if(len(obj_path_split)>0):
            # We try to read root file and print objects contained in it to help user
            try:
                ErrorMessages_wrong_path=ErrorMessages_wrong_path+string_list_available_objects_in_root_file(obj_path_split[0])
            except Exception as ex:
                ErrorMessages_wrong_path.append(f"In addition, the file provided ({obj_path_split[0]}) does not seem to be a ROOT file")
        raise TypeError("\n".join(ErrorMessages_wrong_path))

    # At this point obj_path_split has the required lenght of 2
    file_path=obj_path_split[0]
    root_object_path=obj_path_split[1]
    
    # Main reader of root files (from hepdata_lib)
    rreader=open_data_file(file_path,"root") # type: ignore 

    # but, need to get information about object type from uproot:
    item_classname=get_object_class(file_path,root_object_path)

    loaded_object_hepdata_lib=None    
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


# Just information for users that is used in two places
tabular_loc_decode_clarification=""" This variable should point to the tabular environment that is desired to be read. It should use information of TexSoup (https://texsoup.alvinwan.com/) object 'latex' 
 created from your input file. In most cases something along this line is sufficient:

 tabular_loc_decode":"latex.find_all(['tabular*','tabular'])[0]"
"""    

def get_array_from_tex(file_path:Union[str,os.PathLike],
                       decode:str,
                       tabular_loc_decode:str,
                       replace_dict:Dict[str,str]={})->np.ndarray:
    """
    Obtain a data array from a tabular envirnoment inside a .tex file
    using using TexSoup
    Multicolumn and multirow comamnds are accepted.

    Args:
      file_path: path to the tex file to be read

      decode: a transformation on a 2D numpy variable 'table' that
        is made from the specified tex-tabular table.
        One can use numpy (loaded as ``np``), ``re``, ``scipy.stats``, ``scipy.special``
        and functions inside useful_functions.py (loaded as ``ufs``)

      tabular_loc_decode: This variable should point to the tabular environment one desires to read.
        It should use function of TexSoup (https://texsoup.alvinwan.com/)
        object made from readting the 'file_path' file.
        The object can be access by name 'latex'.

        In most cases something along this line is sufficient:
          ``"tabular_loc_decode":"latex.find_all(['tabular*','tabular'])[0]"``.

      replace_dict: a string with json-style dictionary used for replacing symbols inside the table.
        Internally re.sub(key,value,text) is executed on all key, value pairs
        (see also https://docs.python.org/3/library/re.html).
    """
    log.debug("--------- tex file read -------------")
    log.debug(f"Reading variable information from tex file {file_path}")
    log.debug(f"decode used: '{decode}'")
    log.debug(f"tabular_loc_decode used: '{tabular_loc_decode}'")
    log.debug(f"replace_dict used: '{replace_dict}'")
    if(not tabular_loc_decode):
        raise TypeError(f"File {file_path}: when reading tex file, variable 'tabular_loc_decode' must be set!\n{tabular_loc_decode_clarification}")
    if(len(replace_dict)==0):
        log.debug("  You can specify 'replace_dict' to replace any regex appearing in tex file. Internally re.sub(key,value,text) is executed (see https://docs.python.org/3/library/re.html)")

    table= get_table_from_tex(file_path,tabular_loc_decode,replace_dict)

    #
    ## Trying to get a data column from the table
    # First we define message for user if we fail. 
    decode_clarification=f"""It defines a transformation on a 2D numpy variable 'table' that is made from the specified tex-tabular table.
    One can use numpy (loaded as 'np'), re, scipy.ststs, scipy.special and functions inside useful_functions.py (loaded as 'ufs')

    For reference, 'table' (you should use in your 'decode') contains following information:
    {table}
    """
    if(not decode):
        raise TypeError(f"""You need to specify variable 'decode'. {decode_clarification}""")
    try:
        result=eval(decode,merge_dictionaries({"np":np},{'table':table},{"re":re},{"scipy.stats":scipy.stats},{"scipy.special":scipy.special},{"ufs":ufs}))
    except Exception as exc:
        log.error(f"""Check your 'decode' settings!
        {decode_clarification}""")
        raise exc
    ##
    #
    
    return result

def get_table_from_tex(file_path:Union[str,os.PathLike],
                       tabular_loc_decode:str,
                       replace_dict:Dict[str,str]={})->np.ndarray:
    r"""
    Obtain 2-D numpy.ndarray representing information stored
    in a tabular envirnoment inside a .tex file.
    Multirow and multicolumn commands are accepted

    Args:
      file_path: path to the tex file to be read

      tabular_loc_decode: This variable should point to the tabular environment one desires to read.
        It should use function of TexSoup (https://texsoup.alvinwan.com/)
        object made from readting the 'file_path' file.
        The object can be access by name 'latex'.

        In most cases something along this line is sufficient:
          ``"tabular_loc_decode":"latex.find_all(['tabular*','tabular'])[0]"``.

      replace_dict: a string with json-style dictionary used for replacing symbols inside the table.
        Internally re.sub(key,value,text) is executed on all key, value pairs.

        Example:
          Replacing custom tags, e.g. '\\GeV' with 'GeV':
            ``"{'\\\\GeV':'GeV'}"`` (mind the 4-backslashes)

          See https://docs.python.org/3/library/re.html
          for regex patterns allowed and
          https://docs.python.org/3/howto/regex.html#the-backslash-plague
          for the need of multiple backslashes.
    """

    # First load .tex file
    soup=open_data_file(file_path,"tex")# type: ignore 

    # try to evaluate 'tabular_loc_decode'
    try:
        tabular_info=eval(tabular_loc_decode,{'latex':soup}).expr
    except Exception as exc:
        log.error(f"File {file_path}: Issue with tabular decoding. Please check your 'tabular_loc_decode' variable!\n{tabular_loc_decode_clarification}")
        raise exc

    # Clean the table from comments / separators and user-chosen artifacts
    tabular_info.string=re.sub('%.*','',tabular_info.string)
    for key,value in {**replace_dict, **{r'\\hline':'',r'\\n':'',r'\\cline{.?}':''}}.items():
        tabular_info.string=re.sub(key,value,tabular_info.string)

    # now, data should be easily separable by '&' (columns) and '\\' (rows)
    table=[[y.rstrip().strip() for y in x.split(r'&')] for x in tabular_info.string.split(r'\\')]

    #
    ## Below we decode information from multirow and multicolumn commands 
    nrepeated_row_list:List[Dict[str,Any]]=[{'n':0, 'item':''} for i in range(max([len(x) for x in table]))]
    new_table:List[List[Any]]=[]
    for nrow in range(len(table)):
        row:List[Any]=[]
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
    ##
    #
    
    # Final sanitisation by removing empty raw/columns:
    return_table=np.array([x for x in new_table if (x!=[] and not all([(y=='' or y==None) for y in x]))],dtype=object)
    return return_table
    
def read_data_file(file_path:str,
                   decode:str,
                   **extra_args:Any)->np.ndarray:
    """
    Get a column of data (1-D numpy array) from a file.

    Args:
      file_path: path to file to be read (types accepted:['json', 'yaml', 'root', 'csv', 'tex'])

      decode: string selecting information from the input file.
        Required syntax depends on the type of the file read.
        See specific 'get_array_from_[file_type]' functions for details:


          - :py:func:`hepdata_maker.variable_loading.get_array_from_root`
          - :py:func:`hepdata_maker.variable_loading.get_array_from_json`
          - :py:func:`hepdata_maker.variable_loading.get_array_from_yaml`
          - :py:func:`hepdata_maker.variable_loading.get_array_from_csv`
          - :py:func:`hepdata_maker.variable_loading.get_array_from_tex`


      extra_args: extra arguments, which are:

        - file_type: string specifying type of the file to be load.
          Required only if file type cannot be guessed from file extention.

        - delimiter: 'optional' for csv file; specifies delimiter if  csv file read
          (see https://docs.python.org/3/library/csv.html)

        - tabular_loc_decode: 'required' if tex file is read (see 'get_array_from_tex' for more details)

        - replace_dict:  'optional' if tex file is read (see 'get_array_from_tex' for more details)
    """
    tmp_values=None
    if(not os.path.isfile(file_path.split(":")[0])): # split is for ROOT files
        raise ValueError(f"Could not find data file '{file_path}'. Please check the path provided.")

    delimiter=extra_args.get('delimiter',',')
    replace_dict=extra_args.get('replace_dict',{})
    tabular_loc_decode=extra_args.get('tabular_loc_decode',None)
    file_type=extra_args.get('file_type',None)
    log.debug(f"reading data file: {file_path} with following options provided:\n file_type='{file_type}', delimiter='{delimiter}', tabular_loc_decode (for .tex file)='{tabular_loc_decode}', replace_dict(for .tex files)='{replace_dict}'.")

    if file_type: # file_type is specified. It takes precedence over type-guessing
        log.debug(f"You specified file_type={file_type} for the input file and this will be used.")
    else:
        log.debug(f"You have not specified the type of the input file. It will be guess from the name.")
        file_type=file_path.split(":")[0].lower().split(".")[-1]

    if True:
        # Just for visual appeal of the code
        if(file_type=='json'):
            tmp_values=get_array_from_json(file_path,decode)
        elif(file_type=='yaml'):
            tmp_values=get_array_from_yaml(file_path,decode)
        elif(file_type=='root'):
            tmp_values=get_array_from_root(file_path,decode)
        elif(file_type=='csv'):
            tmp_values=get_array_from_csv(file_path,decode,delimiter)
        elif(file_type=='tex'):
            tmp_values=get_array_from_tex(file_path,decode,tabular_loc_decode=tabular_loc_decode,replace_dict=replace_dict)
        else:
            raise TypeError(f"""File {file_path}: unsuported file type (file type: '{file_type}')!
            If the file_type cannot be guest from the filename extention, you can use flag/field 'file_type' to have it set manually.""")            

    return tmp_values


def get_variable_steering_snipped(in_file:Union[str,os.PathLike],
                                  decode:str,
                                  data_type:str,
                                  transformations:List[str],
                                  **extra_args:Any)-> Dict[str,Any]:
    """
    Get a snipped of steering file for variable using provided information
    This is used to provide user with an easy to use and 'minimal' insertion.
    """
    delimiter=extra_args.get('delimiter',None)
    replace_dict=extra_args.get('replace_dict',{})
    tabular_loc_decode=extra_args.get('tabular_loc_decode',None)
    file_type=extra_args.get('file_type',None)
    log.debug(f"Inside 'get_variable_steering_snipped': {in_file} with following options provided:\n file_type='{file_type}', delimiter='{delimiter}', tabular_loc_decode (for .tex file)='{tabular_loc_decode}', replace_dict(for .tex files)='{replace_dict}'.")
    result_json:Dict[str,Any]={}
    result_json['name']="VAR"
    
    additional_properties={}
    if('delimiter' in extra_args and ((file_type and file_type=='csv') or os.path.splitext(in_file)[1]=='csv')):
        additional_properties['delimiter']=extra_args['delimiter']
    if('replace_dict' in extra_args and len(replace_dict)>0):
        additional_properties['replace_dict']=extra_args['replace_dict']
    if('tabular_loc_decode' in extra_args and tabular_loc_decode):
        additional_properties['tabular_loc_decode']=extra_args['tabular_loc_decode']
    if('file_type' in extra_args and file_type):
        additional_properties['file_type']=extra_args['file_type']
    if(in_file):
        result_json['in_files']=[merge_dictionaries({"name":in_file, "decode":decode},additional_properties)]
    
    if(data_type):
        print(f"passed {data_type}")
        result_json['data_type']=data_type
    if(transformations):
        result_json['transformations']=list(transformations)
    return result_json
