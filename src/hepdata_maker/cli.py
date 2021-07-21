import click
from .Submission import Submission
from . import utils 

@click.group(context_settings=dict(help_option_names=['-h', '--help']))
def hepdata_maker():
    """Top-level CLI entrypoint."""


@click.command()
@click.argument('steering_file',type=click.Path(exists=True))
@click.option('--data-root', default='./', help='Location of files specified in steering file (if not an absolute location is given there)',type=click.Path(exists=True),)
@click.option('--output-dir', default='submission_files', help='The name of the directory where the submission files will be created. Default: submission_files',type=click.Path(exists=False))
def create_submission(steering_file,data_root,output_dir):
    print(f"Creating submission file based on {steering_file}:")
    #print(f"!!! {data_root} !!!")
    submission=Submission()
    submission.load_table_config(steering_file)
    submission.implement_table_config(data_root)
    # TODO require user to confirm overwriting output_dir if it already exist
    submission.create_hepdata_record(data_root,output_dir)

@click.command()
@click.argument('steering_file',type=click.Path(exists=True))
def check_schema(steering_file):
    print(f"Checking schema of {steering_file}:")
    utils.check_schema(steering_file,'steering_file.json')
    print("All ok!")
hepdata_maker.add_command(create_submission)
hepdata_maker.add_command(check_schema)

