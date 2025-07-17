# Automatic Branch Parameter Deduction

## Overview

This enhancement makes the `branch()` method in the Quantalogic Flow workflow system more intuitive by automatically deducing the `default` and `next_node` parameters when not explicitly provided. This results in cleaner, more fluent workflow definitions.

## Key Features

### 1. Automatic Default Deduction

When no `default` parameter is provided to `branch()`, the system automatically uses the first branch node as the default fallback.

**Before:**
```python
wf.branch([
    ("process_pdf", lambda ctx: ctx["file_type"] == "pdf"),
    ("process_text", lambda ctx: ctx["file_type"] == "text")
], default="process_pdf", next_node="save_result")
```

**After:**
```python
wf.branch([
    ("process_pdf", lambda ctx: ctx["file_type"] == "pdf"),
    ("process_text", lambda ctx: ctx["file_type"] == "text")
]).then("save_result")
```

### 2. Automatic Convergence Detection

When no `next_node` parameter is provided, the system tracks branch state and automatically sets up convergence when the next `then()` method is called.

**Implementation Details:**

1. **Branch State Tracking**: When `branch()` is called without `next_node`, the system:
   - Sets `is_branching = True`
   - Tracks all branch nodes in `branch_nodes`
   - Records the source node in `branch_source_node`

2. **Convergence Detection**: When `then()` is called after a branch:
   - Detects the branching state (`is_branching = True`)
   - Automatically sets up convergence transitions from all branch nodes to the next node
   - Clears the branch state tracking

## API Changes

### Branch Method Signature

```python
def branch(
    self,
    branches: List[Tuple[str, Callable | None]],
    default: str | None = None,  # Now optional
    next_node: str | None = None,  # Already optional
) -> Workflow:
```

### Behavior Changes

1. **Default Parameter**: When `None`, uses the first branch node as the default
2. **Next Node Parameter**: When `None`, sets up branch state tracking for automatic convergence
3. **Backward Compatibility**: All existing explicit usage continues to work unchanged

## Examples

### Basic Automatic Branch

```python
# Simple branch with automatic default and convergence
wf.branch([
    ("handle_pdf", lambda ctx: ctx["type"] == "pdf"),
    ("handle_text", lambda ctx: ctx["type"] == "text")
]).then("process_result")

# Equivalent to the old explicit syntax:
# wf.branch([
#     ("handle_pdf", lambda ctx: ctx["type"] == "pdf"),
#     ("handle_text", lambda ctx: ctx["type"] == "text")
# ], default="handle_pdf", next_node="process_result")
```

### Mixed Usage

```python
# Explicit default, automatic convergence
wf.branch([
    ("handle_pdf", lambda ctx: ctx["type"] == "pdf"),
    ("handle_text", lambda ctx: ctx["type"] == "text")
], default="handle_fallback").then("process_result")

# Automatic default, explicit convergence (legacy)
wf.branch([
    ("handle_pdf", lambda ctx: ctx["type"] == "pdf"),
    ("handle_text", lambda ctx: ctx["type"] == "text")
], next_node="process_result")
```

### Real-World Example: analyze_paper.py

```python
# File type detection with automatic convergence
wf.branch([
    ("convert_pdf_to_markdown", lambda ctx: ctx["file_type"] == "pdf"),
    ("read_text_or_markdown", lambda ctx: ctx["file_type"] in ["text", "markdown"])
]).then("save_markdown_content")

# Continues with sequential processing
wf.then("extract_first_100_lines")
  .then("extract_paper_info")
  .then("generate_linkedin_post")
  # ... etc
```

## Implementation Details

### Workflow State Tracking

The system adds three new instance variables to track branch state:

```python
class Workflow:
    def __init__(self, start_node: str):
        # ... existing initialization ...
        self.is_branching: bool = False
        self.branch_nodes: List[str] = []
        self.branch_source_node: str | None = None
```

### Branch Method Logic

1. **Default Deduction**: If `default` is `None`, use `branches[0][0]` (first branch node)
2. **Immediate Convergence**: If `next_node` is provided, set up convergence transitions immediately
3. **Deferred Convergence**: If `next_node` is `None`, set up branch state tracking for automatic convergence

### Then Method Enhancement

The `then()` method now detects branching state and automatically sets up convergence:

```python
def then(self, next_node: str, condition: Callable | None = None) -> Workflow:
    # ... existing logic ...
    
    elif self.is_branching:
        # This is a convergence point for branching - automatically set up convergence
        for branch_node in self.branch_nodes:
            if branch_node not in self.transitions or not self.transitions[branch_node]:
                self.transitions.setdefault(branch_node, []).append((next_node, None))
        
        # Reset branch state
        self.is_branching = False
        self.branch_nodes = []
        self.branch_source_node = None
    
    # ... rest of method ...
```

## Testing

The enhancement includes comprehensive tests covering:

1. **Auto-deduction of default parameter**
2. **Automatic convergence detection with `then()`**
3. **Fully automatic branch usage**
4. **Mixed explicit/automatic usage**
5. **Backward compatibility with existing explicit syntax**
6. **Edge cases and error handling**

## Benefits

1. **Cleaner Code**: Reduces boilerplate and makes workflows more readable
2. **Fluent API**: Enables natural chaining with `branch().then()` syntax
3. **Backward Compatible**: All existing code continues to work unchanged
4. **Intuitive**: Follows the principle of least surprise - defaults work as expected
5. **Maintainable**: Less explicit state management required in workflow definitions

## Migration Guide

### No Changes Required

Existing code using explicit parameters continues to work unchanged:

```python
# This still works exactly as before
wf.branch([
    ("node_a", condition_a),
    ("node_b", condition_b)
], default="node_a", next_node="convergence")
```

### Optional Migration

You can gradually migrate to the new automatic syntax:

```python
# Old explicit syntax
wf.branch([
    ("node_a", condition_a),
    ("node_b", condition_b)
], default="node_a", next_node="convergence")

# New automatic syntax
wf.branch([
    ("node_a", condition_a),
    ("node_b", condition_b)
]).then("convergence")
```

## Conclusion

This enhancement makes the Quantalogic Flow workflow system more intuitive and reduces the cognitive load required to define complex workflows. By automatically deducing sensible defaults and detecting convergence points, developers can focus on the logic of their workflows rather than the mechanical aspects of state management.
