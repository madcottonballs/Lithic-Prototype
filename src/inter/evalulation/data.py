def resolve_let(tokens, i, ltc) -> None:
    t = ltc.t
    helper = ltc.helper
    if len(tokens[i].args) not in (2, 4):
        raise SyntaxError("let expects: let [type] [varname] OR let [type] [varname] = [value]")

    let_type = len(tokens[i].args)
    var_type_arg = tokens[i].args[0]
    var_name_arg = tokens[i].args[1]
    var_value_arg = None

    if not isinstance(var_name_arg, t.token):
        raise TypeError("Second argument to let must be a variable name token")

    var_mem_addr = ltc.sp

    if let_type == 4:
        equals_arg = tokens[i].args[2]
        var_value_arg = tokens[i].args[3]

        if not (isinstance(equals_arg, t.token) and equals_arg.val == "="):
            raise SyntaxError("let expects '=' as the third argument")

        if type(var_value_arg) != ltc.types[var_type_arg.val]:
            raise TypeError (
                f"Type of value '{type(var_value_arg).__name__}' does not match expected type '{var_type_arg.val}'"
            )

        if isinstance(var_type_arg, t.array):
            if var_value_arg.arrayType != var_type_arg.arrayType:
                raise TypeError(
                    f"Let statement tried to declare {var_type_arg.arrayType}[] but was assigned {var_value_arg.arrayType}[]"
                )
            if len(var_value_arg.val) != var_type_arg.size:
                raise SyntaxError(
                    f"Let statement tried to declare {var_type_arg.arrayType}[{var_type_arg.size}] "
                    f"but was assigned {var_value_arg.arrayType}[{len(var_value_arg.val)}]"
                )
            helper.load_to_mem(ltc, var_value_arg, "array")
        else:
            helper.load_to_mem(ltc, var_value_arg, var_type_arg.val)
    else:
        if isinstance(var_type_arg, t.array):
            empty_array = t.array([], arrayType=var_type_arg.arrayType, parse=False)
            empty_array.size = var_type_arg.size
            helper.load_to_mem(ltc, empty_array, "array")
        else:
            helper.load_to_mem(ltc, helper.recieve_empty_form(ltc, var_type_arg.val), var_type_arg.val)
    
    if isinstance(var_type_arg, t.array):
        ltc.namespace[len(ltc.namespace) - 1][var_name_arg.val] = {
            "type": "array",
            "addr": var_mem_addr,
            "length": var_type_arg.size,
            "elem_type": var_type_arg.arrayType,
        }
    elif isinstance(var_type_arg, t.ltctuple) or (isinstance(var_type_arg, t.token) and var_type_arg.val == "tuple"):
        tuple_element_types = None
        if isinstance(var_type_arg, t.ltctuple):
            tuple_element_types = var_type_arg.element_types
        elif isinstance(var_value_arg, t.ltctuple):
            tuple_element_types = var_value_arg.element_types

        if tuple_element_types is None:
            raise TypeError("Tuple declarations require element types (use makeTuple(...) or an explicit tuple type).")

        ltc.namespace[len(ltc.namespace) - 1][var_name_arg.val] = {
            "type": "tuple",
            "addr": var_mem_addr,
            "element_types": tuple_element_types,
        }
    else:
        ltc.namespace[len(ltc.namespace) - 1][var_name_arg.val] = {
            "type": var_type_arg.val,
            "addr": var_mem_addr,
        }

    tokens[i] = t.i32(0)

def resolve_typeof(tokens, i, ltc) -> None:
    t = ltc.t
    if len(tokens[i].args) != 1:
        raise SyntaxError("typeof expects exactly one argument")
    tokens[i] = t.string(type(tokens[i].args[0]).__name__)

