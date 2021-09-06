import click
from .Submission import Submission,rich_highlight_dict_objects,decode_variable_from_hepdata,perform_transformation
from .Submission import Variable
from .Submission import Table
from .logs import logging
from .console import console
from . import utils
from . import checks
from . import variable_loading
from . import useful_functions as ufs
from .version import __version__
from .variable_loading import check_if_file_exists_and_readable
from .variable_loading import yaml_ordered_safe_load, yaml_ordered_safe_load_all
from collections.abc import Iterable
import numpy as np
import rich.columns 
import rich.table 
import rich.panel
import collections
import re 
import scipy.stats, scipy.special  # type: ignore
import json
import jsonref # type: ignore
import os.path
from typing import List,Optional,Dict,Any,Tuple

## hepdata_maker
@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.version_option(version=__version__)
@click.option('--log-level',
              type=click.Choice(list(logging._levelToName.values()),
                                case_sensitive=False),
              default="INFO",help="set log level.")
def hepdata_maker(log_level):
    """hepdata_maker base CLI entry"""
    from .logs import set_default_logger
    set_default_logger(log_level)
    log = logging.getLogger(__name__)
    log.debug(f"Log-level is {log_level}")

# Global logging object can only be created after debug level is set above
log = logging.getLogger(__name__)

## hepdata_maker create_submission
@hepdata_maker.command()
@click.argument('steering_file',type=click.Path(exists=True))
@click.option('--data-root', default='./',
              type=click.Path(exists=True),
              help="""Location of data files specified in the steering file.
              This is used if a relative path is given for
              data/image/resource files.

              Their names are then resolved to
              ``<data-root>/<relative_path_given_in_steering_file>``.

              By default, execution directory is used.
              """)
@click.option('--output-dir',
              default='submission_files',
              type=click.Path(exists=False),
              help="""The name of the directory where the submission files
              will be created into.

              Default: ``submission_files``.
              """)
@click.option('--use-fancy-names',
              is_flag=True,
              help="""Force 'fancy-names' to be used for tables,
              variables and uncertainties.
              """)
def create_submission(steering_file,data_root,output_dir,use_fancy_names):
    """
    Create HEPdata submission files using STEERING_FILE.

    Args:
      steering_file: the path to the (hepdata_maker) steering file to use.
    """
    log.debug(f"Creating submission file based on {steering_file}. Data-root is {data_root} and the output directory {output_dir}. ")
    console.rule("create_submission",characters="=")
    console.print(f"Loading submission information based on {steering_file}")
    submission=Submission()
    submission.read_table_config(steering_file)
    submission.load_table_config(data_root)
    # TODO require user to confirm overwriting output_dir if it already exist
    with console.status("Creating hepdata files (this might take a while)..."):
        submission.create_hepdata_record(data_root,output_dir,use_fancy_names)

## hepdata_maker check_schema
@hepdata_maker.command()
@click.argument('steering_file',type=click.Path(exists=True))
def check_schema(steering_file):
    """
    Check STEERING_FILE against hepdata_maker\'s schema.

    Args:
      steering_file: the path to the (hepdata_maker) steering file to use.
    """
    console.rule("checking_schema",characters="=")
    console.print(f"Checking schema of {steering_file}.")
    with open(steering_file, 'r') as fstream:
        log.debug("file://"+os.path.abspath(os.path.dirname(steering_file)),steering_file)
        json_data = jsonref.load(fstream,base_uri="file://"+os.path.abspath(os.path.dirname(steering_file))+"/")
    utils.check_schema(json_data,'steering_file.json')
    console.print(f"    All ok!    ")


def submission_for_selected_tables(steering_file:str,
                                   data_root:str,
                                   load_all_tables:bool,
                                   requested_tables:List[Tuple[str,bool]])->Submission:
    """
    Create Submission object from STEERING_FILE loading all or only selected tables.
    """
    console.print(f"Loading requested tables based on {steering_file}")
    submission=Submission()
    submission.read_table_config(steering_file)
    if(load_all_tables):
        submission.load_table_config(data_root)
    else:
        submission.load_table_config(data_root,selected_table_names=requested_tables)

    return submission

## hepdata_maker check_table
@hepdata_maker.command()
@click.argument('steering_file',
                type=click.Path(exists=True))
@click.option('--data-root',
              default='./',
              type=click.Path(exists=True),
              help="""Location of data files specified in the steering file.
              This is used if a relative path is given for
              data/image/resource files.

              Their names are then resolved to
              ``<data-root>/<relative_path_given_in_steering_file>``.

              By default, execution directory is used.
              """)
@click.option('--load-all-tables/--load-only-selected','-a/-o',
              help="""Choose whether to load all tables specified in the steering file
              or only the selected ones.
              """,
              default=True)
