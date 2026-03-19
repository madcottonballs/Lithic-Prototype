"""This module contains the logic for resolving operators. 
This includes both evaluating the operands and performing the operation itself. 
The main entry point is the resolve_opers function, which takes a list of tokens and an index, and checks if the token at that index is an operator that can be resolved. 
If it is, it resolves the operator and returns True along with the (possibly updated) stack pointer. If it is not, it returns False along with the original stack pointer."""

def resolve_opers(tokens, i, ltc, return_values, evaluate, execute_source_fn=None):
    t = ltc.t
    n = ltc.n
    if isinstance(tokens[i], n.mono_oper):
        if isinstance(tokens[i], n.invert):
            resolve_invert_oper(tokens, i, ltc, return_values, evaluate, execute_source_fn)
            return True, ltc.sp
        elif isinstance(tokens[i], n.free):
            resolve_free_oper(tokens, i, ltc)
            return True
        elif isinstance(tokens[i], n.memloc):
            resolve_memloc_oper(tokens, i, ltc)
            return True
    elif isinstance(tokens[i], n.oper):
        if isinstance(tokens[i], n.assign):
            resolve_assign_oper(tokens, i, ltc, return_values, evaluate, execute_source_fn)
            return True
        if isinstance(tokens[i], n.equal):
            resolve_bool_oper(ltc, tokens, i, "==", return_values, evaluate, execute_source_fn)
            return True
        if isinstance(tokens[i], n.not_equal):
            resolve_bool_oper(ltc, tokens, i, "!=", return_values, evaluate, execute_source_fn)
            return True
        if isinstance(tokens[i], n.gtr_than):
            resolve_bool_oper(ltc, tokens, i, ">", return_values, evaluate, execute_source_fn)
            return True
        if isinstance(tokens[i], n.less_than):
            resolve_bool_oper(ltc, tokens, i, "<", return_values, evaluate, execute_source_fn)
            return True
        if isinstance(tokens[i], n.gtr_than_or_equal):
            resolve_bool_oper(ltc, tokens, i, ">=", return_values, evaluate, execute_source_fn)
            return True
        if isinstance(tokens[i], n.less_than_or_equal):
            resolve_bool_oper(ltc, tokens, i, "<=", return_values, evaluate, execute_source_fn)
            return True

    if isinstance(tokens[i].node1, t.integer) and isinstance(tokens[i].node2, t.integer):
        if type(tokens[i].node1) == t.ptr or type(tokens[i].node2) == t.ptr: # 
            ptr_arithmatic = True
        else:
            ptr_arithmatic = False
        if (type(tokens[i].node1) != type(tokens[i].node2)) and not ptr_arithmatic:  # if not using ptr arithmetic, then the types must match. If using ptr arithmetic, then one can be a ptr and the other can be an integer.
            # Unary-negation rewrite may produce 0 - <typed-int>; align the synthetic zero type.
            if isinstance(tokens[i], n.sub) and tokens[i].node1.val == 0 and type(tokens[i].node1) is t.i32:
                tokens[i].node1 = type(tokens[i].node2)(0)
            else:
                raise TypeError(f"Type mismatch in operation: {type(tokens[i].node1).__name__} vs {type(tokens[i].node2).__name__}")
        
        if ptr_arithmatic:
            resolve_type = t.ptr
        else:
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
            ltc.sp, _, ltc.hp = evaluate(tokens[i].node1.val, ltc, return_values, execute_source_fn)
            if len(tokens[i].node1.val) != 1:
                raise TypeError("Sub-expression did not reduce to a single value")
            tokens[i].node1 = tokens[i].node1.val[0]
        elif isinstance(tokens[i].node1, n.oper):
            temp = [tokens[i].node1]
            ltc.sp, _, ltc.hp = evaluate(temp, ltc, return_values, execute_source_fn)
            tokens[i].node1 = temp[0]
        elif isinstance(tokens[i].node1, t.function):
            temp = [tokens[i].node1]
            ltc.sp, _, ltc.hp = evaluate(temp, ltc, return_values, execute_source_fn)
            tokens[i].node1 = temp[0]

        if isinstance(tokens[i].node2, n.subexp):
            ltc.sp, _, ltc.hp = evaluate(tokens[i].node2.val, ltc, return_values, execute_source_fn)
            if len(tokens[i].node2.val) != 1:
                raise TypeError("Sub-expression did not reduce to a single value")
            tokens[i].node2 = tokens[i].node2.val[0]
        elif isinstance(tokens[i].node2, n.oper):
            temp = [tokens[i].node2]
            ltc.sp, _, ltc.hp = evaluate(temp, ltc, return_values, execute_source_fn)
            tokens[i].node2 = temp[0]
        elif isinstance(tokens[i].node2, t.function):
            temp = [tokens[i].node2]
            ltc.sp, _, ltc.hp = evaluate(temp, ltc, return_values, execute_source_fn)
            tokens[i].node2 = temp[0]

        return True

    return False

