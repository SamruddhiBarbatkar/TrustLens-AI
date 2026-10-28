"""MongoDB persistence for the existing TrustLens API models.

The API still uses its mapped model objects, but this session stores their
scalar fields as MongoDB documents. Relationships are assembled from indexed
foreign keys when a claim or verification run is read.
"""

from datetime import date, datetime, timezone
from functools import lru_cache

from pymongo import ASCENDING, MongoClient, ReturnDocument
from pymongo.errors import OperationFailure
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.sql.elements import BinaryExpression, BindParameter, UnaryExpression
from sqlalchemy.sql import operators

from app.core.config import settings


@lru_cache(maxsize=1)
def mongo_client():
    return MongoClient(
        settings.mongodb_uri,
        tz_aware=True,
        serverSelectionTimeoutMS=5000,
    )


def mongo_database():
    return mongo_client()[settings.mongodb_database]


def initialize_mongodb():
    """Fail startup clearly if MongoDB is unavailable and create lookup indexes."""
    client = mongo_client()
    client.admin.command("ping")
    db = client[settings.mongodb_database]
    db.users.create_index("email", unique=True)
    db.claims.create_index("claim_number", unique=True)
    db.claims.create_index("owner_id")
    # Legacy SQL records can contain multiple images of the same type. The API
    # controls new uploads; keep the index non-unique to preserve old evidence.
    db.evidence.create_index([("claim_id", ASCENDING), ("evidence_type", ASCENDING)])
    db.verification_runs.create_index("claim_id")
    db.analysis_results.create_index([("verification_run_id", ASCENDING), ("evidence_id", ASCENDING)])
    db.review_decisions.create_index("claim_id")


def _models():
    from app.db.models import AnalysisResult, Claim, Evidence, ReviewDecision, User, VerificationRun

    return User, Claim, Evidence, VerificationRun, AnalysisResult, ReviewDecision


def _collection_name(model):
    return model.__tablename__


