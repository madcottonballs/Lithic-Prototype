def resolve_let(tokens, i, ltc) -> None:
    t = ltc.t
    helper = ltc.helper
    if len(tokens[i].args) not in (2, 4):
        ltc.error("let expects: let [type] [varname] OR let [type] [varname] = [value]")

    let_type = len(tokens[i].args)
    var_type_arg = tokens[i].args[0]
    var_name_arg = tokens[i].args[1]
    var_value_arg = None

    if not isinstance(var_name_arg, t.token):
        ltc.error("Second argument to let must be a variable name token")

    var_mem_addr = ltc.sp

    if let_type == 4:
        equals_arg = tokens[i].args[2]
        var_value_arg = tokens[i].args[3]

        if not (isinstance(equals_arg, t.token) and equals_arg.val == "="):
            ltc.error("let expects '=' as the third argument")

        if type(var_value_arg) != ltc.types[var_type_arg.val]:
            ltc.error(
                f"Type of value '{type(var_value_arg).__name__}' does not match expected type '{var_type_arg.val}'"
            )

        if isinstance(var_type_arg, t.array):
            helper.load_to_mem(ltc, var_value_arg, "array")
            # vars stored for unified meta data reconstruction at end
            array_type = var_type_arg.arrayType
            array_length = var_type_arg.get_size()
        elif isinstance(var_type_arg, t.token) and var_type_arg.val == "array":
            if not isinstance(var_value_arg, t.array):
                ltc.error("let array expects an array literal or array value on the right hand side")
            # Ensure array literal is parsed so arrayType is inferred.
            var_value_arg.parse(ltc)
            array_type = var_value_arg.arrayType
            if array_type is None:
                ltc.error("let array expects a non-empty array literal so element type can be inferred")
            helper.load_to_mem(ltc, var_value_arg, "array")
            array_length = var_value_arg.get_size()
        elif isinstance(var_type_arg, t.token) and var_type_arg.val == "string":
            # Store strings on heap to avoid stack lifetime issues.
            string_copy = t.string(var_value_arg.val)
            var_mem_addr, capacity = helper.add_string_to_heap(string_copy, ltc.memory, ltc)
        else:
            helper.load_to_mem(ltc, var_value_arg, var_type_arg.val)
    else:
        if isinstance(var_type_arg, t.array):
            empty_array = t.array([], ltc, arrayType=var_type_arg.arrayType, parse=False)
            empty_array.size = var_type_arg.size
            helper.load_to_mem(ltc, empty_array, "array")
            # vars stored for unified meta data reconstruction at end
            array_type = var_type_arg.arrayType
            array_length = var_type_arg.size
        elif isinstance(var_type_arg, t.token) and var_type_arg.val == "array":
            ltc.error("let array requires an initializer; use let array x = [..];")
        elif isinstance(var_type_arg, t.token) and var_type_arg.val == "string":
            # Empty strings start on the stack; they'll migrate to heap if they grow.
            helper.load_to_mem(ltc, t.string(""), "string")
        else:
            helper.load_to_mem(ltc, helper.recieve_empty_form(ltc, var_type_arg.val), var_type_arg.val)
    
    if isinstance(var_type_arg, t.array) or (isinstance(var_type_arg, t.token) and var_type_arg.val == "array"):
        ltc.namespace[len(ltc.namespace) - 1][var_name_arg.val] = {
            "type": "array",
            "addr": var_mem_addr,
            "length": array_length,
            "elem_type": array_type,
        }
    elif isinstance(var_type_arg, t.ltctuple) or (isinstance(var_type_arg, t.token) and var_type_arg.val == "tuple"):
        tuple_element_types = None
        if isinstance(var_type_arg, t.ltctuple):
            tuple_element_types = var_type_arg.element_types
        elif isinstance(var_value_arg, t.ltctuple):
            tuple_element_types = var_value_arg.element_types

        if tuple_element_types is None:
            ltc.error("Tuple declarations require element types (use makeTuple(...) or an explicit tuple type).")

        ltc.namespace[len(ltc.namespace) - 1][var_name_arg.val] = {
            "type": "tuple",
            "addr": var_mem_addr,
            "element_types": tuple_element_types,
        }
    else: # generic case for primitives and other types
        entry = {
            "type": var_type_arg.val,
            "addr": var_mem_addr,
        }
        if isinstance(var_type_arg, t.token) and var_type_arg.val == "string" and "capacity" in locals(): # strings need their capacity stored
            entry["capacity"] = capacity
        ltc.namespace[len(ltc.namespace) - 1][var_name_arg.val] = entry

    tokens[i] = t.i32(0, ltc)

