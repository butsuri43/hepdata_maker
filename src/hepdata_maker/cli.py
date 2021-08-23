import click
from .Submission import Submission
from .Submission import print_dict_highlighting_objects
from .Submission import perform_transformation
from . import utils
from .logs import logging
from .console import console
from . import variable_loading
from collections.abc import Iterable
import numpy as np
import rich.columns 
import rich.table 
import rich.panel
import collections
import re
import scipy.stats, scipy.special
from . import useful_functions as ufs
import json
import jsonref
@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('--log-level',
              type=click.Choice(list(logging._levelToName.values()), case_sensitive=False),default="INFO",help="set log level.")
def hepdata_maker(log_level):
    """HEPData submission maker"""
    from .logs import set_default_logger
    set_default_logger(log_level)
    log = logging.getLogger(__name__)
    log.debug(f"Log-level is {log_level}")
    #if(log_level!="DEBUG" or log_level):
    #    click.echo(f" --- Log-level is {log_level} ---")

# Logging object can only be created after debug level is set above
log = logging.getLogger(__name__)

@hepdata_maker.command()
@click.argument('steering_file',type=click.Path(exists=True))
@click.option('--data-root', default='./', help='Location of files specified in steering file (if not an absolute location is given there)',type=click.Path(exists=True),)
@click.option('--output-dir', default='submission_files', help='The name of the directory where the submission files will be created. Default: submission_files',type=click.Path(exists=False))
@click.option('--use-fancy-names', help="Force 'fancy-names' to be used for tables, and uncertainties (not recommended)", is_flag=True)
def create_submission(steering_file,data_root,output_dir,use_fancy_names):
    log.debug(f"Creating submission file based on {steering_file}. Data-root is {data_root} and the output directory {output_dir}. ")
    console.rule("create_submission",characters="=")
    console.print(f"Loading submission information based on {steering_file}")
    submission=Submission()
    submission.read_table_config(steering_file)
    submission.load_table_config(data_root)
    # TODO require user to confirm overwriting output_dir if it already exist
    with console.status("Creating hepdata files (this might take a while)..."):
        submission.create_hepdata_record(data_root,output_dir,use_fancy_names)
        
@hepdata_maker.command()
@click.argument('steering_file',type=click.Path(exists=True))
def check_schema(steering_file):
    console.rule("checking_schema",characters="=")
    console.print(f"Checking schema of {steering_file}.")
    with open(steering_file, 'r') as fstream:
        print("file://"+os.path.abspath(os.path.dirname(steering_file)),steering_file)
        json_data = jsonref.load(fstream,base_uri="file://"+os.path.abspath(os.path.dirname(steering_file))+"/")
    utils.check_schema(json_data,'steering_file.json')
    console.print(f"    All ok!    ")

def get_requested_table_list(steering_file,load_all_tables,indices,names):
    available_tables=utils.get_available_tables(steering_file)
    if(load_all_tables):
        return available_tables
    if(not (indices or names)):
        raise TypeError(f"You need to provide the name/index of the table you want to print. Choose from: (name,index)={[(tuple[0],index) for index,tuple in enumerate(available_tables)]}")
    if(indices and (max(indices)>len(available_tables) or min(indices)<0)):
        raise ValueError(f"You requested table with index {max(indices)} while only range between 0 and {len(available_tables)} is available!")
    requested_tables=[]
    for idx in indices:
        name=available_tables[idx][0]
        should_be_processed=available_tables[idx][1]
        if(not should_be_processed):
            raise ValueError(f"You requested table with index {idx} (name: {name}) however flag 'should_be_processed' is set to False.")
        requested_tables.append(name)
    available_table_names=[table[0] for table in available_tables]
    for name in names:
        if(name not in available_table_names):
            raise ValueError(f"You requested table with name {name} however this name is not found in the file {steering_file}. Available are {[table[0] for table in available_tables]}")
        for av_name,should_be_processed in available_tables:
            if(av_name==name and (not should_be_processed)):
                raise ValueError(f"You requested table with name: {name} however flag 'should_be_processed' is set to False.")
        requested_tables.append(name)
    return requested_tables