def resolve_sizeof(tokens, i, ltc) -> None:
    t = ltc.t
    helper = ltc.helper
    if len(tokens[i].args) != 1:
        raise SyntaxError("sizeof expects exactly one argument")
    arg = tokens[i].args[0]
    match type(arg):
        case t.string:
            tokens[i] = t.i32(len(arg.val) + 1)
        case t.array:
            tokens[i] = t.i32(arg.get_size())
        case t.ltctuple:
            tokens[i] = t.i32(arg.get_size())
        case t.i32 | t.i64 | t.i8 | t.i16 | t.u32 | t.u64 | t.u8 | t.u16 | t.boolean | t.char | t.ptr:
            tokens[i] = t.i32(helper.get_ltc_type_size(type(arg).__name__))
        case t.token:
            if arg.val in ltc.types:
                type_name = arg.val
                if type_name in ("string", "array", "tuple", "ltctuple"):
                    raise TypeError(f"sizeof cannot be used on dynamically sized types like '{type_name}' without an instance. Use sizeof(var) instead of sizeof(type) for these types.")
                tokens[i] = t.i32(helper.get_ltc_type_size(type_name))
            else:
                raise TypeError(f"Token argument to sizeof must be a valid type name, got '{arg.val}'")
        case _:
            raise TypeError(f"Unsupported argument type for sizeof: {type(arg).__name__}")

def resolve_concat(tokens, i, ltc) -> None:
    t = ltc.t
    if len(tokens[i].args) < 2:
        raise SyntaxError("concat expects at least two arguments")
    concatenated = None
    expected_type = None
    for arg in tokens[i].args:
        if expected_type is None: # set the expected type based on the first argument
            expected_type = type(arg)
        if type(arg) != expected_type: # enforce that all arguments are of the same type
            raise TypeError(f"Argument type mismatch in concat: expected {expected_type.__name__}, got {type(arg).__name__}")
        
        if not isinstance(arg, expected_type):
            raise TypeError(f"Unsupported argument type for concat: {type(arg).__name__}")
        
        if isinstance(arg, t.string):
            if concatenated is None:
                concatenated = arg.val # initialize concatenated as a string if the first argument is a string
            else:
                concatenated += arg.val # concatenate strings
        elif isinstance(arg, t.array):
            if concatenated is None:
                expected_array_type = arg.arrayType
                concatenated = arg.val # initialize concatenated as an array if the first argument is an array
            else:
                if arg.arrayType != expected_array_type:
                    raise TypeError(f"Array type mismatch in concat: expected {expected_array_type}, got {arg.arrayType}")
                concatenated.extend(arg.val) # concatenate arrays
        elif isinstance(arg, t.ltctuple):
            if concatenated is None:
                concatenated = arg.val # initialize concatenated as a tuple if the first argument is a tuple
                concatenated_types = arg.element_types
            else:
                concatenated += (arg.val) # concatenate tuples
                concatenated_types += (arg.element_types)
    
    if expected_type == t.ltctuple:
        tokens[i] = t.ltctuple(ltc, elements=tuple(concatenated), element_types=concatenated_types)
    elif expected_type == t.array:
        tokens[i] = t.array(concatenated, arrayType=arg.arrayType, parse=False)
    else: # strings & arrays
        tokens[i] = expected_type(concatenated)

