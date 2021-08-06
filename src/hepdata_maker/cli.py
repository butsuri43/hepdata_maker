import click
from .Submission import Submission
from .Submission import print_dict_highlighting_objects
from .Submission import perform_transformation
from . import utils
from .logs import logging
from .console import console
from . import variable_loading
import numpy as np
import rich.columns 
import rich.table 
import rich.panel
import collections
import re
import scipy.stats, scipy.special
from . import useful_functions as ufs
from . import utils
import json

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

@click.command()
@click.argument('steering_file',type=click.Path(exists=True))
@click.option('--data-root', default='./', help='Location of files specified in steering file (if not an absolute location is given there)',type=click.Path(exists=True),)
@click.option('--output-dir', default='submission_files', help='The name of the directory where the submission files will be created. Default: submission_files',type=click.Path(exists=False))
def create_submission(steering_file,data_root,output_dir):
    log.debug(f"Creating submission file based on {steering_file}. Data-root is {data_root} and the output directory {output_dir}. ")
    console.rule("create_submission",characters="=")
    console.print(f"Loading submission information based on {steering_file}")
    submission=Submission()
    submission.read_table_config(steering_file)
    submission.load_table_config(data_root)
    # TODO require user to confirm overwriting output_dir if it already exist
    with console.status("Creating hepdata files (this might take a while)..."):
        submission.create_hepdata_record(data_root,output_dir)

@click.command()
@click.argument('steering_file',type=click.Path(exists=True))
def check_schema(steering_file):
    console.rule("checking_schema",characters="=")
    console.print(f"Checking schema of {steering_file}.")
    with open(steering_file, 'r') as fstream:
        json_data = json.load(fstream)
    utils.check_schema(json_data,'steering_file.json')
    console.print(f"    All ok!    ")

def get_requested_table_list(steering_file,indices,names):
    available_tables=utils.get_available_tables(steering_file)
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

@click.command()
@click.argument('steering_file',type=click.Path(exists=True))
@click.option('--data-root', default='./', help='Location of files specified in steering file (if not an absolute location is given there)',type=click.Path(exists=True),)
@click.option('--load-all-tables/--load-only-selected', '-a/-o', default=True)
@click.option('--indices', '-i', type=int,multiple=True)
@click.option('--names', '-n', type=str,multiple=True)
def check_table(steering_file,data_root,load_all_tables,indices,names):
    console.rule("check_table",characters="=")
    requested_tables=get_requested_table_list(steering_file,indices,names)
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
            #var_names_styles=[(var.name,"on gray") for var in table.variables]
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
                var_name_with_unit=var.name if (not var.unit) else var.name+" ["+var.unit+"]"
                rich_table.add_column(var_name_with_unit,style=style)
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

@click.command()
@click.option('--in-file','-f',type=click.Path(exists=False))
@click.option('--data-root', default='./', help='Location of in_file and files specified in steering file (if not an absolute location is given for those)',type=click.Path(exists=True))
@click.option('--file-type',type=click.Choice(['json', 'yaml','csv','root','tex'], case_sensitive=False))
@click.option('--decode','-d',type=str)
@click.option('--data-type','-t',type=str)
@click.option('--tabular-loc-decode',type=str)
@click.option('--delimiter',type=str,default=',')
@click.option('--replace_dict',type=dict,default={})
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
    if(in_file):
        console.print(f"Since [bold]data_root[/bold] is {data_root}, the following location is to be read {utils.resolve_file_name(in_file,data_root)}")
        curr_locals=locals()
        extra_args={k: curr_locals[k] for k in ['delimiter', 'file_type', 'replace_dict', 'tabular_loc_decode'] if k in curr_locals}
    #logging.root.level='debug'
    current_loaded_module_log_level=variable_loading.log.level
    variable_loading.log.setLevel(logging.DEBUG)
    log.info("For better idea of transformations performed a debug mode is turned on!")
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
        requested_tables=get_requested_table_list(steering_file,indices,names)
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
            if(not isinstance(tmp_values,np.ndarray)):
                console.rule()
                console.print("Output of transformation needs to be a numpy array.")
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


hepdata_maker.add_command(create_submission)
hepdata_maker.add_command(check_schema)
hepdata_maker.add_command(check_table)
hepdata_maker.add_command(check_variable)
