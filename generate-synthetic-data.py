import random
import string
from pymongo import MongoClient, errors

# Configuration
mongo_uri = '' #redacted
database_name = 'DeviceDatabase'
collection_name = 'devices'

# Initialize MongoDB client
mongo_client = MongoClient(mongo_uri)
database = mongo_client[database_name]
device_collection = database[collection_name]


# Function to generate random string
def random_string(length=8):
    letters = string.ascii_letters + string.digits
    return ''.join(random.choice(letters) for i in range(length))

# Number of synthetic device records to create
num_devices = 50

# Create synthetic device data
synthetic_devices = []
for _ in range(num_devices):
    device_id = random_string(12)
    device_token = random_string(16)
    attested = random.choice([True, False])
    synthetic_devices.append({
        '_id': device_id,  # Use device_id as the shard key
        'deviceid': device_id,
        'deviceToken': device_token,
        'attested': attested
    })

# Insert synthetic device data into MongoDB
try:
    result = device_collection.insert_many(synthetic_devices, ordered=False)
    print(f'Inserted {len(result.inserted_ids)} synthetic device records into the collection.')
except errors.BulkWriteError as bwe:
    print(bwe.details)
