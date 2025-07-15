# Mustrd Debugging Improvements

This document outlines the improvements made to mustrd to make debugging easier, especially for issues like the "list index out of range" error that was difficult to diagnose.

## 🐛 Original Problem

The test `20-test-vx-purchase-information-record.mustrd.ttl` was failing with an unhelpful error:

```
IndexError: list index out of range
```

This error occurred because the test was referencing a non-existent Anzo query step, but the error message gave no indication of what was wrong.

## ✅ Improvements Implemented

### 1. Better Error Messages for Missing Query Steps

**File**: `mustrd/mustrdAnzo.py`

**Before**:
```python
return json_to_dictlist(query_configuration(anzo_config=triple_store, query=query))[0]['query']
```

**After**: Added comprehensive error checking with helpful messages:
```python
result = json_to_dictlist(query_configuration(anzo_config=triple_store, query=query))

if not result:
    # Check if the step exists at all
    existence_query = f"""ASK WHERE {{ <{query_step_uri}> ?p ?o }}"""
    
    if not step_exists:
        raise ValueError(f"Query step <{query_step_uri}> does not exist in Anzo triplestore. "
                       f"Check if the step URI is correct or consider using must:FileSparqlSource instead. "
                       f"Example: [ a must:FileSparqlSource ; must:fileurl <file://path/to/query.sparql> ; must:queryType must:UpdateSparql ]")
```

### 2. Proactive Test Spec Validation

**File**: `mustrd/mustrd.py`

Added `validate_test_spec()` function that checks for common issues:

- ⚠️ **Warns about AnzoGraphmartStepSparqlSource usage** - suggests alternatives
- ❌ **Validates file paths exist** - catches missing data files early  
- ❌ **Checks required properties** - ensures must:given, must:when, must:then are present
- ⚠️ **Flags relative file paths** - helps with path resolution issues

This validation runs automatically before each test execution.

### 3. Enhanced Logging Throughout Pipeline

**File**: `mustrd/mustrd.py`

Improved the `run_when_with_logging()` wrapper to provide context-aware logging:

```python
if hasattr(when, 'anzoQueryStep'):
    log.info(f"Executing AnzoGraphmartStepSparqlSource for spec {spec_uri}")
    log.info(f"Using Anzo query step: {when.anzoQueryStep}")
    log.warning(f"If this fails with 'list index out of range', the query step may not exist in Anzo.")

elif hasattr(when, 'fileurl') or hasattr(when, 'file'):
    log.info(f"Executing FileSparqlSource for spec {spec_uri}")
    log.info(f"Using file-based SPARQL: {file_ref}")
```

### 4. Validation-Only CLI Mode

**File**: `mustrd/run.py`

Added `--validate-only` flag to check specs without running them:

```bash
python -m mustrd.run --put /path/to/tests --validate-only
```

Example output:
```
=== Validation Results for test_creation_of_purchase_information_records ===
WARNINGS:
  ⚠️  Relative file path detected: ./data/vx-vendor.ttl
  ⚠️  Using AnzoGraphmartStepSparqlSource with step http://example.com/step123
ERRORS:
  ❌ File does not exist: /path/to/missing-file.ttl

=== Summary ===
Validated 5 test specs
```

## 🎯 Impact on Original Bug

With these improvements, the original bug would now produce this helpful error instead of "list index out of range":

```
ValueError: Query step <http://cambridgesemantics.com/QueryStep/c3e790f84373472193b8ee9a5c4de84c> does not exist in Anzo triplestore. 
Check if the step URI is correct or consider using must:FileSparqlSource instead. 
Example: [ a must:FileSparqlSource ; must:fileurl <file://path/to/query.sparql> ; must:queryType must:UpdateSparql ]
```

Plus the validation would have warned during spec loading:
```
WARNING: Using AnzoGraphmartStepSparqlSource with step http://cambridgesemantics.com/QueryStep/c3e790f84373472193b8ee9a5c4de84c. 
If this step doesn't exist in Anzo, consider using FileSparqlSource for local development.
```

## 🚀 Usage Examples

### Validate specs before running:
```bash
python -m mustrd.run --put mustrd-tests/unit-tests/vx-vendors --validate-only
```

### Run with enhanced logging:
```bash
python -m mustrd.run --put mustrd-tests/unit-tests/vx-vendors --verbose
```

### Check specific test file:
```python
from mustrd.mustrd import validate_test_spec
from rdflib import Graph, URIRef

spec_graph = Graph()
spec_graph.parse("my-test.mustrd.ttl", format="turtle")
warnings, errors = validate_test_spec(spec_graph, URIRef("http://example.com/test"))
```

## 📊 Benefits

1. **🔍 Faster Debugging**: Clear error messages point directly to the problem
2. **🛡️ Early Detection**: Validation catches issues before test execution
3. **📚 Educational**: Error messages include examples and suggestions
4. **🔄 Iterative Development**: `--validate-only` mode for quick checks
5. **📈 Better DX**: Developers spend less time debugging, more time developing

## 🔮 Future Enhancements

- Configuration option to fail fast on validation errors
- Integration with IDEs for real-time validation
- Suggestion engine for common fixes
- Validation rules as configurable policies