def resolve_typeof(tokens, i, ltc) -> None:
    t = ltc.t
    if len(tokens[i].args) != 1:
        ltc.error("typeof expects exactly one argument")
    tokens[i] = t.string(type(tokens[i].args[0]).__name__)

def resolve_sizeof(tokens, i, ltc) -> None:
    t = ltc.t
    helper = ltc.helper
    if len(tokens[i].args) != 1:
        ltc.error("sizeof expects exactly one argument")
    arg = tokens[i].args[0]
    match type(arg):
        case t.string:
            tokens[i] = t.i32(len(arg.val) + 1)
        case t.array:
            tokens[i] = t.i32(arg.get_size())
        case t.ltctuple:
            tokens[i] = t.i32(arg.get_size())
        case t.i32 | t.i64 | t.i8 | t.i16 | t.u32 | t.u64 | t.u8 | t.u16 | t.boolean | t.char | t.ptr:
            tokens[i] = t.i32(helper.get_ltc_type_size(type(arg).__name__, ltc))
        case t.token:
            if arg.val in ltc.types:
                type_name = arg.val
                if type_name in ("string", "array", "tuple", "ltctuple"):
                    ltc.error(f"sizeof cannot be used on dynamically sized types like '{type_name}' without an instance. Use sizeof(var) instead of sizeof(type) for these types.")
                tokens[i] = t.i32(helper.get_ltc_type_size(type_name, ltc))
            else:
                ltc.error(f"Token argument to sizeof must be a valid type name, got '{arg.val}'")
        case _:
            ltc.error(f"Unsupported argument type for sizeof: {type(arg).__name__}")

def resolve_concat(tokens, i, ltc) -> None:
    t = ltc.t
    if len(tokens[i].args) < 2:
        ltc.error("concat expects at least two arguments")
    concatenated = None
    expected_type = None
    for arg in tokens[i].args:
        if expected_type is None: # set the expected type based on the first argument
            if isinstance(arg, t.char):
                expected_type = t.string
                concatenated = arg.val
                continue
            expected_type = type(arg)

        # Allow char to participate in string concatenation.
        if expected_type is t.string and isinstance(arg, t.char):
            concatenated = ("" if concatenated is None else concatenated) + arg.val
            continue

        if type(arg) != expected_type: # enforce that all arguments are of the same type
            ltc.error(f"Argument type mismatch in concat: expected {expected_type.__name__}, got {type(arg).__name__}")
        
        if not isinstance(arg, expected_type):
            ltc.error(f"Unsupported argument type for concat: {type(arg).__name__}")
        
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
                    ltc.error(f"Array type mismatch in concat: expected {expected_array_type}, got {arg.arrayType}")
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
        tokens[i] = t.array(concatenated, ltc, arrayType=arg.arrayType, parse=False)
    else: # strings & arrays
        tokens[i] = expected_type(concatenated)