def resolve_assign_oper(tokens, i, ltc, return_values, evaluate, execute_source_fn=None) -> None:
    """Resolve assignment"""
    t = ltc.t
    n = ltc.n
    helper = ltc.helper
    namespace = ltc.namespace

    if isinstance(tokens[i].node1, t.function) and tokens[i].node1.val == "@":
        temp = [tokens[i].node1]
        evaluate(temp, ltc, return_values, execute_source_fn)   # return_values can be ignored
        tokens[i].node1 = temp[0]

    if isinstance(tokens[i].node1, n.at_func_return):
        target = tokens[i].node1

        rhs = tokens[i].node2
        helper.resolve_node(rhs, ltc, return_values, evaluate, execute_source_fn)

        helper.load_to_mem(ltc, rhs, type(rhs).__name__, memidx=target.addr)
        tokens[i] = t.i32(0)
        return

    if not isinstance(tokens[i].node1, t.var_ref):
        raise TypeError("Left side of assignment must be a variable reference")

    var_name = tokens[i].node1.val
    var_data = helper.locate_var_in_namespace(namespace, var_name, return_just_the_check=False)
    var_meta = var_data[0]
    var_type = var_meta["type"]
    mem_addr = var_meta["addr"]

    rhs = tokens[i].node2
    helper.resolve_node(rhs, ltc, return_values, evaluate, execute_source_fn)

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
        helper.load_to_mem(ltc, rhs, "array", memidx=mem_addr)
    else:
        if type(rhs).__name__ != var_type:
            raise TypeError(
                f"Type mismatch in assignment to variable '{var_name}': expected {var_type}, got {type(rhs).__name__}"
            )
        helper.load_to_mem(ltc, rhs, type(rhs).__name__, memidx=mem_addr)


    namespace[var_data[1]][var_name] = var_meta
    tokens[i] = t.i32(0)
    return

def resolve_bool_oper(ltc, tokens, i, oper: str, return_values, evaluate, execute_source_fn=None):
    t = ltc.t
    helper = ltc.helper
    lhs = tokens[i].node1
    helper.resolve_node(lhs, ltc, return_values, evaluate, execute_source_fn)

    rhs = tokens[i].node2
    helper.resolve_node(rhs, ltc, return_values, evaluate, execute_source_fn)

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

def resolve_invert_oper(tokens, i, ltc, return_values, evaluate, execute_source_fn=None):
    t = ltc.t
    rhs = tokens[i].node
    helper = ltc.helper

    helper.resolve_node(rhs, ltc, return_values, evaluate, execute_source_fn)

    if not isinstance(rhs, t.boolean):
        raise TypeError("Invert operator only inverts a boolean. To use truthiness, try using truthy operator ('!!').")

    tokens[i] = t.boolean(not rhs.val)

def resolve_free_oper(tokens, i, ltc):
    t = ltc.t
    helper = ltc.helper
    if not isinstance(tokens[i].node, t.var_ref):
        raise TypeError(f"free operator must be a var_ref, not {type(tokens[i].node).__name__}")

    var_name = tokens[i].node.val
    tokens[i] = helper.dereference_var(ltc, tokens[i].node)
    var_data = helper.locate_var_in_namespace(ltc.namespace, var_name, return_just_the_check=False) # var_data is (metadata, scope_level)
    del ltc.namespace[var_data[1]][var_name]

def resolve_memloc_oper(tokens, i, ltc):
    t = ltc.t
    rhs = tokens[i].node

    if not isinstance(rhs, t.ltc_type | t.var_ref):
        raise TypeError(f"memloc operator takes a ltc_type or var_ref, not '{type(tokens[i].node).__name__}'")

    ltc.helper.resolve_node(rhs, ltc, None, None, None) # can just pass None for the last three arguments since resolve_node will not use them when resolving a var_ref

    if not rhs.inmemory:
        raise TypeError(f"Object '{rhs.val}' of type '{type(rhs).__name__}' is not stored in memory and thus does not have a memory address. This error exists only in the interpreter version.")

    tokens[i] = t.ptr(rhs.memloc)