import click
from .Submission import Submission
from . import utils
from .logs import logging
from .console import console

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
    submission.load_table_config(steering_file)
    submission.implement_table_config(data_root)
    # TODO require user to confirm overwriting output_dir if it already exist
    with console.status("Creating hepdata files (this might take a while)..."):
        submission.create_hepdata_record(data_root,output_dir)

@click.command()
@click.argument('steering_file',type=click.Path(exists=True))
def check_schema(steering_file):
    console.rule("checking_schema",characters="=")
    console.print(f"Checking schema of {steering_file}.")
    utils.check_schema(steering_file,'steering_file.json')
    console.print(f"    All ok!    ")
hepdata_maker.add_command(create_submission)
hepdata_maker.add_command(check_schema)