@click.option('--indices', '-i',
              type=int,
              help="Specify the indices of tables to print out.",
              multiple=True)
@click.option('--names', '-n',
              type=str,
              help="Specify names of the tables to print out.",
              multiple=True)
def check_table(steering_file,data_root,load_all_tables,indices,names):
    """
    Print out informations stored in selected tables from STEERING_FILE.
    You can specify tables by names or location in the steering file.

    Args:
      steering_file: the path to the (hepdata_maker) steering file to use.

    By default all tables from the steering file are being loaded
    (more specifically those with 'should_be_loaded'=True).
    This is because your selected tables can depend on the variables
    from other tables too. If this is not the case you can use
    '--load-only-selected' flag to speed up execution.
    """
    console.rule("check_table",characters="=")
    requested_tables=utils.get_requested_table_list(steering_file,load_all_tables,indices,names)
    submission=submission_for_selected_tables(steering_file,data_root,load_all_tables,requested_tables)
    console.print(f"Printing requested tables:")
    print(requested_tables,submission.tables)
    for table in submission.tables:
        if(any(table.name==name and should_process for name,should_process in requested_tables)):
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
            if(len(keyword_tables)>0):
                columns = rich.columns.Columns(keyword_tables, equal=True, expand=False)
                console.print("keywords:",rich.panel.Panel(columns,expand=False))
            if(len(table.images)>0):
                tmp_rich_table=rich.table.Table()
                image_info_grid=tmp_rich_table.grid()
                for image_info in table.images:
                    image_table=rich.table.Table(show_header=False,box=rich.box.SQUARE)
                    image_table.add_row("name: "+image_info.get('name',None))
                    image_table.add_row("label: "+image_info.get('label',''))
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

## hepdata_maker check_variable
@hepdata_maker.command()
@click.option('--in-file','-f',
              type=click.Path(exists=False),
              help="Path to the data file to be used for decoding.")
@click.option('--file-type',
              type=click.Choice(['json', 'yaml','csv','root','tex'],
                                case_sensitive=False),
              help="""Specify the file type of the data file
              (if cannot be guessed from file extention).
              """)
@click.option('--decode','-d',
              type=str,
              help="""Command specifying how to read the data file.
              Required syntax depends on the type of the file read.

              See specific 'get_array_from_[file_type]' functions (python API) for details:

                - :py:func:`hepdata_maker.variable_loading.get_array_from_root`
                - :py:func:`hepdata_maker.variable_loading.get_array_from_json`
                - :py:func:`hepdata_maker.variable_loading.get_array_from_yaml`
                - :py:func:`hepdata_maker.variable_loading.get_array_from_csv`
                - :py:func:`hepdata_maker.variable_loading.get_array_from_tex`
              """)
@click.option('--data-type','-t',
              type=str,
              help='How loaded data should be treated (what is its type, e.g. float, str).')
@click.option('--tabular-loc-decode',
              type=str,
              help="""Only used when reading latex files.

              This variable should point to the 'tabular' environment that is desired.
              It should use information from TexSoup (https://texsoup.alvinwan.com/) object
              called "latex" that is created from the input file given.
              In most cases something along this line is sufficient:

              `tabular_loc_decode":"latex.find_all(['tabular*','tabular'])[0]"`

              which selects the first tabular/tabular* environment found.
              """)
@click.option('--delimiter',
              type=str,
              default=',',
              help="The delimiter used when the csv file is read. Default: ','")
@click.option('--replace_dict',
              type=str,
              default='{}',
              help=r"""A string with json-style dictionary used for replacing symbols inside the table.
              Internally `re.sub(key,value,text)` is executed on all key, value pairs.

              Example:
                Replacing custom tags, e.g. '\\GeV' with 'GeV':
                  ``"{'\\\\GeV':'GeV'}"`` (mind the 4-backslashes)



              See https://docs.python.org/3/library/re.html
              for regex patterns allowed and
              https://docs.python.org/3/howto/regex.html#the-backslash-plague
              for the need of multiple backslashes.
              """)
@click.option('--transformation','-x','transformations',
              type=str,
              multiple=True,
              help="""numpy-style transformation returning a 1-D array/ndarray.

              Example:
                ``"mt-mn"``

                where mt, mn -- previously loaded variables
                (say the mass of the stop-squark and the neutralino respectively),
                results in the element-wise difference between the two.
              """)
@click.option('--steering-file','-s',
              type=click.Path(exists=True),
              help="""The path to the (hepdata_maker) steering file to load.
              Here this is used to provide all the variables from the steering file
              to be accesible for your transformations.
              """)
