
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from apps.root import check_parameters
from apps.parameters import Parameters

def test_crash():
    # Simulate the request parameters that failed
    params = Parameters().todict()
    params["network"] = "HL" # Alias 'net' -> 'network' handled before this?
    # root.py checks_get() calls Parameters().todict() then check_request(params).
    # check_request populates params from request.args.
    
    # We simulate the populated params dict:
    params["network"] = "HL"
    params["start"] = "2024-01-01T00:00:00"
    params["end"] = "2024-01-01T00:10:00"
    params["limit"] = "10" # Comes as string from query string!
    
    # Also add defaults that might be relevant
    params["quality"] = "*"
    params["base_url"] = "http://localhost:9001/query"

    print("Running check_parameters with params:", params)
    
    try:
        # This is where we expect the crash
        result = check_parameters(params)
        print("Result:", result)
        
        # Check if 500
        if result[1]['code'] == 500:
            print("Crashed as expected:", result[1]['details'])
            
    except Exception as e:
        print("Crashed with unhandled exception:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_crash()
