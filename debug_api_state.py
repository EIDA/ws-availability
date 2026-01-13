
import logging
import sys
from datetime import datetime

# Setup basic logging to stdout
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

print("--- DEBUGGING API STATE ---")

try:
    from apps.settings import settings
    from apps.redis_client import RedisClient
    from apps.restriction import RestrictionInventory
    from pymongo import MongoClient
except ImportError as e:
    print(f"CRITICAL: Could not import app modules. Are you running this inside the container? {e}")
    sys.exit(1)

# 1. Check MongoDB
print(f"\n[1] Checking MongoDB ({settings.mongodb_host}:{settings.mongodb_port})...")
try:
    client = MongoClient(
        settings.mongodb_host,
        settings.mongodb_port,
        username=settings.mongodb_usr,
        password=settings.mongodb_pwd,
        authSource=settings.mongodb_name,
        serverSelectionTimeoutMS=2000
    )
    db = client[settings.mongodb_name]
    count = db.availability.count_documents({"net": "NL", "sta": "BHAR"})
    print(f"    -> Connection: OK")
    print(f"    -> 'availability' documents for NL.BHAR: {count}")
    
    if count > 0:
        doc = db.availability.find_one({"net": "NL", "sta": "BHAR"})
        print(f"    -> Sample TS: {doc.get('ts')} | TE: {doc.get('te')} | LOC: {doc.get('loc')}")
    else:
        print("    -> FAIL: No data in MongoDB! (Did you run the reproduction script?)")

except Exception as e:
    print(f"    -> FAIL: MongoDB Connection Error: {e}")

# 2. Check Redis Inventory
print(f"\n[2] Checking Redis Inventory ({settings.cache_inventory_key} @ {settings.cache_host}:{settings.cache_port})...")
try:
    rc = RedisClient(settings.cache_host, settings.cache_port)
    raw_inv = rc.get(settings.cache_inventory_key)
    
    if not raw_inv:
         print("    -> FAIL: Inventory Key NOT FOUND in Redis.")
    else:
        if isinstance(raw_inv, dict):
            print(f"    -> Inventory Type: Queryable Dictionary (Good)")
            # Check for BHAR
            # Inventory structure: {"NET.STA.LOC.CHA": [Epoch, ...]}
            target_key = "NL.BHAR.HGN.D"
            if target_key in raw_inv:
                print(f"    -> SUCCESS: Found station '{target_key}' in Inventory!")
                epochs = raw_inv[target_key]
                for i, ep in enumerate(epochs):
                    print(f"       Epoch {i}: {ep.start} -> {ep.end} ({ep.restriction})")
            else:
                 print(f"    -> FAIL: Inventory exists but '{target_key}' is MISSING.")
                 print(f"       (First 5 keys: {list(raw_inv.keys())[:5]})")
        else:
            print(f"    -> FAIL: Inventory Type is {type(raw_inv)}, expected dict! (Did you use the OLD script?)")

except Exception as e:
    print(f"    -> FAIL: Redis Error: {e}")

# 3. Simulate Restriction Logic
print(f"\n[3] Simulating Restriction Logic...")
try:
    # Mimic wfcatalog_client logic
    ri = RestrictionInventory(settings.cache_host, settings.cache_port, settings.cache_inventory_key)
    if not ri.is_populated:
        print("    -> FAIL: RestrictionInventory failed to load data from Redis.")
    else:
        # Check explicit access
        # NL.BHAR.HGN.D at 2020-06-05
        test_date = datetime(2020, 6, 5).date()
        seed = "NL.BHAR.HGN.D"
        
        # Check _known_seedIDs
        if seed in ri._known_seedIDs:
             print(f"    -> '{seed}' is in _known_seedIDs (Good)")
        else:
             print(f"    -> '{seed}' is NOT in _known_seedIDs (Bad - API will ignore query)")

        status = ri.is_restricted(seed, test_date, test_date)
        print(f"    -> Restriction Status for {test_date}: {status}")

except Exception as e:
    print(f"    -> FAIL: Logic Simulation Error: {e}")

print("\n--- END DEBUG ---")