def resolve_cast_function(tokens: list, i: int, ltc, return_values, evaluate, execute_source_fn):
    t = ltc.t
    if len(tokens[i].args) != 2:
        raise SyntaxError(f"cast expects exactly two arguments, not {len(tokens[i].args)}")
    
    # readability
    cast_target: str = tokens[i].args[1].val
    source_object: object = tokens[i].args[0]
    helper = ltc.helper
    # Resolve nodes so casts work with expressions and @(...) results.
    source_object = helper.resolve_node(source_object, ltc, return_values, evaluate, execute_source_fn)
    if isinstance(source_object, ltc.n.at_func_return):
        source_object = source_object.val
    # only used for integer casts but this avoids rewriting
    ltc_target_int_class = ltc.types[cast_target] # finds the ltc typerizer class referenced by the cast_target string (if cast_target = "i32", ltc_target_int_class = t.i32)

    # execution

    match cast_target: # casting to

        case "i32"|"i64"| "i8" | "i16" | "u32" | "u64" | "u8" | "u16": # cast to integer
            match type(source_object):
                case t.i32 | t.i64 | t.i8 | t.i16 | t.u32 | t.u64 | t.u8 | t.u16 | t.ptr: # integer | ptr -> integer
                    tokens[i] = ltc_target_int_class(source_object.val)
                case t.boolean: # bool -> integer
                    if source_object.val == True: # for readability
                        tokens[i] = ltc_target_int_class(1)
                    else:
                        tokens[i] = ltc_target_int_class(0)
                case t.string: # string -> integer
                    try:
                        int_rep = int(source_object.val)
                    except ValueError:
                        raise ValueError(f"Cannot cast string '{source_object.val}' to integer")
                    tokens[i] = ltc_target_int_class(int_rep)
                case t.char: # char -> integer
                    try:
                        int_rep = ord(source_object.val)
                    except ValueError:
                        raise ValueError(f"Cannot cast char '{source_object.val}' to integer")
                    tokens[i] = ltc_target_int_class(int_rep)
                case _:
                    raise TypeError(f"Cannot cast object of type '{type(tokens[i].args[0]).__name__}' to type '{cast_target}'")
        case "boolean": # cast to boolean
            match type(source_object):
                case t.i32 | t.i64 | t.i8 | t.i16 | t.u32 | t.u64 | t.u8 | t.u16: # integer -> boolean
                    if source_object.val == 0:
                        tokens[i] = t.boolean(False)
                    else:                        
                        tokens[i] = t.boolean(True)
                case t.boolean: # boolean -> boolean (no-op cast)
                    tokens[i] = source_object
                case t.string: # string -> boolean
                    if source_object.val == "": # empty string is falsey, all other strings are truthy
                        tokens[i] = t.boolean(False)
                    else:
                        tokens[i] = t.boolean(True)
                case t.char: # char -> boolean
                    if source_object.val == "": # empty char is falsey, all other characters are truthy
                        tokens[i] = t.boolean(False)
                    else:
                        tokens[i] = t.boolean(True)
                case t.ptr: # ptr -> boolean
                    if source_object.val == 0: # null pointer is falsey, all other pointers are truthy
                        tokens[i] = t.boolean(False)
                    else:
                        tokens[i] = t.boolean(True)
                case _:
                    raise TypeError(f"Cannot cast object of type '{type(tokens[i].args[0]).__name__}' to type '{cast_target}'")
        case "string":
            match type(source_object):
                case t.i32 | t.i64 | t.i8 | t.i16 | t.u32 | t.u64 | t.u8 | t.u16: # integer -> string
                    tokens[i] = t.string(str(source_object.val))
                case t.boolean: # boolean -> string
                    tokens[i] = t.string(str(source_object.val))
                case t.string: # string -> string
                    tokens[i] = source_object
                case t.char: # char -> string
                    tokens[i] = t.string(source_object.val)
                case t.ptr: # ptr -> string
                    tokens[i] = t.string(str(source_object.val))
                case _:
                    raise TypeError(f"Cannot cast object of type '{type(tokens[i].args[0]).__name__}' to type '{cast_target}'")
        case "char":
            match type(source_object):
                case t.i32 | t.i64 | t.i8 | t.i16 | t.u32 | t.u64 | t.u8 | t.u16: # integer -> char
                    if 0 <= source_object.val <= 255: # valid ascii code point range
                        tokens[i] = t.char(chr(source_object.val))
                    else:
                        raise ValueError(f"Integer value '{source_object.val}' is not a valid ASCII code point")
                case t.string: # string -> char
                    if len(source_object.val) == 1:
                        tokens[i] = t.char(source_object.val)
                    else:
                        raise ValueError(f"String value '{source_object.val}' is not a valid character")
                case _:
                    raise TypeError(f"Cannot cast object of type '{type(tokens[i].args[0]).__name__}' to type '{cast_target}'")
        case "ptr":
            match type(source_object):
                case t.i32 | t.i64 | t.i8 | t.i16 | t.u32 | t.u64 | t.u8 | t.u16:
                    tokens[i] = t.ptr(source_object.val)
                case t.string:
                    try:
                        int_rep = int(source_object.val)
                    except ValueError:
                        raise ValueError(f"Cannot cast string '{source_object.val}' to ptr")
                    tokens[i] = t.ptr(int_rep)
                case t.ptr:
                    tokens[i] = source_object
                case _:
                    raise TypeError(f"Cannot cast object of type '{type(tokens[i].args[0]).__name__}' to type '{cast_target}'")
        case _:
            raise TypeError(f"Unsupported cast target type: '{cast_target}'")

