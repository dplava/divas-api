import os, glob, sys, uvicorn, datetime

DATA_DIR = "../data"
sets = []

for org in os.scandir(DATA_DIR):
    
    if os.path.isdir(org):
        list = os.scandir(os.path.join(DATA_DIR, org))
        
        collections = []
        
        
        for item in list:
            if os.path.isdir(item) and not item.name.startswith("."):
                collections.append(item.name)
                
        if len(collections) > 0:
            for collection in collections:
                sets.append(f"{org.name}:{collection}")
        else:
            sets.append(org.name)        
                
            
                        
                        
print(sets)