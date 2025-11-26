import pymongo
from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017" # Aumentando os timeouts
DB_NAME = "bigdata_dengue_rj"

print("test")

def get_mongo_collection(collection_name):
    """Conecta ao MongoDB e retorna a coleção desejada."""
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME][collection_name]
        print(f"Conectado ao MongoDB: {DB_NAME}")

        places = []
        for doc in db.find({}, {"_id": 0, "municipio": 1}):
            place = doc.get("municipio")
            if place in places:
                continue
            else:
                places.append(place)
        for place in places:
            print(place)
    except Exception as e:
        print(f"Erro ao conectar ao MongoDB: {e}")
        return None

get_mongo_collection("precipitacao_chuva")

import matplotlib.pyplot as plt

plt.plot([1, 2, 3], [1, 4, 9])
plt.show()
