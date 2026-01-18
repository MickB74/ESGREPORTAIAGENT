
import os
import certifi
from pymongo import MongoClient
import toml

def get_mongo_uri():
    try:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        secrets_path = os.path.join(base, ".streamlit", "secrets.toml")
        print(f"Checking secrets at: {secrets_path}")
        
        if os.path.exists(secrets_path):
            data = toml.load(secrets_path)
            if "MONGO_URI" in data:
                return data["MONGO_URI"]
            if "mongo" in data:
                return data["mongo"]["uri"]
    except Exception as e:
        print(f"Error: {e}")
    return os.environ.get("MONGO_URI")

uri = get_mongo_uri()
if not uri:
    print("No URI")
    exit()

client = MongoClient(uri, tlsCAFile=certifi.where(), tlsAllowInvalidCertificates=True)
db = client.esg_agent
coll = db.sbti_companies

# Get one doc
doc = coll.find_one({}, {"_id": 0})
if doc:
    print("Keys found:")
    for k in doc.keys():
        print(f"- {k}")
    print("\nSample Data:")
    print(doc)
else:
    print("No documents found yet.")
