"""This module contains the logic for resolving operators. 
This includes both evaluating the operands and performing the operation itself. 
The main entry point is the resolve_opers function, which takes a list of tokens and an index, and checks if the token at that index is an operator that can be resolved. 
If it is, it resolves the operator and returns True along with the (possibly updated) stack pointer. If it is not, it returns False along with the original stack pointer."""

def _resolve_dot_target(dot_node, ltc, return_values, evaluate, execute_source_fn):
    """Return (struct_name, field_name, struct_addr) for nested dot assignment."""
    t = ltc.t
    n = ltc.n
    helper = ltc.helper
    shelper = ltc.shelper

    if not isinstance(dot_node, n.dot_oper):
        ltc.error("dot target resolver expects a dot operator node")

    # Left-associated chain: dot(dot(b, ex), x)
    if isinstance(dot_node.node1, n.dot_oper):
        parent_name, parent_field, parent_addr = _resolve_dot_target(
            dot_node.node1, ltc, return_values, evaluate, execute_source_fn
        )
        parent_value = shelper.read_struct_field_from_memory(ltc, parent_name, parent_field, parent_addr)
        if not isinstance(parent_value, t.struct_instance):
            ltc.error("Nested dot assignment requires intermediate fields to be structs")
        if not parent_value.inmemory or parent_value.memloc is None:
            ltc.error("Nested struct field must be stored in memory for assignment")
        if not isinstance(dot_node.node2, t.token):
            ltc.error("Final field in dot assignment must be an identifier token")
        return parent_value.struct_name, dot_node.node2.val, parent_value.memloc

    # Right-associated chain fallback: dot(b, dot(ex, x))
    if isinstance(dot_node.node2, n.dot_oper):
        base_value = helper.resolve_node(dot_node.node1, ltc, return_values, evaluate, execute_source_fn)
        if not isinstance(base_value, t.struct_instance):
            ltc.error("dot assignment expects a struct instance on the left-hand side")
        if not base_value.inmemory or base_value.memloc is None:
            ltc.error("Struct instance must be stored in memory to assign fields with '.'")

        inner = dot_node.node2
        intermediate = shelper.read_struct_field_from_memory(ltc, base_value.struct_name, inner.node1.val, base_value.memloc)
        if not isinstance(intermediate, t.struct_instance):
            ltc.error("Nested dot assignment requires intermediate fields to be structs")
        if not intermediate.inmemory or intermediate.memloc is None:
            ltc.error("Nested struct field must be stored in memory for assignment")
        if isinstance(inner.node2, n.dot_oper):
            return _resolve_dot_target(
                n.dot_oper(intermediate, inner.node2),
                ltc,
                return_values,
                evaluate,
                execute_source_fn,
            )
        return intermediate.struct_name, inner.node2.val, intermediate.memloc

    struct_obj = helper.resolve_node(dot_node.node1, ltc, return_values, evaluate, execute_source_fn)
    if not isinstance(struct_obj, t.struct_instance):
        ltc.error("dot assignment expects a struct instance on the left-hand side")
    if not struct_obj.inmemory or struct_obj.memloc is None:
        ltc.error("Struct instance must be stored in memory to assign fields with '.'")
    if not isinstance(dot_node.node2, t.token):
        ltc.error("dot assignment target must end in a field name")
    return struct_obj.struct_name, dot_node.node2.val, struct_obj.memloc

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
        if isinstance(tokens[i], n.dot_oper):
            resolve_dot_oper(tokens, i, ltc, return_values, evaluate, execute_source_fn)
            return True
        if isinstance(tokens[i], n.index_oper):
            resolve_index_oper(tokens, i, ltc, return_values, evaluate, execute_source_fn)
            return True
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
            # Allow ++/-- and // ** rewriting to use i32 literals with other integer types by aligning the literal.
            if isinstance(tokens[i], (n.add, n.sub)):
                if isinstance(tokens[i].node1, t.integer) and isinstance(tokens[i].node2, t.i32) and tokens[i].node2.val in (0, 1, 2):
                    tokens[i].node2 = type(tokens[i].node1)(tokens[i].node2.val, ltc)
                elif isinstance(tokens[i].node2, t.integer) and isinstance(tokens[i].node1, t.i32) and tokens[i].node1.val in (0, 1, 2):
                    tokens[i].node1 = type(tokens[i].node2)(tokens[i].node1.val, ltc)
            if isinstance(tokens[i], (n.mult, n.div)):
                if isinstance(tokens[i].node1, t.integer) and isinstance(tokens[i].node2, t.i32) and tokens[i].node2.val in (2,):
                    tokens[i].node2 = type(tokens[i].node1)(tokens[i].node2.val, ltc)
                elif isinstance(tokens[i].node2, t.integer) and isinstance(tokens[i].node1, t.i32) and tokens[i].node1.val in (2,):
                    tokens[i].node1 = type(tokens[i].node2)(tokens[i].node1.val, ltc)
            # If alignment fixed the mismatch, continue without error.
            if type(tokens[i].node1) == type(tokens[i].node2):
                pass
            else:
            # Unary-negation rewrite may produce 0 - <typed-int>; align the synthetic zero type.
                if isinstance(tokens[i], n.sub) and tokens[i].node1.val == 0 and type(tokens[i].node1) is t.i32:
                    tokens[i].node1 = type(tokens[i].node2)(0, ltc)
                else:
                    ltc.error(f"Type mismatch in operation: {type(tokens[i].node1).__name__} vs {type(tokens[i].node2).__name__}")
        
        if ptr_arithmatic:
            resolve_type = t.ptr
        else:
            resolve_type = type(tokens[i].node1) # resolve_type is the type of the result of the operation, which should be the same as the type of the operands since we do not allow mixed-type operations. We can just use the type of one of the operands for this.

        if isinstance(tokens[i], n.add):
            tokens[i] = resolve_type(tokens[i].node1.val + tokens[i].node2.val, ltc)
        elif isinstance(tokens[i], n.sub):
            tokens[i] = resolve_type(tokens[i].node1.val - tokens[i].node2.val, ltc)
        elif isinstance(tokens[i], n.mult):
            tokens[i] = resolve_type(tokens[i].node1.val * tokens[i].node2.val, ltc)
        elif isinstance(tokens[i], n.div):
            tokens[i] = resolve_type(tokens[i].node1.val / tokens[i].node2.val, ltc)
    else:
        tokens[i].node1 = ltc.helper.resolve_node(tokens[i].node1, ltc, return_values, evaluate, execute_source_fn)
        tokens[i].node2 = ltc.helper.resolve_node(tokens[i].node2, ltc, return_values, evaluate, execute_source_fn)
        return True

    return False