def submission_for_selected_tables(steering_file,data_root,load_all_tables,requested_tables):
    console.print(f"Loading requested tables based on {steering_file}")
    submission=Submission()
    submission.read_table_config(steering_file)
    if(load_all_tables):
        submission.load_table_config(data_root)
    else:
        submission.load_table_config(data_root,selected_table_names=requested_tables)

    return submission

@hepdata_maker.command()
@click.argument('steering_file',type=click.Path(exists=True))
@click.option('--data-root', default='./', help='Location of files specified in steering file (if not an absolute location is given there)',type=click.Path(exists=True),)
@click.option('--load-all-tables/--load-only-selected', '-a/-o', default=True)
@click.option('--indices', '-i', type=int,multiple=True)
@click.option('--names', '-n', type=str,multiple=True)
def check_table(steering_file,data_root,load_all_tables,indices,names):
    console.rule("check_table",characters="=")
    requested_tables=get_requested_table_list(steering_file,load_all_tables,indices,names)
    submission=submission_for_selected_tables(steering_file,data_root,load_all_tables,requested_tables)
    console.print(f"Printing requested tables:")
    for table in submission.tables:
        if(any(table.name==name for name in requested_tables)):
            console.rule(f"[bold]{table.name}")
            console.print("title:",rich.panel.Panel(table.title,expand=False))
            console.print("location:",rich.panel.Panel(table.location,expand=False))
            keyword_tables=[]
            for key,vals in table.keywords.items():
                tmp_key_table=rich.table.Table()
                tmp_key_table.add_column(key)
                for val in vals:
                    tmp_key_table.add_row(val)
                keyword_tables.append(tmp_key_table)
                columns = rich.columns.Columns(keyword_tables, equal=True, expand=False)
            console.print("keywords:",rich.panel.Panel(columns,expand=False))
            if(len(table.images)>0):
                tmp_rich_table=rich.table.Table()
                image_info_grid=tmp_rich_table.grid()
                for image_info in table.images:
                    image_table=rich.table.Table(show_header=False,box=rich.box.SQUARE)
                    image_table.add_row("name: "+image_info.name)
                    image_table.add_row("label: "+image_info.label)
                    image_info_grid.add_row(image_table)
                console.print("images:",rich.panel.Panel(image_info_grid,expand=False))
            rich_table=rich.table.Table()
            not_visible_variable_names=[]
            visible_variables=[]
            for var in table.variables:
                if(not var.is_visible):
                    # If variable is not visible
                    # (used as temporary one for example)
                    # it can have weird number of entries thus
                    # it is best to not print it
                    not_visible_variable_names.append(var.name)
                    continue
                style="black on white" if var.is_independent else ""
                var_name_with_units=var.name if (not var.units) else var.name+" ["+var.units+"]"
                rich_table.add_column(var_name_with_units,style=style)
                visible_variables.append(var)
            if(len(not_visible_variable_names)>0):
                console.print("not-visible variables:",not_visible_variable_names)
            variable_tables=[]
            for var in visible_variables:
                var_table=rich.table.Table()
                var_table.add_column()
                for unc in var.uncertainties:
                    if(unc.is_visible):
                        var_table.add_column(unc.name)
                for index in range(len(var)):
                    all_unc_grids=[]
                    for unc in var.uncertainties:
                        if(unc.is_visible):
                            if(len(unc[index].shape)==0):
                                # just a number
                                all_unc_grids.append("+/- "+str(unc[index]))
                            else:
                                all_unc_grids.append(str(unc[index]))
                    var_table.add_row(str(var[index]),*all_unc_grids)
                variable_tables.append(var_table)
                rich_table.add_row(*variable_tables)
            console.print("visible values:",rich_table)