def resolve_cast_function(tokens: list, i: int, ltc, return_values, evaluate, execute_source_fn):
    t = ltc.t
    if len(tokens[i].args) != 2:
        ltc.error(f"cast expects exactly two arguments, not {len(tokens[i].args)}")
    
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
                        ltc.error(f"Cannot cast string '{source_object.val}' to integer")
                    tokens[i] = ltc_target_int_class(int_rep)
                case t.char: # char -> integer
                    try:
                        int_rep = ord(source_object.val)
                    except ValueError:
                        ltc.error(f"Cannot cast char '{source_object.val}' to integer")
                    tokens[i] = ltc_target_int_class(int_rep)
                case _:
                    ltc.error(f"Cannot cast object of type '{type(tokens[i].args[0]).__name__}' to type '{cast_target}'")
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
                    ltc.error(f"Cannot cast object of type '{type(tokens[i].args[0]).__name__}' to type '{cast_target}'")
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
                    ltc.error(f"Cannot cast object of type '{type(tokens[i].args[0]).__name__}' to type '{cast_target}'")
        case "char":
            match type(source_object):
                case t.i32 | t.i64 | t.i8 | t.i16 | t.u32 | t.u64 | t.u8 | t.u16: # integer -> char
                    if 0 <= source_object.val <= 255: # valid ascii code point range
                        tokens[i] = t.char(chr(source_object.val))
                    else:
                        ltc.error(f"Integer value '{source_object.val}' is not a valid ASCII code point")
                case t.string: # string -> char
                    if len(source_object.val) == 1:
                        tokens[i] = t.char(source_object.val)
                    else:
                        ltc.error(f"String value '{source_object.val}' is not a valid character")
                case _:
                    ltc.error(f"Cannot cast object of type '{type(tokens[i].args[0]).__name__}' to type '{cast_target}'")
        case "ptr":
            match type(source_object):
                case t.i32 | t.i64 | t.i8 | t.i16 | t.u32 | t.u64 | t.u8 | t.u16:
                    tokens[i] = t.ptr(source_object.val)
                case t.string:
                    try:
                        int_rep = int(source_object.val)
                    except ValueError:
                        ltc.error(f"Cannot cast string '{source_object.val}' to ptr")
                    tokens[i] = t.ptr(int_rep)
                case t.ptr:
                    tokens[i] = source_object
                case _:
                    ltc.error(f"Cannot cast object of type '{type(tokens[i].args[0]).__name__}' to type '{cast_target}'")
        case _:
            ltc.error(f"Unsupported cast target type: '{cast_target}'")

def resolve_deref(tokens, i, ltc) -> None:
    t = ltc.t
    helper = ltc.helper
    n = ltc.n
    if len(tokens[i].args) == 2:
        index_operation = False # 2 args, no index provided, just dereference the pointer as is (index defaults to 0)
    if len(tokens[i].args) != 3:
        ltc.error("@ expects exactly three arguments: @(ptr, type, index) or @(ptr, type) for dereferencing without indexing (index defaults to 0)")
    else:
        index_operation = True # 3 args

    ptr_arg = tokens[i].args[0]
    type_arg = tokens[i].args[1]
    if index_operation:
        index_arg = tokens[i].args[2]
    else:
        index_arg = t.i32(0) # default index value for non-indexed dereference

    if not isinstance(ptr_arg, t.ptr):
        ltc.error(f"First argument to @ must be a pointer, got {type(ptr_arg).__name__}")
    if (not isinstance(type_arg, t.token)) or (not type_arg.val in ltc.types.keys()):
        ltc.error(f"Second argument to @ must be a type name, instead got {type_arg.val}")
    if not isinstance(index_arg, t.integer):
        ltc.error(f"Third argument to @ must be an integer, got {type(index_arg).__name__}")

    if type_arg.val in ltc.primitives:
        type_size = helper.get_ltc_type_size(type_arg.val, ltc)
    else:
        ltc.error(f"Unsupported type for @ operator: '{type_arg.val}'. Only fixed-length types are supported for now.")
    
    ptr_offset: int = ptr_arg.val + (index_arg.val * type_size) # calculate the memory offset to read from by adding the base pointer value and the index multiplied by the size of the type being dereferenced. This allows for pointer arithmetic to access elements in an array or fields in a struct/tuple.

    ptr_deref = helper.read_ltc_type_from_mem(ltc.memory, ptr_offset, type_arg.val, ltc) # returns the obj read from memory

    tokens[i] = n.at_func_return(ptr_deref, ptr_offset, type_size, index_arg.val) # create an at_func_return_obj to hold the dereferenced value along with the original pointer and type size for use in assign_oper