def resolve_deref(tokens, i, ltc) -> None:
    t = ltc.t
    helper = ltc.helper
    n = ltc.n
    if len(tokens[i].args) != 3:
        raise SyntaxError("@ expects exactly three arguments: @(ptr, type, index)")
    
    ptr_arg = tokens[i].args[0]
    type_arg = tokens[i].args[1]
    index_arg = tokens[i].args[2]

    if not isinstance(ptr_arg, t.ptr):
        raise TypeError(f"First argument to @ must be a pointer, got {type(ptr_arg).__name__}")
    if (not isinstance(type_arg, t.token)) or (not type_arg.val in ltc.types.keys()):
        raise TypeError(f"Second argument to @ must be a type name, instead got {type_arg.val}")
    if not isinstance(index_arg, t.integer):
        raise TypeError(f"Third argument to @ must be an integer, got {type(index_arg).__name__}")

    match type_arg.val:
        # note: all types that are supported by @ must have .read_from_memory implemented in their ltc type class, which is used here to read the byte value from memory
        case "i32" | "i64" | "i8" | "i16" | "u32" | "u64" | "u8" | "u16":
            type_size = helper.integer_type_to_size(type_arg.val)
        case "boolean":
            type_size = 1
        case "char":
            type_size = 1
        case _:
            raise TypeError(f"Unsupported type for @ operator: '{type_arg.val}'. Only fixed-length types are supported for now.")
    
    ptr_offset: int = ptr_arg.val + (index_arg.val * type_size) # calculate the memory offset to read from by adding the base pointer value and the index multiplied by the size of the type being dereferenced. This allows for pointer arithmetic to access elements in an array or fields in a struct/tuple.

    ptr_deref = helper.read_ltc_type_from_mem(ltc.memory, ptr_offset, type_arg.val, ltc) # returns the obj read from memory

    tokens[i] = n.at_func_return(ptr_deref, ptr_offset, type_size, index_arg.val) # create an at_func_return_obj to hold the dereferenced value along with the original pointer and type size for use in assign_oper

def resolve_tset(tokens, i, ltc) -> None:
    t = ltc.t
    helper = ltc.helper
    if len(tokens[i].args) != 3:
        raise SyntaxError("tSet expects exactly three arguments: tSet(tupleVar, index, value)")

    tuple_ref = tokens[i].args[0]
    tuple_index = tokens[i].args[1]
    new_value = helper.resolve_node(tokens[i].args[2], ltc, [], ltc.evaluator.evaluate, None)
    element_types = None
    base_addr = None

    if not isinstance(tuple_index, t.integer):
        raise TypeError("tSet index must be a integer")

    # sets the element_types and base_addr variables
    if not isinstance(tuple_ref, t.ltctuple):
        raise TypeError("tSet first argument must be a tuple reference")

    if not tuple_ref.inmemory or tuple_ref.memloc is None:
        raise TypeError("tSet first argument must reference a tuple variable in memory")
    
    element_types = tuple_ref.element_types

    if tuple_index.val < 0: # example: (4, 2, 9)[-1] -> 9
        tuple_index.val = tuple_index.val % len(element_types)  # support negative indexing for tuples
    
    base_addr = tuple_ref.memloc
    tuple_ref.update_element_in_memory(ltc, base_addr, tuple_index.val, new_value, element_types)

    tokens[i] = t.i32(0)

