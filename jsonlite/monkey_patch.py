import sys
import os
import pathlib
import types
import jsonlite


class MongoClientAdapter:
    def __init__(self, uri, *args, **kwargs):
        if uri.startswith('jsonlite://'):
            self.database_path = pathlib.Path(uri[11:])
            self.database_path.mkdir(parents=True, exist_ok=True)
        else:
            raise ValueError("Unsupported URI scheme for MongoClientAdapter")

    def __getitem__(self, name):
        return DatabaseAdapter(self.database_path / name)

    def __getattr__(self, name):
        return self.__getitem__(name)


class DatabaseAdapter:
    def __init__(self, db_path):
        self.db_path = db_path
        self.db_path.mkdir(parents=True, exist_ok=True)

    def __getitem__(self, name):
        return CollectionAdapter(self.db_path / f"{name}.json")

    def __getattr__(self, name):
        return self.__getitem__(name)


class CollectionAdapter:
    def __init__(self, collection_path):
        self.collection = jsonlite.JSONlite(collection_path)

    def insert_one(self, document):
        return self.collection.insert_one(document)

    def insert_many(self, documents):
        return self.collection.insert_many(documents)

    def find_one(self, *args, **kwargs):
        return self.collection.find_one(*args, **kwargs)

    def find(self, *args, **kwargs):
        return self.collection.find(*args, **kwargs)

    def update_one(self, filter, update, *args, **kwargs):
        return self.collection.update_one(filter, update, *args, **kwargs)

    def update_many(self, filter, update, *args, **kwargs):
        return self.collection.update_many(filter, update, *args, **kwargs)

    def delete_one(self, filter):
        return self.collection.delete_one(filter)

    def delete_many(self, filter):
        return self.collection.delete_many(filter)

    def drop(self):
        if self.collection._filename.is_file():
            self.collection._filename.unlink()
        print(f"Collection {self.collection._filename} dropped")


def pymongo_patch():
    import importlib.machinery
    import sys
    import types

    class PymongoFinder:
        def find_spec(self, fullname, path, target=None):
            if fullname == "pymongo":
                return self.create_spec(fullname)
            return None

        def create_spec(self, name):
            loader = PymongoLoader()
            return importlib.machinery.ModuleSpec(name, loader)

    class PymongoLoader:
        def create_module(self, spec):
            module = types.ModuleType(spec.name)
            module.MongoClient = MongoClientAdapter
            return module

        def exec_module(self, module):
            pass

    sys.meta_path.insert(0, PymongoFinder())
