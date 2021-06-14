import click
from Submission import Submission

@click.command()
@click.argument('steering_script',type=click.Path(exists=True))

def main(steering_script):
    print(f"Creating submission file based on {steering_script}:")
    submission=Submission()
    submission.load_table_config(steering_script)
    submission.implement_table_config()
    submission.create_hepdata_record()
    print("Submission created in test_submission")


    


if __name__ == "__main__":
    main()
