"""Test Mongo client deployment options."""

import certifi

from app import db


def run():
    assert db._client_kwargs("mongodb://localhost:27017") == {}
    print("  local uri       -> no TLS override")

    atlas_kwargs = db._client_kwargs(
        "mongodb+srv://user:pass@cluster.fh1ttjy.mongodb.net/?retryWrites=true"
    )
    assert atlas_kwargs == {"tls": True, "tlsCAFile": certifi.where()}
    print("  atlas srv uri   -> certifi TLS")

    atlas_direct_kwargs = db._client_kwargs(
        "mongodb://user:pass@ac-22jo3hb-shard-00-00.fh1ttjy.mongodb.net:27017/"
    )
    assert atlas_direct_kwargs == {"tls": True, "tlsCAFile": certifi.where()}
    print("  atlas host uri  -> certifi TLS")


run()
print("\nALL DB CONFIG CHECKS PASSED")
