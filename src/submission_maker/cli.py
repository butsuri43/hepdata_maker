import click
from .Submission import Submission
from . import utils 

@click.group(context_settings=dict(help_option_names=['-h', '--help']))
def submission_maker():
    """Top-level CLI entrypoint."""


@click.command()
@click.argument('steering_file',type=click.Path(exists=True))
def create_submission(steering_file):
    print(f"Creating submission file based on {steering_file}:")
    submission=Submission()
    submission.load_table_config(steering_file)
    submission.implement_table_config()
    submission.create_hepdata_record()
    print("Submission created in test_submission")

@click.command()
@click.argument('steering_file',type=click.Path(exists=True))
def check_schema(steering_file):
    print(f"Checking schema of {steering_file}:")
    utils.check_schema(steering_file,'steering_file.json')
    print("All ok!")
submission_maker.add_command(create_submission)
submission_maker.add_command(check_schema)

