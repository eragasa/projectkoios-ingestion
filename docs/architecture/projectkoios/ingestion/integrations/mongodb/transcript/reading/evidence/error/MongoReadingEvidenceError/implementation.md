# `MongoReadingEvidenceError` implementation

Typed provider exception retains one stable error code and bounded human message while chaining the original PyMongo/BSON failure internally. Vendor exception objects never cross the adapter boundary.
