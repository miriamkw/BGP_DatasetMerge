#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess
import shutil
import os

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

    for filename in os.listdir(source_folder):
        source_file = os.path.join(source_folder, filename)
        destination_file = os.path.join(destination_folder, filename)
        shutil.move(source_file, destination_file)

    shutil.rmtree('data')


def main():
    setup_directories()

    # COMMENT OUT DATASET HERE IF YOU DON'T WANT TO PROCESS IT
    parse_dataset("ohio_t1dm", UNPROCESSED_DATA_PATH)

    reorganize_results()


if __name__ == "__main__":
    main()
