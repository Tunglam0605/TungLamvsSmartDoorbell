# face_db.py
import os
import json
import numpy as np
import threading
from config import *

class FaceDB:
    """
    JSON-backed DB storing list of {"id":"001","name":"Alice","embedding":[...]}
    """
    def __init__(self, path=DB_PATH):
        self.path = path
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.lock = threading.RLock()
        self.data = []
        self.load()

    def load(self):
        with self.lock:
            if os.path.exists(self.path):
                try:
                    with open(self.path, "r") as f:
                        self.data = json.load(f)
                except Exception:
                    self.data = []
            else:
                self.data = []

    def save(self):
        with self.lock:
            try:
                with open(self.path, "w") as f:
                    json.dump(self.data, f, indent=2)
            except Exception as e:
                print("[FaceDB] save failed:", e)

    def generate_new_id(self):
        with self.lock:
            if not self.data:
                return "001"
            ids = [int(p["id"]) for p in self.data if p.get("id") and str(p["id"]).isdigit()]
            return f"{max(ids)+1:03d}"

    def add_person(self, name, embedding):
        with self.lock:
            pid = self.generate_new_id()
            entry = {"id": pid, "name": name, "embedding": embedding.tolist()}
            self.data.append(entry)
            self.save()
            return pid

    def get_all_embeddings(self):
        """
        Trả về dict: id -> (name, np.array(embedding))
        """
        with self.lock:
            out = {}
            for p in self.data:
                try:
                    emb = np.array(p["embedding"], dtype=np.float32)
                    out[p["id"]] = (p["name"], emb)
                except Exception:
                    continue
            return out

    def list_people(self):
        with self.lock:
            return list(self.data)

    def delete_person(self, person_id):
        with self.lock:
            before = len(self.data)
            self.data = [p for p in self.data if str(p.get('id')) != str(person_id)]
            if len(self.data) == before:
                return False
            self.save()
            return True

    def update_person(self, person_id, name=None, embedding=None):
        with self.lock:
            for p in self.data:
                if str(p.get("id")) != str(person_id):
                    continue
                if name is not None:
                    p["name"] = name
                if embedding is not None:
                    try:
                        emb = embedding.tolist()
                    except Exception:
                        emb = list(embedding)
                    p["embedding"] = emb
                self.save()
                return True
            return False
