import click
from .Submission import Submission
from . import utils 

@click.group(context_settings=dict(help_option_names=['-h', '--help']))
def hepdata_maker():
    """Top-level CLI entrypoint."""


@click.command()
@click.argument('steering_file',type=click.Path(exists=True))
@click.option('--data-root', default='./', help='',type=click.Path(exists=True),)
def create_submission(steering_file,data_root):
    print(f"Creating submission file based on {steering_file}:")
    #print(f"!!! {data_root} !!!")
    submission=Submission()
    submission.load_table_config(steering_file)
    submission.implement_table_config(data_root)
    submission.create_hepdata_record(data_root)
    print("Submission created in test_submission")

@click.command()
@click.argument('steering_file',type=click.Path(exists=True))
def check_schema(steering_file):
    print(f"Checking schema of {steering_file}:")
    utils.check_schema(steering_file,'steering_file.json')
    print("All ok!")
hepdata_maker.add_command(create_submission)
hepdata_maker.add_command(check_schema)

