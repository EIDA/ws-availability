
from pymongo import MongoClient
from datetime import datetime
from apps.settings import settings

def reproduce():
    # Connect using valid settings from the environment
    client = MongoClient(
        settings.mongodb_host,
        settings.mongodb_port,
        username=settings.mongodb_usr,
        password=settings.mongodb_pwd,
        authSource=settings.mongodb_name,
    )
    db = client[settings.mongodb_name]
    
    # 1. Insert Daily Stream (avail < 100)
    stream_doc = {
        "net": "NL", "sta": "BHAR", "loc": "HGN", "cha": "D",
        "qlt": "D", "avail": 50.0,
        "srate": [200.0],
        "ts": datetime(2020, 6, 5),
        "te": datetime(2020, 6, 6),
        "created": datetime.utcnow()
    }
    res = db.daily_streams.insert_one(stream_doc)
    stream_id = res.inserted_id
    print(f"Inserted daily_stream: {stream_id}")
    
    # 2. Insert Overlapping c_segments
    # Row 1 End: ...59.005, Row 2 Start: ...59.000
    seg1 = {
        "streamId": stream_id,
        "srate": 200.0,
        "ts": datetime(2020, 6, 5, 0, 0, 0),
        "te": datetime(2020, 6, 5, 17, 26, 59, 5000),
        "num_samples": 1000
    }
    seg2 = {
        "streamId": stream_id,
        "srate": 200.0,
        "ts": datetime(2020, 6, 5, 17, 26, 59, 0),
        "te": datetime(2020, 6, 5, 17, 32, 9, 5000),
        "num_samples": 1000
    }
    db.c_segments.insert_many([seg1, seg2])
    print("Inserted overlapping c_segments.")

    # 3. Insert into 'availability' collection (Simulating main.js aggregation)
    # The API queries 'availability', not 'daily_streams' directly.
    # main.js usually populates this. We will do it manually to ensure data exists.
    
    avail_doc1 = {
        "_id": seg1["_id"], # Same ID as c_segment
        "net": stream_doc["net"],
        "sta": stream_doc["sta"],
        "loc": stream_doc["loc"],
        "cha": stream_doc["cha"],
        "qlt": stream_doc["qlt"],
        "srate": [seg1["srate"]] if isinstance(seg1["srate"], float) else seg1["srate"], # main.js creates array? No, main.js takes first $srate. Wait, main.js says: srate: { $first: "$c_segments.srate" }. In my seg1 it is float. In availability schema it might be float or list? API expects what?
        # API models.py doesn't strictly validate srate type in response, but typical usage is float.
        # main.js: srate: { $first: "$c_segments.srate" } -> float. 
        # But wait, updateAvailabilityDaily does: srate: { $first: { $arrayElemAt: ["$srate", 0] } } which implies daily_streams has list.
        # daily_streams has list [200.0]. c_segments has float 200.0.
        # So continuous view has float.
        "srate": 200.0,
        "ts": seg1["ts"],
        "te": seg1["te"],
        "created": stream_doc["created"],
        "restr": "OPEN",
        "count": 1
    }
    
    avail_doc2 = {
        "_id": seg2["_id"],
        "net": stream_doc["net"],
        "sta": stream_doc["sta"],
        "loc": stream_doc["loc"],
        "cha": stream_doc["cha"],
        "qlt": stream_doc["qlt"],
        "srate": 200.0,
        "ts": seg2["ts"],
        "te": seg2["te"],
        "created": stream_doc["created"],
        "restr": "OPEN",
        "count": 1
    }

    # Use replace_one to allow re-running without duplicate key error
    db.availability.replace_one({"_id": avail_doc1["_id"]}, avail_doc1, upsert=True)
    db.availability.replace_one({"_id": avail_doc2["_id"]}, avail_doc2, upsert=True)
    print("Inserted/Updated 'availability' collection (Manual Aggregation).")

    # 3. Insert into Redis Inventory (Required for API to recognize the station)
    # 3. Insert into Redis Inventory (Required for API to recognize the station)
    from apps.redis_client import RedisClient
    from apps.restriction import Epoch, Restriction
    from datetime import date
    
    print(f"Injecting {settings.cache_inventory_key} into Redis...")
    rc = RedisClient(settings.cache_host, settings.cache_port)
    
    # Retrieve existing inventory (if any) using RedisClient (which handles unpickling)
    # Note: RedisClient.get returns the unpickled object (Dict) or None
    inv = rc.get(settings.cache_inventory_key)
    if not inv or not isinstance(inv, dict):
        print("Inventory empty or invalid, initializing new Dict.")
        inv = {}
        
    test_seed = "NL.BHAR.HGN.D"
    if test_seed not in inv:
        # Create a fake OPEN epoch for this station
        # Epoch(net, sta, loc, cha, start, end)
        ep = Epoch("NL", "BHAR", "HGN", "D", date(2000, 1, 1), date(2030, 1, 1))
        ep.restriction = Restriction.OPEN
        
        inv[test_seed] = [ep]
        
        # Save back to Redis (RedisClient handles pickling)
        rc.set(settings.cache_inventory_key, inv)
        print(f"Added {test_seed} to Redis inventory (as Epoch object).")
    else:
        print(f"{test_seed} already in Redis inventory.")

if __name__ == "__main__":
    reproduce()