def resolve_aset(tokens, i, ltc) -> None:
    t = ltc.t
    helper = ltc.helper
    if len(tokens[i].args) != 3:
        raise SyntaxError("aSet expects exactly three arguments: aSet(arrayVar, index, value)")

    array_ref = tokens[i].args[0]
    array_index = tokens[i].args[1]
    new_value = helper.resolve_node(tokens[i].args[2], ltc, [], ltc.evaluator.evaluate, None)

    if not isinstance(array_ref, t.var_ref):
        raise TypeError("aSet first argument must be an array variable reference")
    if not isinstance(array_index, t.integer):
        raise TypeError("aSet index must be a integer")
    
    if array_index.val < 0:
        raise SyntaxError("aSet index cannot be negative")

    var_data = helper.locate_var_in_namespace(ltc.namespace, array_ref.val, return_just_the_check=False)
    var_meta = var_data[0]
    if var_meta is None:
        raise NameError(f"Variable '{array_ref.val}' not found")
    if var_meta["type"] != "array":
        raise TypeError("aSet first argument must reference an array variable")

    elem_type = var_meta["elem_type"]
    array_len = var_meta["length"]
    if array_index.val < 0:
        array_index.val = array_index.val % array_len

    if array_index.val >= array_len:
        raise SyntaxError(f"Array index out of range: {array_index.val} for length {array_len}")

    if type(new_value).__name__ != elem_type:
        raise TypeError(f"aSet type mismatch: expected {elem_type}, got {type(new_value).__name__}")

    base_addr = var_meta["addr"]
    match elem_type:
        case "i32" | "i64" | "i8" | "i16" | "u32" | "u64" | "u8" | "u16" | "ptr":
            elem_addr = base_addr + (array_index.val * helper.get_ltc_type_size(elem_type))
            helper.load_to_mem(ltc, new_value, elem_type, memidx=elem_addr)
        case "boolean":
            elem_addr = base_addr + array_index.val
            helper.load_to_mem(ltc, new_value, "boolean", memidx=elem_addr)
        case "char":
            elem_addr = base_addr + array_index.val
            helper.load_to_mem(ltc, new_value, "char", memidx=elem_addr)
        case _:
            raise TypeError(f"aSet does not support element type '{elem_type}' yet")

    tokens[i] = t.i32(0)

def resolve_maketuple(tokens, i, ltc) -> None:
    t = ltc.t
    if len(tokens[i].args) < 1:
        raise SyntaxError("makeTuple expects at least one argument")
    element_types = []
    for arg in tokens[i].args:
        if not isinstance(arg, t.token) or arg.val not in ltc.types:
            raise TypeError(f"makeTuple arguments must be type name tokens, got '{arg}'")
        element_types.append(arg.val)

    tokens[i] = t.ltctuple(ltc, elements=(), element_types=element_types)

def resolve_tag(tokens, i, ltc) -> None:
    """Used for optionally tagging pointers with type information. Type info is stored in variable metadata."""
    t = ltc.t
    if len(tokens[i].args) != 2:
        raise SyntaxError("tag expects exactly two arguments: tag(ptr, type)")
    ptr_arg = tokens[i].args[0]
    type_arg = tokens[i].args[1]
    if not isinstance(ptr_arg, t.ptr):
        raise TypeError(f"First argument to tag must be a pointer, got {type(ptr_arg).__name__}")
    if not isinstance(type_arg, t.token) or type_arg.val not in ltc.types:
        raise TypeError(f"Second argument to tag must be a valid type, got {type(type_arg).__name__}")

    if ptr_arg.var_name == None:
        raise ValueError("Only pointer variables can be tagged, but got an unreferenced pointer")
    
    # check if the variable exists, it should but let's be safe
    var_data = ltc.helper.locate_var_in_namespace(ltc.namespace, ptr_arg.var_name, return_just_the_check=False)
    (var_meta, scope_level) = var_data
    if var_meta is None:
        raise NameError(f"Variable '{ptr_arg.var_name}' not found for tagging")
    
    ltc.namespace[scope_level][ptr_arg.var_name]["tag"] = type_arg.val # store the tag in the variable's metadata
    tokens[i] = t.i32(0) # return 0 for success (could also return the pointer itself or the tag if desired)