def resolve_index_oper(tokens, i, ltc, return_values, evaluate, execute_source_fn=None):
    t = ltc.t
    helper = ltc.helper
    base = helper.resolve_node(tokens[i].node1, ltc, return_values, evaluate, execute_source_fn)
    idx = helper.resolve_node(tokens[i].node2, ltc, return_values, evaluate, execute_source_fn)

    if not isinstance(idx, t.integer):
        ltc.error("Index must resolve to an integer")

    index_val: int = idx.val

    if isinstance(base, t.array):
        array_len = base.get_size()
        if array_len == 0:
            ltc.error("Cannot index an empty array")
        if index_val < 0:
            index_val = index_val % array_len
        if index_val >= array_len:
            ltc.error(f"Tried to index an array of size {array_len} with an index of {index_val}")
        
        # For arrays, we want to return the element at the index, but we need to make sure to return it as the correct type according to the array's element type. This is because the elements of the array are stored as their raw values (e.g. an i32 array stores the i32 values directly), so when we retrieve an element from the array we need to wrap it in the appropriate ltc_type class (e.g. t.i32) before returning it.
        elem = base.val[index_val]
        val = elem.val if hasattr(elem, "val") else elem
        
        match base.arrayType:
            case "i32" | "i64" | "i8" | "i16" | "u32" | "u64" | "u8" | "u16" | "ptr":
                tokens[i] = ltc.types[base.arrayType](val, ltc)
            case "boolean":
                tokens[i] = t.boolean(val)
            case "char":
                tokens[i] = t.char(val)
            case _:
                ltc.error("Unsupported type of array used for indexing")
        
        return

    if isinstance(base, t.string):
        if index_val < 0 or index_val >= len(base.val):
            ltc.error(f"Tried to index a string of size {len(base.val)} with an index of {index_val}")
        element = base.val[index_val]
        tokens[i] = t.char(element)
        return

    if isinstance(base, t.ltctuple):
        tuple_len = len(base.element_types)
        if index_val < 0:
            index_val = index_val % tuple_len
        if index_val >= tuple_len:
            ltc.error(f"Tried to index a tuple of size {tuple_len} with an index of {index_val}")
        if base.inmemory and base.memloc is not None:
            tokens[i] = t.ltctuple.read_element_from_memory(ltc, list(base.element_types), index_val, base.memloc)
        else:
            tokens[i] = base.val[index_val]
        return
    
    if isinstance(base, t.ptr):
        if index_val < 0:
            ltc.error(f"Cannot use negative index {index_val} for pointer indexing, as there is no defined size for the pointer's referent type to use for wrapping the index like we do for arrays and tuples")

        ptr_base_addr = base.val

        # find the variable in the namespace that corresponds to this pointer to get its type tag for proper pointer arithmetic
        # we are doing this to get the element_size
        # element_size is needed to calculate the offset for pointer arithmetic 
        if base.var_name == None:
            ltc.error("Only pointer variables can have type tags, but got an unreferenced pointer")
        
        # check if the variable exists, it should but let's be safe
        var_data = ltc.helper.locate_var_in_namespace(ltc.namespace, base.var_name, return_just_the_check=False)
        (var_meta, scope_level) = var_data
        if var_meta is None:
            ltc.error(f"Variable '{base.var_name}' not found for retrieving type tag")
        
        if "tag" not in ltc.namespace[scope_level][base.var_name]:
            ltc.error(f"Variable '{base.var_name}' is not tagged")
        
        pointer_type: str = ltc.namespace[scope_level][base.var_name]["tag"]
        element_size: int = helper.get_ltc_type_size(pointer_type, ltc)

        # now that we have element_size, we can calculate the memory address of the indexed element and return a pointer to that address

        elem_addr = ptr_base_addr + index_val * element_size

        ptr_deref = helper.read_ltc_type_from_mem(ltc.memory, elem_addr, pointer_type, ltc) # returns the obj read from memory
        tokens[i] = ptr_deref
        return

    ltc.error("Indexing is only supported for arrays, strings, and tuples")

