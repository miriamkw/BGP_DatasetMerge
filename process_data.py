#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess
import shutil
import os
import pandas as pd
import numpy as np
from smoother.smooth_SMBG_data import smooth_smbg_data

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


def impute_datasets():
    source_folder = 'processed_data'
    for filename in os.listdir(source_folder):
        # TODO: Remove some of them!
        # TODO: also split into test / train!
        if 'imputed' not in filename and '.DS_Store' not in filename and 'T1DEXI' not in filename and 'Ohio' not in filename:
            df = pd.read_csv(os.path.join(source_folder, filename), index_col='date', parse_dates=['date'],
                             low_memory=False)
            print(f"Processing {filename} with imputation...")
            all_processed_dfs = []  # List to store processed dataframes

            for subject_id, subset_df in df.groupby('id'):  # Group by the 'id' column
                for is_test in [True, False]:
                    subset_split_df = subset_df[subset_df['is_test'] == is_test]
                    forward_fill_cols = ['galvanic_skin_response', 'skin_temp', 'air_temp', 'heartrate']
                    for col in [col for col in forward_fill_cols if col in df.columns]:
                        # First, set 0 to nan
                        subset_split_df[col] = subset_split_df[col].replace(0, np.nan)
                        # Then, forward fill with upper limit
                        upper_limit = 12
                        subset_split_df[col] = subset_split_df[col].fillna(method='ffill', limit=upper_limit)

                    fill_nan_with_zero_cols = ['carbs', 'bolus', 'basal', 'steps', 'acceleration']
                    for col in [col for col in fill_nan_with_zero_cols if col in subset_split_df.columns]:
                        # First, set 0 to nan
                        subset_split_df[col] = subset_split_df[col].replace(0, np.nan)
                        # Replace NaN values with 0 if they were filled within the limit
                        mask = subset_split_df[col].isna()  # Identify NaN values
                        subset_split_df[col] = subset_split_df[col].fillna(0)
                        # Retain NaN for stretches that exceed the limit
                        upper_limit = 12*24
                        subset_split_df[col] = subset_split_df[col].where(~mask | (mask & mask.shift(upper_limit, fill_value=False)), np.nan)

                    # Smoothen Cgm data
                    subset_split_df = smoothen_cgm_data(subset_split_df)
                    all_processed_dfs.append(subset_split_df)

            df_processed = pd.concat(all_processed_dfs)
            save_file_name = filename.split('.')[0] + '_imputed.' + filename.split('.')[1]
            save_path = os.path.join(source_folder, save_file_name)
            df_processed.to_csv(save_path)
            print(f"Processed file saved as: {save_path}")


def smoothen_cgm_data(df):
    glucose_values = np.array(df['CGM'].values)
    dates = np.array(df.index.values)
    smoother_result = smooth_smbg_data(dates, glucose_values)

    smoothed_df = pd.DataFrame({'y_smoothed': smoother_result['y_smoothed']}, index=smoother_result['t_i'])
    # Convert smoothed_df index to match df's timezone
    if df.index.tz is not None:  # df has a timezone
        if smoothed_df.index.tz is None:  # smoothed_df is naive
            smoothed_df.index = smoothed_df.index.tz_localize(df.index.tz)  # Localize to df's timezone
        else:  # smoothed_df already has a timezone
            smoothed_df.index = smoothed_df.index.tz_convert(df.index.tz)  # Convert to the same timezone as df
    else:  # df.index is naive (no timezone)
        smoothed_df.index = smoothed_df.index.tz_localize(None)  # Make smoothed_df naive

    df['CGM_smoothed'] = smoothed_df['y_smoothed'].reindex(df.index, method='nearest')

    # Add nans to CGM smoothened if CGM is nan for more than two hours
    df = df.copy()  # Explicitly create a new copy to avoid warnings
    window_size = 24
    rolling_nan_count = df['CGM'].isna().rolling(window=window_size, min_periods=1).sum()
    full_nan_indices = rolling_nan_count[rolling_nan_count == window_size].index
    for idx in full_nan_indices:
        window_start = idx - pd.Timedelta(minutes=5 * (window_size - 1))
        window_end = idx
        df.loc[window_start:window_end, 'CGM_smoothed'] = np.nan
    return df


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




def main():
    setup_directories()

    # COMMENT OUT DATASET HERE IF YOU DON'T WANT TO PROCESS IT
    #parse_dataset("ohio_t1dm", UNPROCESSED_DATA_PATH)
    #parse_dataset("tidepool_dataset", UNPROCESSED_DATA_PATH)
    #parse_dataset("t1dexi", UNPROCESSED_DATA_PATH)
    #parse_dataset("open_aps", os.path.join(UNPROCESSED_DATA_PATH, 'OpenAPS Data/'))

    # TODO: Add derived features: ICE, IOB (but regenerate figures first! and send paper to supervisors!)

    reorganize_results()
    impute_datasets()


if __name__ == "__main__":
    main()
