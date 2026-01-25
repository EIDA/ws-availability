
import sys
import os

# Add current directory to path
print("Starting reproduction script...")
sys.path.append(os.getcwd())

from unittest.mock import MagicMock
sys.modules["apps.wfcatalog_client"] = MagicMock()

from apps.data_access_layer import records_to_text

def test_empty_location_text_format():
    params = {
        "format": "text",
        "merge": [],
        "showlastupdate": False,
        "extent": False
    }

    # Mock data with empty location (3rd element)
    # The data passed to records_to_text is already processed by select_columns, 
    # so it contains only the columns requested and they are strings.
    # Standard header: Network, Station, Location, Channel, Quality, SampleRate, Earliest, Latest
    
    # Let's assume select_columns produced this:
    data = [
        ["IU", "ANMO", "", "BHZ", "M", "20.0", "1989-08-29T22:07:20.482000Z", "1998-10-26T17:38:43.640000Z"]
    ]

    output = records_to_text(params, data)
    print("Output:")
    print(output)

    lines = output.strip().split('\n')
    # Header is line 0
    # Data is line 1
    data_line = lines[1]
    parts = data_line.split()
    
    # IU ANMO "" BHZ ... 
    # If empty string is printed, it might be just spaces depending on padding.
    # But usually it's empty.
    
    # We expect "--" for location.
    
    if "--" in parts:
        print("SUCCESS: Location represented as '--'")
    else:
        print("FAILURE: Location NOT represented as '--'")

if __name__ == "__main__":
    test_empty_location_text_format()