@hepdata_maker.command()
@click.option('--in-file','-f',type=click.Path(exists=False))
@click.option('--data-root', default='./', help='Location of in_file and files specified in steering file (if not an absolute location is given for those)',type=click.Path(exists=True))
@click.option('--file-type',type=click.Choice(['json', 'yaml','csv','root','tex'], case_sensitive=False))
@click.option('--decode','-d',type=str)
@click.option('--data-type','-t',type=str)
@click.option('--tabular-loc-decode',type=str)
@click.option('--delimiter',type=str,default=',')
@click.option('--replace_dict',type=str,default='{}')
@click.option('--transformation','-x','transformations',type=str,multiple=True)
@click.option('--steering-file','-s',type=click.Path(exists=True))
@click.option('--load-all-tables/--load-only-selected', '-a/-o', default=True)
@click.option('--indices', '-i', type=int,multiple=True)
@click.option('--names', '-n', type=str,multiple=True)
def check_variable(in_file,data_root,file_type,decode,data_type,tabular_loc_decode,delimiter,replace_dict,transformations,steering_file,load_all_tables,indices,names):
    console.rule("check_variable",characters="=")
    console.print("This option checks whether you provide correct information for loading a variable and helps you debug.")
    console.rule("in_file")
    console.print("Provide information on the location of the file (.json/.yaml/.root/.csv or .tex files) with variable information")
    console.print(f"You provided [bold]in_file[/bold]: {in_file}")
    replace_dict=json.loads(replace_dict)
    extra_args={}
    if(in_file):
        console.print(f"Since [bold]data_root[/bold] is {data_root}, the following location is to be read {utils.resolve_file_name(in_file,data_root)}")
        curr_locals=locals()
        extra_args={k: curr_locals[k] for k in ['delimiter', 'file_type', 'replace_dict', 'tabular_loc_decode'] if k in curr_locals}
    #logging.root.level='debug'
    current_loaded_module_log_level=variable_loading.log.level
    variable_loading.log.setLevel(logging.DEBUG)
    log.info("For better idea of transformations performed a debug mode is turned on!")
    tmp_values=np.array([])
    if(in_file):
        tmp_values=variable_loading.read_data_file(utils.resolve_file_name(in_file,data_root),decode,**extra_args)
    # Let's print what we have so far
    var_table_init=rich.table.Table(show_header=False,box=rich.box.SQUARE)
    var_table_init.add_row(f"[bold]len={len(tmp_values)}")
    for value in tmp_values:
        var_table_init.add_row(str(value))
    console.print("The variable loaded directly from the input file (before transformations) looks the following:",var_table_init)

    show_tables_dict=collections.OrderedDict([("From_file",var_table_init)])
    # Let's get transformations now!
    ## First, for complecated transformations other tables might be necessary, thus loading steering_file if provided
    submission=None
    submission_dict={}
    if(steering_file):
        log.debug(f"Steering file {steering_file} has been provided and is being read.")
        requested_tables=get_requested_table_list(steering_file,load_all_tables,indices,names)
        submission=submission_for_selected_tables(steering_file,data_root,load_all_tables,requested_tables)
        submission_dict=submission.__dict__

    console.rule("data_type")
    var_table_datatype=rich.table.Table(show_header=False,box=rich.box.SQUARE)
    if(data_type):
        console.print(f"data_type has been specified ({data_type}) and is being enforced.")
        if(data_type!='' and tmp_values is not None):
            try:
                tmp_values=tmp_values.astype(data_type)
            except Exception as exc:
                log.error(f"Translation of variable to specific data_type has failed. You wanted '{data_type}' on {tmp_values}")
                raise exc
        # Let's store what we have so far for displaying later
        var_table_datatype.add_row(f"[bold]len={len(tmp_values)}")
        for value in tmp_values:
            var_table_datatype.add_row(str(value))
        show_tables_dict[f"data_type({data_type})"]=var_table_datatype

    console.rule("transformations")
    transformation_tables=[]
    if(transformations):
        for index,transformation in enumerate(transformations):
            console.print(f"Applying transformation '{transformation}' to the variable. Prior to the transformation your variable has the following properties: size={len(tmp_values)},shape={tmp_values.shape},dtype={tmp_values.dtype}.")
            #
            tmp_values=perform_transformation(transformation,submission_dict,{"VAR":tmp_values})
            if(not isinstance(tmp_values,Iterable)):
                console.rule()
                console.print("Output of transformation needs to be Iterable (e.g. list or numpy array).")
                console.print("You can construct those from the following objects:")
                print_dict_highlighting_objects(submission_dict)
                raise TypeError(f"Transformation '{transformation}' has returned a variable not of the type Variable.")

            #
            # Let's store what we have so far for displaying later
            transformation_tables.append(rich.table.Table(show_header=False,box=rich.box.SQUARE))
            transformation_tables[-1].add_row(f"[bold]len={len(tmp_values)}")
            for value in tmp_values:
                transformation_tables[-1].add_row(str(value))
            show_tables_dict[f"tr_{index}"]=transformation_tables[-1]
    if(transformations or data_type):
        console.rule("summary of data transformations")
        show_table=rich.table.Table()
        for key in show_tables_dict:
            show_table.add_column(key)
        show_table.add_row(*list(show_tables_dict.values()))
        console.print(show_table)
    console.rule("steering file snipped")
    variable_json=variable_loading.get_variable_steering_snipped(in_file,decode,data_type,transformations,**extra_args)

    console.rule("You can use following code in your json steering file:")
    utils.check_schema(variable_json,'variable.json')
    console.print(json.dumps(variable_json,indent=4))
    variable_loading.log.setLevel(current_loaded_module_log_level)
    
