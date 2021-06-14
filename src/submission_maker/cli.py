import click
from .Submission import Submission


@click.group(context_settings=dict(help_option_names=['-h', '--help']))
def submission_maker():
    """Top-level CLI entrypoint."""


@click.command()
@click.argument('steering_script',type=click.Path(exists=True))
def create_submission(steering_script):
    print(f"Creating submission file based on {steering_script}:")
    submission=Submission()
    submission.load_table_config(steering_script)
    submission.implement_table_config()
    submission.create_hepdata_record()
    print("Submission created in test_submission")


submission_maker.add_command(create_submission)

