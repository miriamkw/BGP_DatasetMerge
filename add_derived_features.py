import numpy as np
import datetime
import pandas as pd
import os
from loop_to_python_api.api import get_glucose_velocity_values_and_dates, get_active_insulin
import click

# TODO: ADD INSULIN TYPES FOR CORRECT COMPUTATION! Currently assuming rapid-acting insulin
def get_json_loop_prediction_input_from_df(data, basal=None, isf=None, cr=None):
    def get_dates_and_values(column, data):
        mask = ~data[column].isna()  # ~ inverts the boolean mask
        dates = data.index[mask].to_list()
        values = data[column][mask].to_list()
        return dates, values

    data.sort_index(inplace=True)
    bolus_dates, bolus_values = get_dates_and_values('bolus', data)
    basal_dates, basal_values = get_dates_and_values('basal', data)

    insulin_json_list = []
    for date, value in zip(bolus_dates, bolus_values):
        entry = {
            "startDate": date.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "endDate": (date + datetime.timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "type": 'bolus',
            "volume": value
        }
        insulin_json_list.append(entry)

    for date, value in zip(basal_dates, basal_values):
        entry = {
            "startDate": date.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "endDate": (date + datetime.timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%SZ'),
            "type": 'basal',
            "volume": value / 12 # Converting from U/hr to delivered units in 5 minutes
        }
        insulin_json_list.append(entry)
    insulin_json_list.sort(key=lambda x: x['startDate'])

    bg_dates, bg_values = get_dates_and_values('CGM', data)
    bg_json_list = []
    for date, value in zip(bg_dates, bg_values):
        entry = {
            "date": date.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "value": value
        }
        bg_json_list.append(entry)
    bg_json_list.sort(key=lambda x: x['date'])

    carbs_dates, carbs_values = get_dates_and_values('carbs', data)
    carbs_json_list = []
    for date, value in zip(carbs_dates, carbs_values):
        entry = {
            "date": date.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "grams": value,
            "absorptionTime": 10800,
        }
        carbs_json_list.append(entry)
    carbs_json_list.sort(key=lambda x: x['date'])

    # It is important that the setting dates encompass the data to avoid a code crash
    if len(bg_json_list) > 0:
        start_date_settings = datetime.datetime.fromisoformat(bg_json_list[0]['date'].replace('Z', '+00:00')) - datetime.timedelta(hours=999)
        end_date_settings = datetime.datetime.fromisoformat(bg_json_list[-1]['date'].replace('Z', '+00:00')) + datetime.timedelta(hours=999)

        start_date_str = start_date_settings.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_date_str = end_date_settings.strftime('%Y-%m-%dT%H:%M:%SZ')
    else:
        return None

    basal = [{
        "startDate": start_date_str,
        "endDate": end_date_str,
        "value": basal
    }]

    isf = [{
        "startDate": start_date_str,
        "endDate": end_date_str,
        "value": isf
    }]

    cr = [{
        "startDate": start_date_str,
        "endDate": end_date_str,
        "value": cr
    }]

    json_data = {
        "carbEntries": carbs_json_list,
        "doses": insulin_json_list,
        "glucoseHistory": bg_json_list,
        "basal": basal,
        "carbRatio": cr,
        "sensitivity": isf,

        # These settings are required but do not impact the iob and cob calculation
        "maxBasalRate": 4.1,
        "maxBolus": 9,
        "recommendationInsulinType": "novolog", # TODO: CHANGE WITH INPUT!
        "recommendationType": "automaticBolus",
        "suspendThreshold": 78,
        "target": [
            {
                "endDate": end_date_str,
                "lowerBound": 101,
                "startDate": start_date_str,
                "upperBound": 115
            }
        ],
    }
    return json_data


def get_df_from_file_path(file_path):
    return pd.read_csv(file_path, index_col='date', parse_dates=['date'], low_memory=False)


def get_json_data_with_prediction_date(json_data, prediction_date):
    json_data["predictionStart"] = prediction_date.strftime('%Y-%m-%dT%H:%M:%SZ')
    return json_data


def add_col(df, col):
    user_ids = df['id'].unique()

    for user_id in user_ids:
        user_data = df[df['id'] == user_id].copy()
        user_data.sort_index(inplace=True)

        if col in user_data.columns:
            if user_data[col].notna().sum() > 0:
                print("User", user_id, f"already has {col} values. Skipping...")
                continue

        # Use total daily insulin to calculate therapy settings
        user_data['insulin'] = user_data['bolus'] + (user_data['basal'] / 12)

        # Get therapy setting estimates
        SAMPLES_PER_DAY = 288  # 24 hours * 12 (12 samples per hour for 5-minute intervals)
        # Group data by day
        first_valid_index = user_data['CGM'].first_valid_index()
        daily_data = (
            user_data.loc[first_valid_index:][user_data['is_test'] == False]
            .groupby(pd.Grouper(freq='D'))['insulin']
            .agg(['count', 'sum'])  # Count samples and sum non-NaN values per day
        ).iloc[1:]
        daily_data['scaled_insulin'] = daily_data['sum'] * (SAMPLES_PER_DAY / daily_data['count'])
        daily_data['scaled_insulin'] = daily_data['scaled_insulin'].where(daily_data['count'] > 0, np.nan)

        daily_avg_insulin = daily_data['scaled_insulin'].mean()
        if np.isnan(daily_avg_insulin):
            print(f"Warning: No valid data for user {user_id}, skipping...")
            df = df[df['user_id'] != user_id]
        else:
            print(f"Average daily insulin for user {user_id}: {daily_avg_insulin}")

        basal = daily_avg_insulin * 0.45 / 24  # Basal 45% of TDI
        isf = 1800 / daily_avg_insulin  # ISF 1800 rule
        cr = 500 / daily_avg_insulin  # CR 500 rule
        json_data = get_json_loop_prediction_input_from_df(user_data, basal, isf, cr)
        if json_data is None:
            print(f"No json data found for {user_id}, skipping...")
            continue

        print(f"Json data is ready. Getting {col}...")

        if col == 'ice':
            values, dates = get_glucose_velocity_values_and_dates(json_data)
            # Only proceed if we have data
            if len(values) > 0 and len(dates) > 0:
                values = [value * 60 * 5 for value in values]
                dates = [datetime.datetime.strptime(date, "%Y-%m-%dT%H:%M:%S%z") for date in dates]
                col_df = pd.DataFrame({
                    col: values,
                    'date': dates
                })
                col_df.set_index('date', inplace=True)
                print(f"Number of {col} values:", len(col_df))

                # Convert to UTC if it is not already
                if col_df.index.tz is not None:
                    col_df.index = col_df.index.tz_localize(None)

                # Adding ice values to the user id in the main df
                mask = (df['id'] == user_id)
                df.loc[mask, col] = col_df[col]
            else:
                mask = (df['id'] == user_id)
                df.loc[mask, col] = np.nan
                print(f"No {col} values for user", user_id)

            print("Number of non-NA ICE values:", df[col].notna().sum())
            print("Users with non nan ice values", df[df[col].notna()]['id'].unique())

        elif col == 'iob':
            user_data[col] = user_data.apply(lambda row: get_active_insulin(get_json_data_with_prediction_date(json_data, row.name)), axis=1)

            # Adding ice values to the user id in the main df
            mask = (df['id'] == user_id)
            df.loc[mask, col] = user_data[col]
            print(user_data)

        else:
            ValueError(f"No column named {col}. Must either be iob or ice")



@click.group()
def cli():
    pass


@cli.command()
@click.argument('file_path', type=click.Path(exists=True, dir_okay=False))
def add_ice(file_path):
    df = get_df_from_file_path(file_path)
    df = add_col(df, 'ice')
    df.to_csv(file_path)


@cli.command()
@click.argument('file_path', type=click.Path(exists=True, dir_okay=False))
def add_iob(file_path):
    df = get_df_from_file_path(file_path)
    df = add_col(df, 'iob')
    df.to_csv(file_path)


if __name__ == '__main__':
    cli()