@hepdata_maker.command()
@click.argument('steering_file',type=click.Path(exists=True))
@click.option('--data-root', default='./', help='Location of files specified in steering file (if not an absolute location is given there)',type=click.Path(exists=True),)
@click.option('--load-all-tables/--load-only-selected', '-a/-o', default=True)
@click.option('--indices', '-i', type=int,multiple=True)
@click.option('--names', '-n', type=str,multiple=True)
def create_table_of_content(steering_file,data_root,load_all_tables,indices,names):
    console.rule("table of content",characters="=")
    requested_tables=get_requested_table_list(steering_file,load_all_tables,indices,names)
    submission=submission_for_selected_tables(steering_file,data_root,load_all_tables,requested_tables)
    print_which_tables="all" if load_all_tables else requested_tables
    console.print(f"Creating table of content for {print_which_tables} tables.")
    submission.create_table_of_content()
    toc=[table for table in submission.tables if table.name=='overview']
    if(len(toc)<1):
        log.error("Issue encountered. Somehowe table of content was not created. Seems like but on the side of the hepdata_submission_maker.")
    if(len(toc)>1):
        log.error("Several 'overview' tables encountered. You have probably submitted faulty data.")
    console.rule("retrieved table-of-content:")
    console.print(toc[0].title)
    console.rule("steering file snipped")
    table_json=toc[0].steering_file_snippet()
    console.rule("You can add following table in your json steering file:")
    console.print(json.dumps(table_json,indent=4))



def check_if_file_exists_and_readable(file_path):
    import yaml
    import json
    import csv
    import uproot
    import os.path
    from collections import OrderedDict
    from TexSoup import TexSoup
    
    # function to verify that 'file_path' is readable file with one of this types:
    #   - json 
    #   - yaml
    #   - root
    #   - csv
    #   - tex
    #   - txt --> used as table title!
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

