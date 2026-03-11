def resolve_opers(tokens, i, t, n, helper, namespace, memory, types, stack_ptr, user_functions, stack_frames, return_values, evaluate, execute_source_fn=None):
    if isinstance(tokens[i], n.assign):
        stack_ptr = resolve_assign_oper(tokens, i, t, n, helper, namespace, memory, types, stack_ptr, user_functions, stack_frames, return_values, evaluate, execute_source_fn)
        return True, stack_ptr
    if isinstance(tokens[i], n.equal):
        resolve_bool_oper(tokens, i, t, n, helper, namespace, memory, types, "==", user_functions, stack_frames, return_values, evaluate, stack_ptr, execute_source_fn)
        return True, stack_ptr
    if isinstance(tokens[i], n.not_equal):
        resolve_bool_oper(tokens, i, t, n, helper, namespace, memory, types, "!=", user_functions, stack_frames, return_values, evaluate, stack_ptr, execute_source_fn)
        return True, stack_ptr
    if isinstance(tokens[i], n.gtr_than):
        resolve_bool_oper(tokens, i, t, n, helper, namespace, memory, types, ">", user_functions, stack_frames, return_values, evaluate, stack_ptr, execute_source_fn)
        return True, stack_ptr
    if isinstance(tokens[i], n.less_than):
        resolve_bool_oper(tokens, i, t, n, helper, namespace, memory, types, "<", user_functions, stack_frames, return_values, evaluate, stack_ptr, execute_source_fn)
        return True, stack_ptr
    if isinstance(tokens[i], n.gtr_than_or_equal):
        resolve_bool_oper(tokens, i, t, n, helper, namespace, memory, types, ">=", user_functions, stack_frames, return_values, evaluate, stack_ptr, execute_source_fn)
        return True, stack_ptr
    if isinstance(tokens[i], n.less_than_or_equal):
        resolve_bool_oper(tokens, i, t, n, helper, namespace, memory, types, "<=", user_functions, stack_frames, return_values, evaluate, stack_ptr, execute_source_fn)
        return True, stack_ptr
    if isinstance(tokens[i], n.invert):
        resolve_invert_oper(tokens, i, t, n, helper, namespace, memory, types, user_functions, stack_frames, return_values, stack_ptr, execute_source_fn)
        return True, stack_ptr
    if isinstance(tokens[i], n.free):
        resolve_free_oper(tokens, i, t, helper, namespace, memory)
        return True, stack_ptr

    if isinstance(tokens[i].node1, t.integer) and isinstance(tokens[i].node2, t.integer):
        if type(tokens[i].node1) != type(tokens[i].node2):
            # Unary-negation rewrite may produce 0 - <typed-int>; align the synthetic zero type.
            if isinstance(tokens[i], n.sub) and tokens[i].node1.val == 0 and type(tokens[i].node1) is t.i32:
                tokens[i].node1 = type(tokens[i].node2)(0)
            else:
                raise TypeError(f"Type mismatch in operation: {type(tokens[i].node1).__name__} vs {type(tokens[i].node2).__name__}")
        
        resolve_type = type(tokens[i].node1) # resolve_type is the type of the result of the operation, which should be the same as the type of the operands since we do not allow mixed-type operations. We can just use the type of one of the operands for this.

        if isinstance(tokens[i], n.add):
            tokens[i] = resolve_type(tokens[i].node1.val + tokens[i].node2.val)
        elif isinstance(tokens[i], n.sub):
            tokens[i] = resolve_type(tokens[i].node1.val - tokens[i].node2.val)
        elif isinstance(tokens[i], n.mult):
            tokens[i] = resolve_type(tokens[i].node1.val * tokens[i].node2.val)
        elif isinstance(tokens[i], n.div):
            tokens[i] = resolve_type(tokens[i].node1.val / tokens[i].node2.val)
    else:
        if isinstance(tokens[i].node1, n.subexp):
            stack_ptr, _ = evaluate(tokens[i].node1.val, memory, namespace, types, n, t, helper, user_functions, stack_frames, return_values, stack_ptr, execute_source_fn)
            if len(tokens[i].node1.val) != 1:
                raise TypeError("Sub-expression did not reduce to a single value")
            tokens[i].node1 = tokens[i].node1.val[0]
        elif isinstance(tokens[i].node1, n.oper):
            temp = [tokens[i].node1]
            stack_ptr, _ = evaluate(temp, memory, namespace, types, n, t, helper, user_functions, stack_frames, return_values, stack_ptr, execute_source_fn)
            tokens[i].node1 = temp[0]
        elif isinstance(tokens[i].node1, t.function):
            temp = [tokens[i].node1]
            stack_ptr, _ = evaluate(temp, memory, namespace, types, n, t, helper, user_functions, stack_frames, return_values, stack_ptr, execute_source_fn)
            tokens[i].node1 = temp[0]

        if isinstance(tokens[i].node2, n.subexp):
            stack_ptr, _ = evaluate(tokens[i].node2.val, memory, namespace, types, n, t, helper, user_functions, stack_frames, return_values, stack_ptr, execute_source_fn)
            if len(tokens[i].node2.val) != 1:
                raise TypeError("Sub-expression did not reduce to a single value")
            tokens[i].node2 = tokens[i].node2.val[0]
        elif isinstance(tokens[i].node2, n.oper):
            temp = [tokens[i].node2]
            stack_ptr, _ = evaluate(temp, memory, namespace, types, n, t, helper, user_functions, stack_frames, return_values, stack_ptr, execute_source_fn)
            tokens[i].node2 = temp[0]
        elif isinstance(tokens[i].node2, t.function):
            temp = [tokens[i].node2]
            stack_ptr, _ = evaluate(temp, memory, namespace, types, n, t, helper, user_functions, stack_frames, return_values, stack_ptr, execute_source_fn)
            tokens[i].node2 = temp[0]

        return True, stack_ptr

    return False, stack_ptr

