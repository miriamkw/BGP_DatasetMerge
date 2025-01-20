# BGP_DatasetMerge
Processing and merging several big datasets into a standardized format for blood glucose prediction (BGP) purposes. 


## Getting Started

Create and activate a virtual environment, and install required dependencies with the commands:
```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```



## Process Data

Create a folder named `unprocessed_data`, and place your acquired datasets in there. Open the file `process_data.py`,
go to the bottom of the file, and comment out the lines for parsing datasets that you are not going to process.

Then, run:
```
python process_data.py
```

Add derived features like insulin on board or insulin counteraction effects using the CLI commands in `add_derived_features.py` (temporarily only available on Mac).


## To do
- Add a user data file, with information about each subjects insulin type
- Use the specific insulin type in computing derived features like ICE and IOB