@click.option('--data-root',
              default='./',
              type=click.Path(exists=True),
              help="""Location of data files specified in the steering file.
              This is used if a relative path is given for
              data/image/resource files.

              Their names are then resolved to
              ``<data-root>/<relative_path_given_in_steering_file>``.

              By default, execution directory is used.
              """)
@click.option('--load-all-tables/--load-only-selected', '-a/-o',
              default=True,
              help="""Choose whether to load all tables specified
              in the steering file or only the selected ones.
              """)
@click.option('--indices', '-i',
              type=int,
              multiple=True,
              help="Specify the indices of tables to load from the steering_file.")
@click.option('--names', '-n',
              type=str,
              multiple=True,
              help="Specify names of the tables to load from the steering_file.")
def check_variable(in_file,data_root,file_type,decode,data_type,tabular_loc_decode,delimiter,replace_dict,transformations,steering_file,load_all_tables,indices,names):
    """
    Create variable (1-D numpy array) based on information provided.

    This funtion helps finding out correct commands and transformations
    used to decode data_files.
    """
    console.rule("check_variable",characters="=")
    console.print("This option checks whether you provide correct information for loading a variable and helps you debug.")
    console.rule("in_file")
    #console.print("Provide information on the location of the file (.json/.yaml/.root/.csv or .tex files) with variable information")
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
        requested_tables=utils.get_requested_table_list(steering_file,load_all_tables,indices,names)
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
                rich_highlight_dict_objects(submission_dict)
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

## hepdata_maker create_table_of_content
@hepdata_maker.command()
@click.argument('steering_file',
                type=click.Path(exists=True))
@click.option('--data-root',
              default='./',
              type=click.Path(exists=True),
              help="""Location of data files specified in the steering file.
              This is used if a relative path is given for
              data/image/resource files.

              Their names are then resolved to
              ``<data-root>/<relative_path_given_in_steering_file>``.

              By default, execution directory is used.
              """)
@click.option('--load-all-tables/--load-only-selected', '-a/-o',
              default=True,
              help="""Choose whether to load (and create TOC for)
              all tables specified in the steering file or only the selected ones.
              """)
@click.option('--indices', '-i',
              type=int,
              multiple=True,
              help="Specify the indices of tables to load from the steering_file.")
@click.option('--names', '-n',
              type=str,
              multiple=True,
              help="Specify names of the tables to load from the steering_file.")
def create_table_of_content(steering_file,data_root,load_all_tables,indices,names):
    """
    Create a table of content for all the tables found in the STEERING_FILE
    that can be used in your submission.

    You can put the output (snippet) directly into your 'steering_file'
    as a table called 'overview'.
    You can also customise the table of content by changing the provided
    snippet to suit your requirements.

    Args:
      steering_file: the path to the (hepdata_maker) steering file
        to create the table of content for.
    """
    console.rule("table of content",characters="=")
    requested_tables=utils.get_requested_table_list(steering_file,load_all_tables,indices,names)
    submission=submission_for_selected_tables(steering_file,data_root,load_all_tables,requested_tables)
    print_which_tables="all" if load_all_tables else requested_tables
    console.print(f"Creating table of content for {print_which_tables} tables.")
    submission.create_table_of_content()
    toc=[table for table in submission.tables if table.name=='overview']
    if(len(toc)<1):
        log.error("Issue encountered. Somehowe table of content was not created. Seems like bug on the side of the hepdata_submission_maker.")
    if(len(toc)>1):
        log.error("Several 'overview' tables encountered. You have probably submitted faulty data.")
    console.rule("retrieved table-of-content:")
    console.print(toc[0].title)
    console.rule("steering file snipped")
    table_json=toc[0].steering_file_snippet()
    console.rule("You can add following table in your json steering file:")
    console.print(json.dumps(table_json,indent=4))

## hepdata_maker hepdata_to_steering_file
@hepdata_maker.command()
@click.option('--output','-o',default='steering_file.json',type=click.Path(exists=False),
              help="The path to the output steering_file.")
@click.option('--directory','-d',type=click.Path(exists=True),
              help="The path to the directory with hepdata submission files (one record at a time please).")