def resolve_assign_oper(tokens, i, t, n, helper, namespace, memory, types, stack_ptr, user_functions, stack_frames, return_values, evaluate, execute_source_fn=None) -> int:
    """Resolve assignment and return (possibly unchanged) stack pointer."""
    sp = stack_ptr

    if not isinstance(tokens[i].node1, t.var_ref):
        raise TypeError("Left side of assignment must be a variable reference")

    var_name = tokens[i].node1.val
    var_data = helper.locate_var_in_namespace(namespace, var_name, return_just_the_check=False)
    var_meta = var_data[0]
    var_type = var_meta["type"]
    mem_addr = var_meta["addr"]

    rhs = tokens[i].node2
    if isinstance(rhs, n.oper | n.subexp | t.function):
        temp = [rhs]
        sp, _ = evaluate(temp, memory, namespace, types, n, t, helper, user_functions, stack_frames, return_values, sp, execute_source_fn)
        rhs = temp[0]
    elif isinstance(rhs, t.var_ref):
        rhs = helper.dereference_var(t, namespace, memory, rhs)

    if var_type == "array":
        if not isinstance(rhs, t.array):
            raise TypeError(f"Type mismatch in assignment to variable '{var_name}': expected array, got {type(rhs).__name__}")
        expected_elem_type = var_meta["elem_type"]
        expected_len = var_meta["length"]
        if rhs.arrayType != expected_elem_type:
            raise TypeError(f"Array element type mismatch: expected {expected_elem_type}, got {rhs.arrayType}")
        if len(rhs.val) != expected_len:
            raise ValueError(f"Array assignment size mismatch: expected length {expected_len}, got {len(rhs.val)}")
        rhs.size = expected_len
        helper.load_to_mem(memory, rhs, sp, "array", memidx=mem_addr)
    else:
        if type(rhs).__name__ != var_type:
            raise TypeError(
                f"Type mismatch in assignment to variable '{var_name}': expected {var_type}, got {type(rhs).__name__}"
            )
        helper.load_to_mem(memory, rhs, sp, type(rhs).__name__, memidx=mem_addr)


    namespace[var_data[1]][var_name] = var_meta
    tokens[i] = t.i32(0)
    return sp

def resolve_bool_oper(tokens, i, t, n, helper, namespace, memory, types, oper: str, user_functions, stack_frames, return_values, evaluate, stack_ptr=0, execute_source_fn=None):
    lhs = tokens[i].node1
    if isinstance(lhs, n.oper | n.subexp | t.function):
        temp = [lhs]
        _, _ = evaluate(temp, memory, namespace, types, n, t, helper, user_functions, stack_frames, return_values, stack_ptr, evaluate, execute_source_fn)
        lhs = temp[0]
    elif isinstance(lhs, t.var_ref):
        lhs = helper.dereference_var(t, namespace, memory, lhs)

    rhs = tokens[i].node2
    if isinstance(rhs, n.oper | n.subexp | t.function):
        temp = [rhs]
        _ = evaluate(temp, memory, namespace, types, n, t, helper, user_functions, stack_frames,  return_values,stack_ptr, execute_source_fn)
        rhs = temp[0]
    elif isinstance(rhs, t.var_ref):
        rhs = helper.dereference_var(t, namespace, memory, rhs)

    if type(lhs).__name__ != type(rhs).__name__:
        raise TypeError(f"Type mismatch in equality operator '{lhs.val} {oper} {rhs.val}'")

    match oper:
        case "==":
            bool_result = lhs.val == rhs.val
        case "!=":
            bool_result = lhs.val != rhs.val
        case ">":
            bool_result = lhs.val > rhs.val
        case "<":
            bool_result = lhs.val < rhs.val
        case ">=":
            bool_result = lhs.val >= rhs.val
        case "<=":
            bool_result = lhs.val <= rhs.val

    tokens[i] = t.boolean(bool_result)

def resolve_invert_oper(tokens, i, t, n, helper, namespace, memory, types, user_functions, stack_frames, return_values, evaluate, stack_ptr=0, execute_source_fn=None):
    rhs = tokens[i].node
    if isinstance(rhs, n.oper | n.subexp | t.function):
        temp = [rhs]
        _, _ = evaluate(temp, memory, namespace, types, n, t, helper, user_functions, stack_frames, return_values, stack_ptr, execute_source_fn)
        rhs = temp[0]
    elif isinstance(rhs, t.var_ref):
        rhs = helper.dereference_var(t, namespace, memory, rhs)

    if not isinstance(rhs, t.boolean):
        raise TypeError("Invert operator only inverts a boolean. To use truthiness, try using truthy operator ('!!').")

    tokens[i] = t.boolean(not rhs.val)

def resolve_free_oper(tokens, i, t, helper, namespace, memory):
    if not isinstance(tokens[i].node, t.var_ref):
        raise TypeError(f"free operator must be a var_ref, not {type(tokens[i].node).__name__}")

    var_name = tokens[i].node.val
    tokens[i] = helper.dereference_var(t, namespace, memory, tokens[i].node)
    var_data = helper.locate_var_in_namespace(namespace, var_name, return_just_the_check=False) # var_data is (metadata, scope_level)
    del namespace[var_data[1]][var_name]