
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