@click.option('--force','-f', is_flag=True, help='Overwrite output file if already exists.')
def hepdata_to_steering_file(output,directory,force):
    """
    Create `hepdata_maker` steering_file from HEPdata submission files of a record.

    Example:
      - From https://hepdata-submission.readthedocs.io/en/latest/examples.html
        one can download 'HEPData' example submission:

        ``wget https://hepdata-submission.readthedocs.io/en/latest/examples.html -O orig_submission.zip``

        ``unzip -d orig_submission orig_submission.zip``

      - then one can run:

        ``hepdata_maker hepdata_to_steering_file --directory orig_submission``

        which creates file 'steering_file.json'

      - With `create_submission` command we can re-create, up-to (irrelevant) file names, the HEPData submission files:

        ``hepdata_maker create_submission --use-fancy-names``
    """
    console.rule("converting hepdata submission files to hepdata_maker steering file",characters="=")
    import glob
    from .Submission import is_name_correct
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
        checks.validate_submission(submission_file_path) # This will raise issues if something is wrong with submission file or correspondind data file 
        
        steering_data={"tables":[],"additional_resources":[]}
        basedir=os.path.dirname(submission_file_path)
        stream=open(submission_file_path, 'r')
        hepdata_submission = yaml_ordered_safe_load_all(stream)
        # Loop over all YAML documents in the submission.yaml file.
        tab_index=0
        for doc in hepdata_submission:
            # Skip empty YAML documents.
            if not doc:
                continue
            tab_index+=1
            if('comment' in doc or
               ('additional_resources' in doc and 'data_file' not in doc)):
                console.rule(f"[bold]comment")
                if('comment' in doc):
                    steering_data['comment']=doc['comment']
                if('data_license' in doc):
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
                    data_loaded = yaml_ordered_safe_load(stream)
                #dependent_variables
                for var_index,variable in enumerate(data_loaded['dependent_variables']):
                    with console.status(f"Decoding information about variable {variable['header']['name']}"):
                        variables.append(decode_variable_from_hepdata(variable,in_file,is_independent=False,var_index=var_index))

                #independent_variables
                for var_index,variable in enumerate(data_loaded['independent_variables']):
                    with console.status(f"Decoding information about variable {variable['header']['name']}"):
                        variables.append(decode_variable_from_hepdata(variable,in_file,is_independent=True,var_index=var_index))

                #start=time.time()
                steering_data['tables'].append({"name":name,"fancy_name":fancy_name,"images":images,'additional_resources':other_resources,"title":title,"location":location,"keywords":translated_keywords,"variables":variables})
                #stop=time.time()
                #print(f"Adding table {name} took {stop-start} seconds")
            else:
                log.error("Something is wrong. I did not expect this type of submission_file section!")
                log.error("Part unrecognised: {doc}")
                exit(2)
    console.rule(f"[bold]Verifying & saving created steering_file")
    with open(output, 'w') as outfile:
        utils.check_schema(steering_data,'steering_file.json')
        json.dump(steering_data, outfile,indent=4)
    console.print(f"Succesfully created steering_file '[bold]{output}[/bold]'")

## hepdata_maker create_steering_file
@hepdata_maker.command()
@click.option('--output','-o',default='steering_file.json',type=click.Path(exists=False),
              help="The path to the output steering_file.")
@click.option('--directory','-d',type=click.Path(exists=True),
              help='Directory to search through for files (figures and "table" steering files)')
@click.option('--only-steering-files', default=False,
              help='Search only for "table" steering files in the directory, i.e. skip image files.')
@click.option('--force','-f', is_flag=True,help='Overwride output file if already exists')
def create_steering_file(output,directory,only_steering_files,force):
    """
    Create a steering_file based on pdf/png and other files present in DIRECTORY.
    This is a good way to start with your submission preparation.

    The DIRECTORY is searched for:
       1) "table" steering files, with names '\*_stiring.json',
          containing table information.
       2) pdf/png files that are interpreted as table figures.
           If other files with the same basenames are found they are used either as:
           
           i) table title (if <baseneame>.txt),
           ii) data_files (if <basename>.root/.csv/.tex/.json/.yaml).
    """
    import glob
    import os.path
    from hepdata_lib import RootFileReader # type: ignore
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

        if("txt" in selected_associated_files):
            log.debug(f"file {selected_associated_files['txt']} added as a title to table centered around figure {figure_path}")
            title=selected_associated_files['txt'] # It is supported to have titles read directly from files

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

## hepdata_maker validate_submission
@hepdata_maker.command()
@click.argument('directory',type=click.Path(exists=True))
def validate_submission(directory):
    """
    Validate HEPdata submission files located in DIRECTORY.

    This is an off-line check one can run prior to
    uploading the files into HEPData.

    Args:
      directory: the path to the directory containing 'submission.yaml'
        and other submission files of HEPData.
    """
    console.rule("checking hepdata submission files",characters="=")
    checks.validate_submission(directory+'/submission.yaml')
    # If no error raised all is good
    console.print(f"The submission in '{directory}'[bold] is correct [/bold]HEPData submission!")

hepdata_maker.add_command(create_submission)
hepdata_maker.add_command(check_schema)
hepdata_maker.add_command(check_table)
hepdata_maker.add_command(check_variable)
hepdata_maker.add_command(create_table_of_content)
hepdata_maker.add_command(create_steering_file)
hepdata_maker.add_command(hepdata_to_steering_file)
hepdata_maker.add_command(validate_submission)
