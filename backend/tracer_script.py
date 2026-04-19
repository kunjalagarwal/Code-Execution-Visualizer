import sys
import json

def _get_id(obj):
    return f"ref_{id(obj)}"

def serialize_val(val, heap, visited=None):
    if visited is None:
        visited = set()
    v_id = id(val)
    if v_id in visited:
        return _get_id(val)
    
    if type(val) in (int, float, bool, type(None), str):
        return val

    # Non-primitive
    visited.add(v_id)
    ref = _get_id(val)
    
    if type(val) is list:
        heap[ref] = {"type": "list", "value": [serialize_val(item, heap, visited) for item in val]}
        return ref
    elif type(val) is dict:
        heap[ref] = {"type": "dict", "value": {str(k): serialize_val(v, heap, visited) for k, v in val.items()}}
        return ref
    elif type(val) is tuple:
        heap[ref] = {"type": "tuple", "value": [serialize_val(item, heap, visited) for item in val]}
        return ref
    elif type(val) is set:
        heap[ref] = {"type": "set", "value": [serialize_val(item, heap, visited) for item in val]}
        return ref
    else:
        # Fallback for custom objects / functions
        heap[ref] = {"type": type(val).__name__, "value": repr(val)}
        return ref

trace_data = []
MAX_STEPS = 1000
step_count = 0

def trace_calls(frame, event, arg):
    global step_count
    
    # We only want to trace user code, filter out internal python libs
    if "user_code.py" not in frame.f_code.co_filename:
        return None
        
    if event in ['line', 'call', 'return']:
        step_count += 1
        if step_count > MAX_STEPS:
            raise Exception("Maximum execution steps exceeded.")
            
        heap = {}
        # Collect stack frames up to this point
        call_stack = []
        curr_frame = frame
        while curr_frame and "user_code.py" in curr_frame.f_code.co_filename:
            fn_name = curr_frame.f_code.co_name
            # serialize locals
            locals_serialized = {}
            for k, v in curr_frame.f_locals.items():
                # Filter out standard metadata
                if k in ['__name__', '__builtins__', '__doc__', '__package__', '__loader__', '__spec__', '__file__', '__cached__']: 
                    continue
                locals_serialized[k] = serialize_val(v, heap)
                
            call_stack.insert(0, {
                "func_name": fn_name,
                "locals": locals_serialized
            })
            curr_frame = curr_frame.f_back
            
        trace_data.append({
            "line": frame.f_lineno,
            "event": event,
            "stack": call_stack,
            "heap": heap,
            "return_val": serialize_val(arg, heap) if event == 'return' else None
        })
        
    return trace_calls

if __name__ == "__main__":
    import os
    
    code_path = sys.argv[1]
    
    with open(code_path, "r", encoding="utf-8") as f:
        code = f.read()
        
    # setup stdin if provided
    if len(sys.argv) > 2:
        stdin_path = sys.argv[2]
        if os.path.exists(stdin_path) and os.path.getsize(stdin_path) > 0:
            sys.stdin = open(stdin_path, "r", encoding="utf-8")
        
    try:
        compiled_code = compile(code, "user_code.py", "exec")
        # Initialize a fresh globals dict avoiding pollution
        ns = {"__name__": "__main__", "__builtins__": __builtins__}
        
        sys.settrace(trace_calls)
        exec(compiled_code, ns)
        sys.settrace(None)
    except Exception as e:
        sys.settrace(None)
        # Record the error safely
        trace_data.append({"error": str(e), "line": getattr(e, 'lineno', None)})
        
    # dump data as the last line
    print(json.dumps(trace_data))