def resolve_tset(tokens, i, ltc) -> None:
    t = ltc.t
    helper = ltc.helper
    if len(tokens[i].args) != 3:
        ltc.error("tSet expects exactly three arguments: tSet(tupleVar, index, value)")

    tuple_ref = tokens[i].args[0]
    tuple_index = tokens[i].args[1]
    new_value = helper.resolve_node(tokens[i].args[2], ltc, [], ltc.evaluator.evaluate, None)
    element_types = None
    base_addr = None

    if not isinstance(tuple_index, t.integer):
        ltc.error("tSet index must be a integer")

    # sets the element_types and base_addr variables
    if not isinstance(tuple_ref, t.ltctuple):
        ltc.error("tSet first argument must be a tuple reference")

    if not tuple_ref.inmemory or tuple_ref.memloc is None:
        ltc.error("tSet first argument must reference a tuple variable in memory")
    
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
        ltc.error("aSet expects exactly three arguments: aSet(arrayVar, index, value)")

    array_ref = tokens[i].args[0]
    array_index = tokens[i].args[1]
    new_value = helper.resolve_node(tokens[i].args[2], ltc, [], ltc.evaluator.evaluate, None)

    if not isinstance(array_ref, t.var_ref):
        ltc.error("aSet first argument must be an array variable reference")
    if not isinstance(array_index, t.integer):
        ltc.error("aSet index must be a integer")
    
    if array_index.val < 0:
        ltc.error("aSet index cannot be negative")

    var_data = helper.locate_var_in_namespace(ltc.namespace, array_ref.val, return_just_the_check=False)
    var_meta = var_data[0]
    if var_meta is None:
        ltc.error(f"Variable '{array_ref.val}' not found")
    if var_meta["type"] != "array":
        ltc.error("aSet first argument must reference an array variable")

    elem_type = var_meta["elem_type"]
    array_len = var_meta["length"]
    if array_index.val < 0:
        array_index.val = array_index.val % array_len

    if array_index.val >= array_len:
        ltc.error(f"Array index out of range: {array_index.val} for length {array_len}")

    if type(new_value).__name__ != elem_type:
        ltc.error(f"aSet type mismatch: expected {elem_type}, got {type(new_value).__name__}")

    base_addr = var_meta["addr"]
    match elem_type:
        case "i32" | "i64" | "i8" | "i16" | "u32" | "u64" | "u8" | "u16" | "ptr":
            elem_addr = base_addr + (array_index.val * helper.get_ltc_type_size(elem_type, ltc))
            helper.load_to_mem(ltc, new_value, elem_type, memidx=elem_addr)
        case "boolean":
            elem_addr = base_addr + array_index.val
            helper.load_to_mem(ltc, new_value, "boolean", memidx=elem_addr)
        case "char":
            elem_addr = base_addr + array_index.val
            helper.load_to_mem(ltc, new_value, "char", memidx=elem_addr)
        case _:
            ltc.error(f"aSet does not support element type '{elem_type}' yet")

    tokens[i] = t.i32(0)

def resolve_maketuple(tokens, i, ltc) -> None:
    t = ltc.t
    if len(tokens[i].args) < 1:
        ltc.error("makeTuple expects at least one argument")
    element_types = []
    for arg in tokens[i].args:
        if not isinstance(arg, t.token) or arg.val not in ltc.types:
            ltc.error(f"makeTuple arguments must be type name tokens, got '{arg}'")
        element_types.append(arg.val)

    tokens[i] = t.ltctuple(ltc, elements=(), element_types=element_types)