def _encode(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    return value


def _decode(column, value):
    if value is not None and column.type.python_type is date and isinstance(value, str):
        return date.fromisoformat(value)
    return value


def _fields(obj):
    return {
        column.key: _encode(getattr(obj, column.key))
        for column in obj.__table__.columns
    }


class MongoQuery:
    def __init__(self, session, model):
        self.session = session
        self.model = model
        self.filters = {}
        self.sort_field = None
        self.sort_direction = ASCENDING

    def filter(self, *conditions):
        for condition in conditions:
            if not isinstance(condition, BinaryExpression) or condition.operator != operators.eq:
                raise ValueError("MongoDB queries support equality filters only.")
            if not isinstance(condition.right, BindParameter):
                raise ValueError("MongoDB queries need a literal filter value.")
            self.filters[condition.left.key] = condition.right.value
        return self

    def order_by(self, expression):
        if isinstance(expression, UnaryExpression) and expression.modifier == operators.desc_op:
            self.sort_field = expression.element.key
            self.sort_direction = -1
        else:
            self.sort_field = expression.key
            self.sort_direction = ASCENDING
        return self

    def all(self):
        results = self.session.find(self.model, self.filters)
        if self.sort_field:
            results.sort(
                key=lambda item: getattr(item, self.sort_field) or 0,
                reverse=self.sort_direction == -1,
            )
        return results

    def first(self):
        results = self.all()
        return results[0] if results else None


class MongoSession:
    def __init__(self, database):
        self.database = database
        self.identity = {}
        self.snapshots = {}
        self.new = set()
        self.loading = set()

    def query(self, model):
        return MongoQuery(self, model)

    def _key(self, model, identifier):
        return model, int(identifier)

    def _materialize(self, model, document, deep=True):
        key = self._key(model, document["_id"])
        if key not in self.identity:
            values = {
                column.key: _decode(column, document.get(column.key))
                for column in model.__table__.columns
            }
            obj = model(**values)
            self.identity[key] = obj
            self.snapshots[key] = _fields(obj)
        obj = self.identity[key]
        if deep:
            self._hydrate(obj)
        return obj

    def _matching(self, obj, filters):
        return all(getattr(obj, field) == value for field, value in filters.items())

    def _related(self, model, filters):
        collection = self.database[_collection_name(model)]
        documents = list(collection.find(filters))
        found = {
            int(doc["_id"]): self._materialize(model, doc, deep=False)
            for doc in documents
        }
        for (loaded_model, identifier), obj in self.identity.items():
            if loaded_model is model:
                if self._matching(obj, filters):
                    found[identifier] = obj
                else:
                    found.pop(identifier, None)
        return list(found.values())

    def find(self, model, filters):
        results = self._related(model, filters)
        for obj in results:
            self._hydrate(obj)
        return results

    def _first_related(self, model, filters):
        values = self._related(model, filters)
        return values[0] if values else None

    def _hydrate(self, obj):
        User, Claim, Evidence, VerificationRun, AnalysisResult, ReviewDecision = _models()
        key = self._key(type(obj), obj.id)
        if key in self.loading:
            return
        if isinstance(obj, Claim):
            self.loading.add(key)
            try:
                owner = self.get(User, obj.owner_id, deep=False) if obj.owner_id else None
                set_committed_value(obj, "owner", owner)
                evidence = self._related(Evidence, {"claim_id": obj.id})
                for item in evidence:
                    set_committed_value(item, "claim", obj)
                set_committed_value(obj, "evidence", evidence)
                runs = self._related(VerificationRun, {"claim_id": obj.id})
                for run in runs:
                    self._hydrate_run(run, obj)
                set_committed_value(obj, "verification_runs", runs)
                decisions = self._related(ReviewDecision, {"claim_id": obj.id})
                for decision in decisions:
                    self._hydrate_decision(decision)
                    set_committed_value(decision, "claim", obj)
                set_committed_value(obj, "review_decisions", decisions)
            finally:
                self.loading.remove(key)
        elif isinstance(obj, VerificationRun):
            claim = self.get(Claim, obj.claim_id)
            self._hydrate_run(obj, claim)
        elif isinstance(obj, ReviewDecision):
            self._hydrate_decision(obj)

    def _hydrate_run(self, run, claim):
        _, _, _, _, AnalysisResult, ReviewDecision = _models()
        set_committed_value(run, "claim", claim)
        analyses = self._related(AnalysisResult, {"verification_run_id": run.id})
        set_committed_value(run, "analysis_results", analyses)
        decisions = self._related(ReviewDecision, {"verification_run_id": run.id})
        set_committed_value(run, "review_decisions", decisions)

    def _hydrate_decision(self, decision):
        User = _models()[0]
        reviewer = self.get(User, decision.reviewer_id, deep=False)
        set_committed_value(decision, "reviewer", reviewer)

    def get(self, model, identifier, deep=True):
        if identifier is None:
            return None
        key = self._key(model, identifier)
        if key in self.identity:
            obj = self.identity[key]
            if deep:
                self._hydrate(obj)
            return obj
        document = self.database[_collection_name(model)].find_one({"_id": int(identifier)})
        return self._materialize(model, document, deep) if document else None

    def add(self, obj):
        model = type(obj)
        if obj.id is None:
            counter = self.database.counters.find_one_and_update(
                {"_id": _collection_name(model)},
                {"$inc": {"value": 1}},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            obj.id = counter["value"]
            for column in obj.__table__.columns:
                if column.key == "created_at" and getattr(obj, column.key) is None:
                    setattr(obj, column.key, datetime.now(timezone.utc))
                elif getattr(obj, column.key) is None and column.default is not None:
                    setattr(obj, column.key, column.default.arg)
            key = self._key(model, obj.id)
            self.new.add(key)
            self.identity[key] = obj
        else:
            self.identity.setdefault(self._key(model, obj.id), obj)

    def flush(self):
        # IDs are allocated in add(), so pending analyses are queryable without
        # writing a partial verification run to MongoDB.
        return None

    def commit(self):
        writes = []
        for key, obj in list(self.identity.items()):
            values = _fields(obj)
            if key in self.new:
                writes.append((key, "insert", values))
            else:
                changed = {
                    field: value for field, value in values.items()
                    if self.snapshots[key].get(field) != value
                }
                if changed:
                    writes.append((key, "update", changed))

        def write_all(driver_session=None):
            kwargs = {"session": driver_session} if driver_session is not None else {}
            for key, action, values in writes:
                collection = self.database[_collection_name(key[0])]
                if action == "insert":
                    collection.insert_one({"_id": key[1], **values}, **kwargs)
                else:
                    collection.update_one({"_id": key[1]}, {"$set": values}, **kwargs)

        if writes:
            try:
                driver_session = self.database.client.start_session()
            except NotImplementedError:
                # In-memory MongoDB test doubles do not implement sessions.
                write_all()
            else:
                try:
                    with driver_session:
                        with driver_session.start_transaction():
                            write_all(driver_session)
                except OperationFailure as error:
                    if error.code != 20:
                        raise
                    # A local standalone server cannot run transactions.
                    write_all()

        for key, obj in self.identity.items():
            values = _fields(obj)
            self.snapshots[key] = values
        self.new.clear()

    def refresh(self, obj):
        # IDs and defaults are assigned locally; populate relationships such
        # as the reviewer needed by the immediate review response.
        self._hydrate(obj)

    def rollback(self):
        # No document is written by flush(); discard pending objects and reload
        # committed objects on the next query.
        self.identity.clear()
        self.snapshots.clear()
        self.new.clear()
        self.loading.clear()

    def close(self):
        self.rollback()


def mongo_session_factory():
    return MongoSession(mongo_database())