def resolve_assign_oper(tokens, i, ltc, return_values, evaluate, execute_source_fn=None) -> None:
    """Resolve assignment"""
    t = ltc.t
    n = ltc.n
    helper = ltc.helper
    shelper = ltc.shelper
    namespace = ltc.namespace
    if isinstance(tokens[i].node1, n.dot_oper):
        rhs = helper.resolve_node(tokens[i].node2, ltc, return_values, evaluate, execute_source_fn)
        struct_name, field_name, struct_addr = _resolve_dot_target(
            tokens[i].node1, ltc, return_values, evaluate, execute_source_fn
        )

        shelper.update_struct_field_in_memory(
            ltc,
            struct_name,
            field_name,
            rhs,
            struct_addr,
        )

        tokens[i] = t.i32(0, ltc)
        return
    
    if isinstance(tokens[i].node1, t.function) and tokens[i].node1.val == "@":
        temp = [tokens[i].node1]
        evaluate(temp, ltc, return_values, execute_source_fn)   # return_values can be ignored
        tokens[i].node1 = temp[0]

    if isinstance(tokens[i].node1, n.at_func_return):
        target = tokens[i].node1

        rhs = helper.resolve_node(tokens[i].node2, ltc, return_values, evaluate, execute_source_fn)
        helper.load_to_mem(ltc, rhs, type(rhs).__name__, memidx=target.addr)
        tokens[i] = t.i32(0, ltc)
        return

    if isinstance(tokens[i].node1, n.index_oper):
        base = tokens[i].node1.node1
        index_node = tokens[i].node1.node2
        index_val = helper.resolve_node(index_node, ltc, return_values, evaluate, execute_source_fn)
        if not isinstance(index_val, t.integer):
            ltc.error("Index must resolve to an integer")

        rhs = helper.resolve_node(tokens[i].node2, ltc, return_values, evaluate, execute_source_fn)

        # tuple/array/ptr indexed assignment
        if isinstance(base, t.var_ref):
            var_meta: dict = helper.locate_var_in_namespace(namespace, base.val, return_just_the_check=False)[0]
            if var_meta is None:
                ltc.error(f"Variable '{base.val}' not found")

            if var_meta.get("type") == "tuple":
                element_types = var_meta["element_types"]
                if index_val.val < 0:
                    index_val.val = index_val.val % len(element_types)
                if index_val.val >= len(element_types):
                    ltc.error(f"Tuple index out of range: {index_val.val} for length {len(element_types)}")
                if type(rhs).__name__ != element_types[index_val.val]:
                    ltc.error(f"tSet type mismatch: expected {element_types[index_val.val]}, got {type(rhs).__name__}")
                t.ltctuple.update_element_in_memory(ltc, var_meta["addr"], index_val.val, rhs, list(element_types))
                tokens[i] = t.i32(0, ltc)
                return

            if var_meta.get("type") == "array":
                elem_type = var_meta["elem_type"]
                array_len = var_meta["length"]
                if index_val.val < 0:
                    index_val.val = index_val.val % array_len
                if index_val.val >= array_len:
                    ltc.error(f"Array index out of range: {index_val.val} for length {array_len}")
                if type(rhs).__name__ != elem_type:
                    ltc.error(f"aSet type mismatch: expected {elem_type}, got {type(rhs).__name__}")
                base_addr = var_meta["addr"]
                match elem_type:
                    case "i32" | "i64" | "i8" | "i16" | "u32" | "u64" | "u8" | "u16" | "ptr":
                        elem_addr = base_addr + (index_val.val * helper.get_ltc_type_size(elem_type, ltc))
                        helper.load_to_mem(ltc, rhs, elem_type, memidx=elem_addr)
                    case "boolean":
                        elem_addr = base_addr + index_val.val
                        helper.load_to_mem(ltc, rhs, "boolean", memidx=elem_addr)
                    case "char":
                        elem_addr = base_addr + index_val.val
                        helper.load_to_mem(ltc, rhs, "char", memidx=elem_addr)
                    case _:
                        ltc.error(f"aSet does not support element type '{elem_type}' yet")
                tokens[i] = t.i32(0, ltc)
                return

            if var_meta.get("type") == "ptr":
                if "tag" not in var_meta:
                    ltc.error(f"Pointer variable '{base.val}' is not tagged")
                pointer_type = var_meta["tag"]
                elem_size = helper.get_ltc_type_size(pointer_type, ltc)
                elem_addr = var_meta["addr"]  # pointer value stored at addr
                ptr_value = helper.read_ltc_type_from_mem(ltc.memory, elem_addr, "ptr", ltc).val
                target_addr = ptr_value + index_val.val * elem_size
                helper.load_to_mem(ltc, rhs, pointer_type, memidx=target_addr)
                tokens[i] = t.i32(0, ltc)
                return

        resolved_base = helper.resolve_node(base, ltc, return_values, evaluate, execute_source_fn)
        if isinstance(resolved_base, t.array):
            array_len = resolved_base.get_size()
            elem_type = resolved_base.arrayType
            if index_val.val < 0:
                index_val.val = index_val.val % array_len
            if index_val.val >= array_len:
                ltc.error(f"Array index out of range: {index_val.val} for length {array_len}")
            if type(rhs).__name__ != elem_type:
                ltc.error(f"aSet type mismatch: expected {elem_type}, got {type(rhs).__name__}")
            if not resolved_base.inmemory or resolved_base.memloc is None:
                ltc.error("Indexed assignment requires an array stored in memory")

            base_addr = resolved_base.memloc
            match elem_type:
                case "i32" | "i64" | "i8" | "i16" | "u32" | "u64" | "u8" | "u16" | "ptr":
                    elem_addr = base_addr + (index_val.val * helper.get_ltc_type_size(elem_type, ltc))
                    helper.load_to_mem(ltc, rhs, elem_type, memidx=elem_addr)
                case "boolean":
                    elem_addr = base_addr + index_val.val
                    helper.load_to_mem(ltc, rhs, "boolean", memidx=elem_addr)
                case "char":
                    elem_addr = base_addr + index_val.val
                    helper.load_to_mem(ltc, rhs, "char", memidx=elem_addr)
                case _:
                    ltc.error(f"aSet does not support element type '{elem_type}' yet")
            tokens[i] = t.i32(0, ltc)
            return

        ltc.error("Indexed assignment requires a variable reference base")

    if not isinstance(tokens[i].node1, t.var_ref):
        ltc.error("Left side of assignment must be a variable reference")

    var_name = tokens[i].node1.val
    var_data = helper.locate_var_in_namespace(namespace, var_name, return_just_the_check=False)
    var_meta = var_data[0]
    var_type = var_meta["type"]
    mem_addr = var_meta["addr"]

    rhs = helper.resolve_node(tokens[i].node2, ltc, return_values, evaluate, execute_source_fn)

    # Strings can grow; if the new value doesn't fit, relocate and update the variable's address.
    if var_type == "string" and isinstance(rhs, t.string):
        # Determine current capacity if tracked.
        capacity = var_meta.get("capacity")
        new_len = len(rhs.val.encode("utf-8")) + 1
        if capacity is not None and new_len <= capacity:
            helper.load_to_mem(ltc, rhs, "string", memidx=mem_addr)
            tokens[i] = t.i32(0, ltc)
            return

        # If capacity is unknown or insufficient, allocate on the heap.
        string_copy = t.string(rhs.val)
        new_capacity = max(new_len, (capacity * 2) if capacity else 16)
        new_addr, alloc = helper.add_string_to_heap(string_copy, ltc.memory, ltc, capacity=new_capacity)
        var_meta["addr"] = new_addr
        var_meta["capacity"] = alloc
        tokens[i] = t.i32(0, ltc)
        return

    if var_type == "array":
        if not isinstance(rhs, t.array):
            ltc.error(f"Type mismatch in assignment to variable '{var_name}': expected array, got {type(rhs).__name__}")
        expected_elem_type = var_meta["elem_type"]
        expected_len = var_meta["length"]
        if rhs.arrayType != expected_elem_type:
            ltc.error(f"Array element type mismatch: expected {expected_elem_type}, got {rhs.arrayType}")
        if len(rhs.val) != expected_len:
            ltc.error(f"Array assignment size mismatch: expected length {expected_len}, got {len(rhs.val)}")
        rhs.size = expected_len
        helper.load_to_mem(ltc, rhs, "array", memidx=mem_addr)
    else:
        if type(rhs).__name__ != var_type:
            ltc.error(
                f"Type mismatch in assignment to variable '{var_name}': expected {var_type}, got {type(rhs).__name__}"
            )
        helper.load_to_mem(ltc, rhs, type(rhs).__name__, memidx=mem_addr)


    namespace[var_data[1]][var_name] = var_meta
    tokens[i] = t.i32(0, ltc)
    return

