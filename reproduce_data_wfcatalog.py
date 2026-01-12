
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

if __name__ == "__main__":
    reproduce()
