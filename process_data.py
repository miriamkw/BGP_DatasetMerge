#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess
import shutil
import os
import pandas as pd

UNPROCESSED_DATA_PATH = 'unprocessed_data'


def run_glupredkit_command(command):
    result = subprocess.run(command, capture_output=True, text=True)
    print(result.stdout)

    if result.stderr:
        print("Errors:")
        print(result.stderr)


def setup_directories():
    run_glupredkit_command(["glupredkit", "setup_directories"])


def parse_dataset(parser, file_path, test_size='0.3'):
    run_glupredkit_command(["glupredkit", "parse", "--parser", parser, "--file-path", file_path,
                            "--test-size", test_size])


def reorganize_results():
    source_folder = os.path.join('data', 'raw')
    destination_folder = 'processed_data'
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)

    # Move results from data subfolder to a folder named "processed_data"
    for filename in os.listdir(source_folder):
        source_file = os.path.join(source_folder, filename)
        destination_file = os.path.join(destination_folder, filename)
        shutil.move(source_file, destination_file)

    shutil.rmtree('data')

    # Split files into a folder where each subject has its own file
    for filename in os.listdir(destination_folder):
        if ".csv" in filename:
            filename_without_end = filename.split(".")[0]
            new_folder_train = os.path.join(destination_folder, filename_without_end, 'train')
            new_folder_test = os.path.join(destination_folder, filename_without_end, 'test')

            # Create a folder with the name of the file
            if not os.path.exists(new_folder_train):
                os.makedirs(new_folder_train)
                os.makedirs(new_folder_test)

            # Open the df, split into each subject and train / test
            data_path = os.path.join(destination_folder, filename)
            df = pd.read_csv(data_path, low_memory=False)
            subject_ids = df['id'].unique()
            for subject_id in subject_ids:
                subset_df = df[df['id'] == subject_id]

                train_df = subset_df[~subset_df['is_test']]
                test_df = subset_df[subset_df['is_test']]

                subject_data_train_path = os.path.join(new_folder_train, str(subject_id) + '.csv')
                subject_data_test_path = os.path.join(new_folder_test, str(subject_id) + '.csv')

                drop_cols = ['id', 'is_test']
                train_df.drop(columns=drop_cols).to_csv(subject_data_train_path, index=False)
                test_df.drop(columns=drop_cols).to_csv(subject_data_test_path, index=False)

            # Delete original file
            os.remove(data_path)


def main():
    setup_directories()

    # COMMENT OUT DATASET HERE IF YOU DON'T WANT TO PROCESS IT
    #parse_dataset("ohio_t1dm", UNPROCESSED_DATA_PATH)
    #parse_dataset("tidepool_dataset", UNPROCESSED_DATA_PATH)
    #parse_dataset("t1dexi", UNPROCESSED_DATA_PATH)
    parse_dataset("open_aps", os.path.join(UNPROCESSED_DATA_PATH, 'OpenAPS Data/'))

    reorganize_results()


if __name__ == "__main__":
    main()