def resolve_tag(tokens, i, ltc) -> None:
    """Used for optionally tagging pointers with type information. Type info is stored in variable metadata."""
    t = ltc.t
    if len(tokens[i].args) != 2:
        ltc.error("tag expects exactly two arguments: tag(ptr, type)")
    ptr_arg = tokens[i].args[0]
    type_arg = tokens[i].args[1]
    if not isinstance(ptr_arg, t.ptr):
        ltc.error(f"First argument to tag must be a pointer, got {type(ptr_arg).__name__}")
    if not isinstance(type_arg, t.token) or type_arg.val not in ltc.types:
        ltc.error(f"Second argument to tag must be a valid type, got {type(type_arg).__name__}")

    if ptr_arg.var_name == None:
        ltc.error("Only pointer variables can be tagged, but got an unreferenced pointer")
    
    # check if the variable exists, it should but let's be safe
    var_data = ltc.helper.locate_var_in_namespace(ltc.namespace, ptr_arg.var_name, return_just_the_check=False)
    (var_meta, scope_level) = var_data
    if var_meta is None:
        ltc.error(f"Variable '{ptr_arg.var_name}' not found for tagging")
    
    ltc.namespace[scope_level][ptr_arg.var_name]["tag"] = type_arg.val # store the tag in the variable's metadata
    tokens[i] = t.i32(0, ltc) # return 0 for success (could also return the pointer itself or the tag if desired)

def resolve_untag(tokens, i, ltc) -> None:
    """Used for optionally untagging pointers with type information. Type info is stored in variable metadata."""
    t = ltc.t
    if len(tokens[i].args) != 1:
        ltc.error("untag expects exactly one argument: untag(ptr)")
    ptr_arg = tokens[i].args[0]
    if not isinstance(ptr_arg, t.ptr):
        ltc.error(f"Argument to untag must be a pointer, got {type(ptr_arg).__name__}")

    if ptr_arg.var_name == None:
        ltc.error("Only pointer variables can be untagged, but got an unreferenced pointer")
    
    # check if the variable exists, it should but let's be safe
    var_data = ltc.helper.locate_var_in_namespace(ltc.namespace, ptr_arg.var_name, return_just_the_check=False)
    (var_meta, scope_level) = var_data
    if var_meta is None:
        ltc.error(f"Variable '{ptr_arg.var_name}' not found for untagging")
    
    if "tag" in ltc.namespace[scope_level][ptr_arg.var_name]:
        del ltc.namespace[scope_level][ptr_arg.var_name]["tag"] # remove the tag from the variable's metadata
    tokens[i] = t.i32(0) # return 0 for success (could also return the pointer itself if desired)

def resolve_gettypetag(tokens, i, ltc) -> None:
    """Used for retrieving the type tag from a tagged pointer."""
    t = ltc.t
    if len(tokens[i].args) != 1:
        ltc.error("getTypeTag expects exactly one argument: getTypeTag(ptr)")
    ptr_arg = tokens[i].args[0]
    if not isinstance(ptr_arg, t.ptr):
        ltc.error(f"Argument to getTypeTag must be a pointer, got {type(ptr_arg).__name__}")

    if ptr_arg.var_name == None:
        ltc.error("Only pointer variables can have type tags, but got an unreferenced pointer")
    
    # check if the variable exists, it should but let's be safe
    var_data = ltc.helper.locate_var_in_namespace(ltc.namespace, ptr_arg.var_name, return_just_the_check=False)
    (var_meta, scope_level) = var_data
    if var_meta is None:
        ltc.error(f"Variable '{ptr_arg.var_name}' not found for retrieving type tag")
    
    if "tag" not in ltc.namespace[scope_level][ptr_arg.var_name]:
        ltc.error(f"Variable '{ptr_arg.var_name}' is not tagged")
    
    tokens[i] = t.string(ltc.namespace[scope_level][ptr_arg.var_name]["tag"]) # return the tag as a token for easy comparison in user code

def resolve_malloctype(tokens, i, ltc) -> None:
    if len(tokens[i].args) != 2:
        ltc.error("mallocType expects exactly two arguments: mallocType(type, count)")
    type_arg = tokens[i].args[0]
    count_arg = tokens[i].args[1]
    if not isinstance(type_arg, ltc.t.token) or type_arg.val not in ltc.types:
        ltc.error(f"mallocType type argument must be a valid type, got {type(type_arg).__name__}")
    if not isinstance(count_arg, ltc.t.integer):
        ltc.error(f"mallocType count argument must be an integer, got {type(count_arg).__name__}")

    num_of_bytes = ltc.helper.get_ltc_type_size(type_arg.val, ltc) * count_arg.val

    ltc.helper.malloc(num_of_bytes, ltc)

    tokens[i] = ltc.t.ptr(ltc.hp) 