def resolve_untag(tokens, i, ltc) -> None:
    """Used for optionally untagging pointers with type information. Type info is stored in variable metadata."""
    t = ltc.t
    if len(tokens[i].args) != 1:
        raise SyntaxError("untag expects exactly one argument: untag(ptr)")
    ptr_arg = tokens[i].args[0]
    if not isinstance(ptr_arg, t.ptr):
        raise TypeError(f"Argument to untag must be a pointer, got {type(ptr_arg).__name__}")

    if ptr_arg.var_name == None:
        raise ValueError("Only pointer variables can be untagged, but got an unreferenced pointer")
    
    # check if the variable exists, it should but let's be safe
    var_data = ltc.helper.locate_var_in_namespace(ltc.namespace, ptr_arg.var_name, return_just_the_check=False)
    (var_meta, scope_level) = var_data
    if var_meta is None:
        raise NameError(f"Variable '{ptr_arg.var_name}' not found for untagging")
    
    if "tag" in ltc.namespace[scope_level][ptr_arg.var_name]:
        del ltc.namespace[scope_level][ptr_arg.var_name]["tag"] # remove the tag from the variable's metadata
    tokens[i] = t.i32(0) # return 0 for success (could also return the pointer itself if desired)

def resolve_gettypetag(tokens, i, ltc) -> None:
    """Used for retrieving the type tag from a tagged pointer."""
    t = ltc.t
    if len(tokens[i].args) != 1:
        raise SyntaxError("getTypeTag expects exactly one argument: getTypeTag(ptr)")
    ptr_arg = tokens[i].args[0]
    if not isinstance(ptr_arg, t.ptr):
        raise TypeError(f"Argument to getTypeTag must be a pointer, got {type(ptr_arg).__name__}")

    if ptr_arg.var_name == None:
        raise ValueError("Only pointer variables can have type tags, but got an unreferenced pointer")
    
    # check if the variable exists, it should but let's be safe
    var_data = ltc.helper.locate_var_in_namespace(ltc.namespace, ptr_arg.var_name, return_just_the_check=False)
    (var_meta, scope_level) = var_data
    if var_meta is None:
        raise NameError(f"Variable '{ptr_arg.var_name}' not found for retrieving type tag")
    
    if "tag" not in ltc.namespace[scope_level][ptr_arg.var_name]:
        raise ValueError(f"Variable '{ptr_arg.var_name}' is not tagged")
    
    tokens[i] = t.string(ltc.namespace[scope_level][ptr_arg.var_name]["tag"]) # return the tag as a token for easy comparison in user code

def resolve_malloctype(tokens, i, ltc) -> None:
    if len(tokens[i].args) != 2:
        raise SyntaxError("mallocType expects exactly two arguments: mallocType(type, count)")
    type_arg = tokens[i].args[0]
    count_arg = tokens[i].args[1]
    if not isinstance(type_arg, ltc.t.token) or type_arg.val not in ltc.types:
        raise TypeError(f"mallocType type argument must be a valid type, got {type(type_arg).__name__}")
    if not isinstance(count_arg, ltc.t.integer):
        raise TypeError(f"mallocType count argument must be an integer, got {type(count_arg).__name__}")

    num_of_bytes = ltc.helper.get_ltc_type_size(type_arg.val) * count_arg.val

    ltc.helper.malloc(num_of_bytes, ltc)

    tokens[i] = ltc.t.ptr(ltc.hp) 

def resolve_malloc(tokens, i, ltc) -> None:
    if len(tokens[i].args) != 1:
        raise SyntaxError("malloc expects exactly one argument")
    arg = tokens[i].args[0]
    if not isinstance(arg, ltc.t.integer):
        raise TypeError(f"malloc size argument must be an integer, got {type(arg).__name__}")
    
    ltc.helper.malloc(arg.val, ltc)

    tokens[i] = ltc.t.ptr(ltc.hp) 