def resolve_bool_oper(ltc, tokens, i, oper: str, return_values, evaluate, execute_source_fn=None):
    t = ltc.t
    helper = ltc.helper
    lhs = helper.resolve_node(tokens[i].node1, ltc, return_values, evaluate, execute_source_fn)

    rhs = helper.resolve_node(tokens[i].node2, ltc, return_values, evaluate, execute_source_fn)

    if type(lhs).__name__ != type(rhs).__name__:
        ltc.error(f"Type mismatch in equality operator '{type(lhs).__name__}: {lhs.val} {oper} {type(rhs).__name__}: {rhs.val}'")

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
    helper = ltc.helper
    rhs = helper.resolve_node(tokens[i].node, ltc, return_values, evaluate, execute_source_fn)

    if not isinstance(rhs, t.boolean):
        ltc.error("Invert operator only inverts a boolean. To use truthiness, try using truthy operator ('!!').")

    tokens[i] = t.boolean(not rhs.val)

def resolve_free_oper(tokens, i, ltc):
    t = ltc.t
    helper = ltc.helper
    if not isinstance(tokens[i].node, t.var_ref):
        ltc.error(f"free operator must be a var_ref, not {type(tokens[i].node).__name__}")

    var_name = tokens[i].node.val
    tokens[i] = helper.dereference_var(ltc, tokens[i].node)
    var_data = helper.locate_var_in_namespace(ltc.namespace, var_name, return_just_the_check=False) # var_data is (metadata, scope_level)
    del ltc.namespace[var_data[1]][var_name]

