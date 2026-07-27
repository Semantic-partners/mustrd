"""mustrd — Spec-By-Example for RDF and SPARQL."""
import logging

# The library posture on logging: emit records, configure nothing. The
# NullHandler keeps Python's last-resort handler quiet for an application that
# has not configured logging, without deciding anything on its behalf.
# `mustrd.logger_setup.configure()` is how an entry point opts in.
logging.getLogger(__name__).addHandler(logging.NullHandler())