def resolve_malloc(tokens, i, ltc) -> None:
    if len(tokens[i].args) != 1:
        ltc.error("malloc expects exactly one argument")
    arg = tokens[i].args[0]
    if not isinstance(arg, ltc.t.integer):
        ltc.error(f"malloc size argument must be an integer, got {type(arg).__name__}")
    
    ltc.helper.malloc(arg.val, ltc)

    tokens[i] = ltc.t.ptr(ltc.hp) 

def resolve_split(tokens, i, ltc) -> None:
    t = ltc.t
    if len(tokens[i].args) != 3:
        ltc.error("split expects exactly three arguments: split[string], [char] | [array] | [string], [boolean])")
    string_arg = tokens[i].args[0]
    delimiter_arg = tokens[i].args[1]
    save_delimiter_arg = tokens[i].args[2]
    
    if not isinstance(string_arg, t.string):
        ltc.error(f"First argument to split must be a string, got {type(string_arg).__name__}")
    if not isinstance(delimiter_arg, (t.string, t.char, t.array)):
        ltc.error(f"Second argument to split must be a string, char, or char array, got {type(delimiter_arg).__name__}")
    if not isinstance(save_delimiter_arg, t.boolean):
        ltc.error(f"Third argument to split must be a boolean, got {type(save_delimiter_arg).__name__}")

    string: str = string_arg.val
    if isinstance(delimiter_arg, t.array):
        delimiter_arg.parse(ltc)
        if delimiter_arg.arrayType != "char":
            ltc.error(f"Argument 2 of split() must either be a string, char, or char array, instead got {delimiter_arg.arrayType} array")
        delimiter: list = delimiter_arg.val
        delimiter = [d.val for d in delimiter] # delimiter is a list of char objects, we need to get their str representation
    else: # either a char or string
        delimiter: str = delimiter_arg.val

    if save_delimiter_arg.val: # save delimiters in the output array if save_delimiter_arg is true
        # this code essentially does split() except saves the delimiter
        split_strings: list[str] = [str()]  # initalize to 1 element of empty str
        idx = 0
        while idx < len(string):
            if type(delimiter) == list: # char array                
                if string[idx] in delimiter:
                    idx_of_delimiter = delimiter.index(string[idx])
                    # Avoid empty segments between consecutive delimiters.
                    if split_strings and split_strings[-1] == "":
                        split_strings.pop()
                    split_strings.append(delimiter[idx_of_delimiter])
                    # Only create a new segment if the next char is not another delimiter.
                    if idx + 1 < len(string) and string[idx + 1] not in delimiter:
                        split_strings.append(str())
                    idx += 1
                else:
                    split_strings[-1] += string[idx]
                    idx += 1
            else: # string or char
                end_of_check: int = idx + len(delimiter)  # the idx of the last char in the sub-string we are currently checking
                if end_of_check > len(string):
                    split_strings[-1] += string[idx:]
                    break
                
                if string[idx:end_of_check] == delimiter:
                    if split_strings and split_strings[-1] == "":
                        split_strings.pop()
                    split_strings.append(delimiter)
                    next_idx = idx + len(delimiter)
                    if next_idx < len(string) and not string.startswith(delimiter, next_idx):
                        split_strings.append(str())
                    idx += len(delimiter)
                else:
                    split_strings[-1] += string[idx]
                    idx += 1
    else: # throw away delimiters in the output
        split_strings = string_arg.val.split(delimiter_arg.val) 

    # arrays cannot hold strings directly, so we store the split strings on the heap and create an array of pointers to them
    ltc_strings = [t.string(s) for s in split_strings]

    ltc_strings_addresses = [ltc.helper.add_string_to_heap(s, ltc.memory, ltc)[0] for s in ltc_strings] # store the split strings on the heap and get their memory locations
    
    ptrs_to_the_strings = [t.ptr(s, ltc) for s in ltc_strings_addresses] # create ptr tokens for the memory locations of the split strings

    tokens[i] = t.array(ptrs_to_the_strings, ltc, arrayType="ptr", parse=False)