def decode_variable_from_hepdata(variable,var_index,in_file,is_independent):
    from .Submission import is_name_correct
    import jq
    import time

    tmp_name=variable['header']['name']
    fancy_var_name=tmp_name
    var_name=tmp_name if is_name_correct(tmp_name) else f"var_{'ind' if is_independent else 'dep'}_{var_index}"
    var_units=variable['header'].get('units',"")
    #print("variable units",var_units)
    errors=[]
    base_var_field_name="independent_variables" if is_independent else "dependent_variables"
    qualifiers=variable.get('qualifiers',[])
    if(len(variable['values'])>0):
        error_names=list(set(jq.all('.values[].errors?[]?.label',variable)))
        #print(len(error_names))
        #start=time.time()
        for err_index,tmp_name in enumerate(error_names):
            err_fancy_name=tmp_name
            err_name=tmp_name if is_name_correct(tmp_name) else f"err_{err_index}"

            # Here we try to save some time in case error is present in the first entry.
            err=jq.all(f'.errors?[]?| select(.label=="{tmp_name}")',variable['values'][0])
            if(err==[]):
                # if it is not, we need to loop over all entries (more time consuming)
                err=jq.first(f'.values[].errors?[]?| select(.label=="{tmp_name}")',variable)
            else:
                err=err[0]
            
            if('asymerror' in err):
                err_decode=f".{base_var_field_name}[{var_index}].values[].errors| if .==null then [0,0] else .[] | select(.label==\"{tmp_name}\") | .asymerror | [.minus,.plus] end"
            elif('symerror' in err):
                err_decode=f".{base_var_field_name}[{var_index}].values[].errors| if .==null then null else .[] | select(.label==\"{tmp_name}\") | .symerror end"
            else:
                raise ValueError("I have not expected error that is not symerror not asymerror!")
            err_steering={"name":err_name,"fancy_name":err_fancy_name,"in_files":[{"name":in_file,"decode":err_decode}]} # No units are present for hepdata records as far as I am aware.
            #print({"name":err_name,"fancy_name":err_fancy_name,"in_files":[{"name":in_file,"decode":err_decode}],"units":err_units})
            errors.append(err_steering)
        #stop=time.time()
        #print(f"timing to get through {len(error_names)} errors={stop-start}")
        if('high' in variable['values'][0]):
            decode=f".{base_var_field_name}[{var_index}].values[] | [.low,.high]"
        else:
            decode=f".{base_var_field_name}[{var_index}].values[].value"
        #print({"in_files":[{"name":in_file,"decode":decode}],"name":var_name,'fancy_name':fancy_var_name,"is_independent":is_independent,"errors":errors,"qualifiers":qualifiers,"units":var_units})
        return {"in_files":[{"name":in_file,"decode":decode}],"name":var_name,'fancy_name':fancy_var_name,"is_independent":is_independent,"errors":errors,"qualifiers":qualifiers,"units":var_units}
    else:
        return {"name":var_name,"fancy_name":fancy_var_name,"is_independent":is_independent,"qualifiers":qualifiers,"units":var_units}
@hepdata_maker.command()
@click.option('--output','-o',default='steering_file.json',help='output file path/name',type=click.Path(exists=False))
@click.option('--directory','-d', help='Directory to search through for files',type=click.Path(exists=True))
@click.option('--force','-f', help='Overwride output file if already exists', is_flag=True)
def hepdata_to_steering_file(output,directory,force):
    console.rule("converting hepdata submission files to hepdata_maker steering file",characters="=")
    import glob
    import os.path
    import yaml
    from .Submission import is_name_correct
    #from .Submission import name_corrected
    from .Submission import Variable
    from .Submission import Table
    from . import checks
    import time
    
    if(os.path.exists(output) and not force):
        raise ValueError(f"{output} file already exists! Give different name or use --force/-f option.")

    if(directory is None):
        raise ValueError(f"No directory to traverse was given!")

    yaml_files=glob.glob(directory+"/**/*.yaml",recursive=True)
    yaml_basenames_dict={os.path.basename(path):path for path in yaml_files}
    if("submission.yaml" in yaml_basenames_dict):
        submission_file_path=yaml_basenames_dict["submission.yaml"]
        checks.validate_submission(submission_file_path) # This will rase issues if something is wrong with submission file or correspondind data file 
        
        #sub=Submission()
        steering_data={"tables":[],"additional_resources":[]}
        basedir=os.path.dirname(submission_file_path)
        stream=open(submission_file_path, 'r')
        hepdata_submission = yaml.safe_load_all(stream)
        # Loop over all YAML documents in the submission.yaml file.
        tab_index=0
        for doc in hepdata_submission:
            # Skip empty YAML documents.
            if not doc:
                continue
            tab_index+=1
            if('comment' in doc):
                console.rule(f"[bold]comment")
                steering_data['comment']=doc['comment']
                steering_data['data_license']=doc['data_license']
                if('additional_resources' in doc):
                    for item in doc['additional_resources']:
                        location=utils.resolve_file_name(item['location'],basedir)
                        item['location']=location
                        steering_data['additional_resources'].append(item)
            elif('data_file' in doc):
                console.rule(f"[bold]{doc['name']}")
                tab_steering={}
                fancy_name=doc['name']
                name=doc['name'] if is_name_correct(doc['name']) else f"table_{tab_index}"
                images=[]
                other_resources=[]
                if('additional_resources' in doc):
                    for add_resource in doc['additional_resources']:
                        file_ext=(os.path.splitext(add_resource['location'])[-1]).lower()
                        #print(add_resource['location'],"file extention:", file_ext)
                        location=utils.resolve_file_name(add_resource['location'],basedir)
                        if(file_ext=='.jpg' or file_ext=='.pdf' or file_ext=='.png' or file_ext=='.eps'):
                            if(not os.path.basename(location).startswith("thumb_")):
                                # We do not want to include thumbnails (they will be later recreated in hepdata_lib)
                                images.append({"name":location,"description":add_resource['description']})
                        else:
                            other_resources.append({"location":location,"description":add_resource['description']})
                title=doc.get('description',"")
                location=doc.get('location',"")
                keywords=doc.get('keywords',[])
                translated_keywords={}
                for key in keywords:
                    translated_keywords[key['name']]=key['values']
                variables=[]
                in_file=utils.resolve_file_name(doc['data_file'],basedir)
                with open(in_file, 'r') as stream:
                    data_loaded = yaml.safe_load(stream)
                #dependent_variables
                for var_index,variable in enumerate(data_loaded['dependent_variables']):
                    with console.status(f"Decoding information about variable {variable['header']['name']}"):
                        variables.append(decode_variable_from_hepdata(variable,var_index,in_file,is_independent=False))
                #print("Read all dependent variables")
                #independent_variables
                for var_index,variable in enumerate(data_loaded['independent_variables']):
                    with console.status(f"Decoding information about variable {variable['header']['name']}"):
                        variables.append(decode_variable_from_hepdata(variable,var_index,in_file,is_independent=True))
                    #print("Read all independent variables")
                #print("variables",variables)
                #print("additional_resources read by cli",other_resources)
                #start=time.time()
                steering_data['tables'].append({"name":name,"fancy_name":fancy_name,"images":images,'additional_resources':other_resources,"title":title,"location":location,"keywords":translated_keywords,"variables":variables})
                #stop=time.time()
                #print(f"Adding table {name} took {stop-start} seconds")
            else:
                log.error("Something is wrong. I did not expect this type of submission_file section!")
                exit(2)
    console.rule(f"[bold]Verifying & saving created steering_file")
    with open(output, 'w') as outfile:
        utils.check_schema(steering_data,'steering_file.json')
        json.dump(steering_data, outfile,indent=4)
    console.print(f"Succesfully created steering_file '[bold]{output}[/bold]'")
