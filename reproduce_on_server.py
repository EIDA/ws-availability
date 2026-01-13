
from pymongo import MongoClient
from datetime import datetime, timedelta

def insert_repro_data():
    # Connect to MongoDB (Adjust host/port if needed, e.g. localhost:27017)
    client = MongoClient("mongodb://localhost:27017/")
    db = client["wfrepo"]
    
    # Collection: availability (Materialized View collection)
    coll = db["availability"]
    
    # 200 Hz = 0.005s sample rate
    srate = 200.0
    
    # Original problematic timestamps
    # Row 1 ends at .005
    # Row 2 starts at .000 (Overlap!)
    t0 = datetime(2020, 6, 5, 0, 0, 0)
    t_mid = datetime(2020, 6, 5, 17, 26, 59)
    
    t_end1 = t_mid + timedelta(microseconds=5000) # ...59.005
    t_start2 = t_mid # ...59.000
    t_end2 = datetime(2020, 6, 7, 0, 2, 0)
    
    creation_time = datetime.utcnow()
    
    # Data Records
    # Network: NL, Station: BHAR, Location: HGN, Channel: D
    # Note: In your output 'HGN' was listed under Location, 'D' under Channel.
    # Adjust 'net', 'sta', 'loc', 'cha' to match your query: net=NL&sta=BHAR&cha=HGN
    # Wait, if cha=HGN, then HGN should be in 'cha' field?
    # Your curl: net=NL&sta=BHAR&cha=HGN
    # Your output: Location=HGN, Channel=D. 
    # This implies the query param 'cha' matched the 'loc' field?? Or 'HGN' is a channel?
    # Let's insert exactly what matches "NL.BHAR..HGN" (assuming empty loc, HGN channel) or "NL.BHAR.HGN.D"?
    # Based on output: Location=HGN, Channel=D.
    # So loc="HGN", cha="D".
    
    rec1 = {
        "net": "NL", "sta": "BHAR", "loc": "HGN", "cha": "D",
        "qlt": "D", "srate": srate,
        "ts": t0, "te": t_end1,
        "created": creation_time, "count": 1, "restr": "OPEN"
    }
    
    rec2 = {
        "net": "NL", "sta": "BHAR", "loc": "HGN", "cha": "D",
        "qlt": "D", "srate": srate,
        "ts": t_start2, "te": t_end2,
        "created": creation_time, "count": 1, "restr": "OPEN"
    }

    print(f"Inserting 2 overlapping records for NL.BHAR.HGN.D...")
    result = coll.insert_many([rec1, rec2])
    print(f"Inserted IDs: {result.inserted_ids}")
    print("Done. Now run the curl command/browser check.")

if __name__ == "__main__":
    insert_repro_data()