def resolve_memloc_oper(tokens, i, ltc):
    t = ltc.t
    rhs = tokens[i].node

    if isinstance(rhs, ltc.n.index_oper):
        helper = ltc.helper
        base = rhs.node1
        idx = helper.resolve_node(rhs.node2, ltc, None, None, None)
        if not isinstance(idx, t.integer):
            ltc.error("Index must resolve to an integer")

        base_addr = None
        element_types = None
        elem_type = None

        if isinstance(base, t.var_ref):
            var_meta = helper.locate_var_in_namespace(ltc.namespace, base.val, return_just_the_check=False)[0]
            if var_meta is None:
                ltc.error(f"Variable '{base.val}' not found")
            base_addr = var_meta["addr"]
            if var_meta["type"] == "tuple":
                element_types = var_meta["element_types"]
            elif var_meta["type"] == "array":
                elem_type = var_meta["elem_type"]
            else:
                ltc.error("memloc indexing only supports tuple and array variables")
        elif isinstance(base, t.ltctuple):
            if not base.inmemory or base.memloc is None:
                ltc.error("memloc tuple indexing requires a tuple stored in memory")
            base_addr = base.memloc
            element_types = base.element_types
        elif isinstance(base, t.array):
            if not base.inmemory or base.memloc is None:
                ltc.error("memloc array indexing requires an array stored in memory")
            base_addr = base.memloc
            elem_type = base.arrayType
        else:
            ltc.error("memloc indexing only supports tuple and array bases")

        index_val = idx.val
        if element_types is not None:
            if index_val < 0 or index_val >= len(element_types):
                ltc.error(f"Tried to index a tuple of size {len(element_types)} with an index of {index_val}")
            offset = sum(helper.get_ltc_type_size(t, ltc) for t in element_types[:index_val])
            elem_addr = base_addr + offset
        else:
            if index_val < 0:
                ltc.error("Array index cannot be negative for memloc indexing")
            offset = index_val * helper.get_ltc_type_size(elem_type, ltc)
            elem_addr = base_addr + offset

        tokens[i] = t.ptr(elem_addr, ltc)
        return

    if not isinstance(rhs, t.ltc_type | t.var_ref):
        ltc.error(f"memloc operator takes a ltc_type or var_ref, not '{type(tokens[i].node).__name__}'")

    rhs = ltc.helper.resolve_node(rhs, ltc, None, None, None) # can just pass None for the last three arguments since resolve_node will not use them when resolving a var_ref

    # Strings are dynamic and stack-lifetime; take a stable heap copy for '&string'.
    if isinstance(rhs, t.string):
        if rhs.inmemory and rhs.memloc is not None and rhs.memloc >= ltc.hp:
            tokens[i] = t.ptr(rhs.memloc, ltc)
            return
        string_copy = t.string(rhs.val)
        addr, _ = ltc.helper.add_string_to_heap(string_copy, ltc.memory, ltc)
        tokens[i] = t.ptr(addr, ltc)
        return

    if not rhs.inmemory:
        ltc.error(f"Object '{rhs.val}' of type '{type(rhs).__name__}' is not stored in memory and thus does not have a memory address. This error exists only in the interpreter version.")

    tokens[i] = t.ptr(rhs.memloc, ltc)

def resolve_dot_oper(tokens, i, ltc, return_values, evaluate, execute_source_fn=None):
    shelper = ltc.shelper
    helper = ltc.helper
    t = ltc.t

    struct_obj = helper.resolve_node(tokens[i].node1, ltc, return_values, evaluate, execute_source_fn)
    field_name = tokens[i].node2.val

    if not isinstance(struct_obj, t.struct_instance):
        ltc.error("dot operator expects a struct instance on the left-hand side")
    if not struct_obj.inmemory or struct_obj.memloc is None:
        ltc.error("Struct instance must be stored in memory to access fields with '.'")

    tokens[i] = shelper.read_struct_field_from_memory(
        ltc,
        struct_obj.struct_name,
        field_name,
        struct_obj.memloc,
    )