@hepdata_maker.command()
@click.option('--output','-o',default='steering_file.json',help='output file path/name',type=click.Path(exists=False))
@click.option('--directory','-d', help='Directory to search through for files',type=click.Path(exists=True))
@click.option('--only-steering-files', help='Search only for steering files in the directory', default=False)
@click.option('--force','-f', help='Overwride output file if already exists', is_flag=True)
def create_steering_file(output,directory,only_steering_files,force):
    import glob
    import os.path
    from hepdata_lib import RootFileReader
    from .Submission import Variable
    from .Submission import Table
    import csv
    from .Submission import is_name_correct
    from collections import OrderedDict

    if(os.path.exists(output) and not force):
        raise ValueError(f"{output} file already exists! Give different name or use --force/-f option.")

    if(directory is None):
        raise ValueError(f"No directory to traverse was given!")
    
    steering_files=glob.glob(directory+"/**/*_steering.json",recursive=True)
    figure_files=glob.glob(directory+"/**/*.pdf",recursive=True)# prefer pdf files if they are both pdf and png
    figure_files+=[x for x in glob.glob(directory+"/**/*.png",recursive=True) if x.replace(".png",".pdf") not in figure_files] # add png if not added as pdf
    log.debug(f"discovered following steering files: {steering_files}")
    # 1)implement all *_steering.json files:
    to_save_steering_files={}
    for steering_file in sorted(steering_files):
        try:
            with open(steering_file, 'r') as stream:
                jsondata=json.load(stream,object_pairs_hook=OrderedDict)
            utils.check_schema(jsondata,"table.json")
            tab=Table(tab_steering=jsondata) # just making sure it works. We do not need this object actually. 
            tab_name=os.path.basename(steering_file).replace("_steering.json","")
            to_save_steering_files[tab_name]=steering_file
            # Remove figures conrrespondning to the steering file:
            figure_files=[fig for fig in figure_files if not os.path.splitext(os.path.basename(fig))[0]==tab_name]
            
        except Exception as ex:
            log.info(f" table steering file {steering_file} is not correctly formatted and will not be included in the steering file constructed\n ERROR:{ex}.") 
    log.debug(f"discovered following figures (excluding already included in steering_files): {figure_files}")
    sub=Submission()
    sub.generate_table_of_content=True
    # 2) loop over remaining figures:
    
    for figure_path in sorted(figure_files):
        fig_dir=os.path.dirname(figure_path)
        fig_name_core=".".join(os.path.basename(figure_path).split(".")[:-1])
        associated_files=glob.glob(fig_dir+'/'+fig_name_core+".*")
        associated_files.remove(figure_path)
        try:
            associated_files.remove(re.sub(".pdf$",".png",figure_path)) # if pdf & png file exsitst together, only pdf file is used
        except ValueError:
            # ignore case when the file not found in the list.
            True
        #print(associated_files)
        selected_associated_files={}
        if(associated_files):
            for associated_path in associated_files:
                if(check_if_file_exists_and_readable(associated_path)):
                    file_type=associated_path.split(".")[-1].lower()
                    selected_associated_files[file_type]=associated_path
                else:
                    log.debug(f" File {associated_path} not recognised as relevant for hepdata.")
        title="Here you should explain what your table shows"
        tab_name=f"{fig_name_core}"
        location=f"data from figure {fig_name_core}"

        tab_steering={
            "name":tab_name,
            "title":title,
            "location":location,
            "images":[
                {
                    "name":figure_path
                }
            ]
            
        }
        tab=Table(tab_steering=tab_steering)

        
        replace_dict=None
        tabular_loc_decode=None
        comments=[]
        variables=[]
        if("txt" in selected_associated_files):
            log.debug(f"file {selected_associated_files['txt']} added as a title to table centered around figure {figure_path}")
            title=selected_associated_files['txt'] # It is supported to have titles read directly from files
        # mind, if we have more than one data_file(json/root/yaml/csv), only one will be selected, given by the following order:

        if("root" in selected_associated_files):
            # In this part we find an object inside the root file that will open fine for user
            # This object will probably be of no relevance for the user, but
            # serves as an example
            log.debug(f"Trying to find suitable example inside root file {selected_associated_files['root']}")
            file_path=selected_associated_files['root']
            av_items=variable_loading.get_list_of_objects_in_root_file(file_path)
            av_item_names_no_cycle=[name.split(';')[0] for name in av_items]
            suitable_object=None
            rreader=RootFileReader(file_path) # this should not fail as the file was checked before
            for obj_name in av_items:
                item_classname=av_items[obj_name]
                loaded_object_hepdata_lib=None
                try:
                    if( "TH1" in item_classname):
                        loaded_object_hepdata_lib=rreader.read_hist_1d(obj_name)
                    elif( "TH2" in item_classname):
                        loaded_object_hepdata_lib=rreader.read_hist_2d(obj_name)
                    elif("RooHist" in item_classname or "TGraph" in item_classname):
                        loaded_object_hepdata_lib=rreader.read_graph(obj_name)
                except Exception:
                    log.debug(f" failed to read object {obj_name} inside root file {file_path}. Skipping the object")
                    continue
                if(loaded_object_hepdata_lib and "x" in loaded_object_hepdata_lib.keys()):
                    suitable_object=obj_name
                    break;
            if(suitable_object is not None):
                in_file=f'{selected_associated_files["root"]}:{suitable_object}'
                variables.append({"in_file":in_file,"decode":"x","name":"variable_x","is_independent":True})
                variables.append({"in_file":in_file,"decode":"y","name":"variable_y","is_independent":False})
                
        elif("json" in selected_associated_files):
            in_file=selected_associated_files["json"]
            variables.append({"in_file":in_file,"decode":"keys_unsorted","name":"keys","is_independent":True})
            variables.append({"in_file":in_file,"decode":".[keys_unsorted[]] | keys_unsorted","name":"keys_of_keys","is_binned":False,"is_independent":False})
        elif("yaml" in selected_associated_files):
            in_file=selected_associated_files["yaml"]
            variables.append({"in_file":in_file,"decode":"keys_unsorted","name":"keys","is_independent":True})
            variables.append({"in_file":in_file,"decode":".[keys_unsorted[]] | keys_unsorted","name":"keys_of_keys","is_binned":False,"is_independent":False})
        elif("csv" in selected_associated_files):
            in_file=selected_associated_files["csv"]
            try:
                with open(in_file) as csvfile:
                    dialect = csv.Sniffer().sniff(csvfile.read(1024))
                with open(in_file) as csvfile:
                    csv_reader = csv.DictReader(csvfile,dialect=dialect)
                    delimiter=dialect.delimiter
                    for index,key in enumerate(csv_reader.fieldnames):
                        name=key if is_name_correct(key) else f"variable_{index}"
                        variables.append({"in_file":in_file,"name":name,"decode":f"{key}","delimiter":delimiter,"is_independent":(index==0)})
            except Exception as ex:
                log.debug(f" failed in discovering csv file {in_file}! File skipped.")
                log.debug(ex)

        elif("tex" in selected_associated_files):
            in_file=selected_associated_files["tex"]
            try:
                tex_table=variable_loading.get_table_from_tex(in_file,"latex.find_all(['tabular*','tabular'])[0]")
                for index,variable_name in enumerate(tex_table[0,:]):
                    sanitised_name=variable_name if is_name_correct(variable_name) else f"variable_{index}"
                    variables.append({"in_file":in_file,"name":sanitised_name,"tabular_loc_decode":"latex.find_all(['tabular*','tabular'])[0]","decode":f"table[1:,{index}]","replace_dict":{},
                                      "is_independent":(index==0)})
            except Exception:
                log.debug(f"failed to read tex table of {tab_name} inside tex-file {in_file}. Not including the tex file")
        
        for variable_info in variables:
            var_steering={
                "name":variable_info['name'],
                "in_files":
                [
                    {
                        "name":variable_info['in_file'],
                        "decode":variable_info['decode']
                    }
                ]
            }
            delimiter=variable_info.get('delimiter',"")
            if(delimiter!=""):
                var_steering['in_files'][0]['delimiter']=delimiter
            is_binned=variable_info.get('is_binned',"")
            if(is_binned!=""):
                var_steering['is_binned']=is_binned
            is_independent=variable_info.get('is_independent',"")
            if(is_independent!=""):
                var_steering['is_independent']=is_independent
            tabular_loc_decode=variable_info.get('tabular_loc_decode',"")
            if(tabular_loc_decode!=""):
                var_steering['in_files'][0]['tabular_loc_decode']=tabular_loc_decode
            replace_dict=variable_info.get('replace_dict',"")
            if(replace_dict!=""):
                var_steering['in_files'][0]['replace_dict']=replace_dict
            

            var=Variable(var_steering=var_steering)
            tab.add_variable(var)
        sub.add_table(tab)
    all_table_names=sorted(sub.get_table_names()+list(to_save_steering_files.keys()))

    final_tables=[]
    for tab_name in all_table_names:
        if(tab_name in to_save_steering_files):
            relative_path_steering_file=os.path.relpath(to_save_steering_files[tab_name],os.path.dirname(output))
            final_tables.append({"$ref":relative_path_steering_file})
        else:
            index=sub.table_index(tab_name)
            final_tables.append(sub.tables[index].steering_file_snippet())

    # Get steering file constructed from figures
    steering_json_from_figures=sub.steering_file_snippet()
        
    # update it with all tables (including the one with jsonref!)
    log.debug(f" all tables (including unresolved):")
    log.debug(json.dumps(final_tables,indent=4))
    steering_json_from_figures['tables']=final_tables
    with open(output, 'w') as outfile:
        json.dump(steering_json_from_figures, outfile,indent=4)
    
hepdata_maker.add_command(create_submission)
hepdata_maker.add_command(check_schema)
hepdata_maker.add_command(check_table)
hepdata_maker.add_command(check_variable)
hepdata_maker.add_command(create_table_of_content)
hepdata_maker.add_command(create_steering_file)
hepdata_maker.add_command(hepdata_to_steering_file)
