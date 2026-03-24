"""This module contains the main evaluation loop for walking the token tree and reducing operations, as well as processing built-in functions."""

from resolve_oper import *

def _bind_user_function_args(call_node, arg_types, arg_names, ltc) -> None:
    """Load user-function arguments into the current frame namespace."""
    # We do not need to check argument count or types here, as that should have been done by user_function.validate_args() already. We just need to load the values into memory and bind their addresses in the namespace.
    for idx, (expected_type, arg_name) in enumerate(zip(arg_types, arg_names)):
        argument_value = call_node.arguments[idx]

        var_addr = ltc.sp
        ltc.helper.load_to_mem(ltc, argument_value, expected_type)
        ltc.namespace[len(ltc.namespace) - 1][arg_name] = {
            "type": expected_type,
            "addr": var_addr,
        }


def evaluate(tokens, ltc, return_values, execute_source_fn) -> list:
    """Walk the tree/list and reduce operations. Returns return_values: list
    Params: tokens, ltc, return_values, execute_source_fn."""

    n = ltc.n
    t = ltc.t
    helper = ltc.helper
    i = 0
    while i < len(tokens):
        if isinstance(tokens[i], n.oper | n.mono_oper):
            retry_current = resolve_opers(tokens, 0, ltc, return_values, evaluate, execute_source_fn)
            if retry_current:
                continue

        if isinstance(tokens[i], n.subexp):
            return_values = evaluate(tokens[i].val, ltc, return_values, execute_source_fn)
            if len(tokens[i].val) != 1:
                raise TypeError(f"Sub-expression did not reduce to a single value, instead got '{tokens[i].val}'")
            tokens[i] = tokens[i].val[0]

        if isinstance(tokens[i], n.at_func_return):
            tokens[i] = tokens[i].val

        if isinstance(tokens[i], t.function):
            for arg_idx, arg_val in enumerate(tokens[i].args):
                # aSet needs the array variable reference as its first argument.
                if tokens[i].val == "aSet" and arg_idx == 0 and isinstance(arg_val, t.var_ref):
                    tokens[i].args[arg_idx] = arg_val
                    continue
                
                arg_val = helper.resolve_node(arg_val, ltc, return_values, evaluate, execute_source_fn)
                # Do not force all function args to be runtime values here.
                # `let` intentionally carries identifier/operator tokens through to function_processing.
                tokens[i].args[arg_idx] = arg_val
            return_values = function_processing(tokens, i, ltc, return_values)
            if isinstance(tokens[i], t.function) and tokens[i].val == "return":
                return return_values

        if isinstance(tokens[i], t.user_function): # resolves user function calls
            if execute_source_fn is None:
                raise RuntimeError("user_function execution requires execute_source_fn")

            for arg_idx, arg_val in enumerate(tokens[i].arguments):
                arg_val = helper.resolve_node(arg_val, ltc, return_values, evaluate, execute_source_fn)
                tokens[i].arguments[arg_idx] = arg_val

            tokens[i].validate_args(ltc.user_functions)
            arg_types, arg_names, body_source = helper._get_user_function_meta(ltc.user_functions, tokens[i].val, ltc)

            helper.create_frame(ltc)
            ltc.traceback.append(tokens[i].val)
            _bind_user_function_args(tokens[i], arg_types, arg_names, ltc)
            local_returns = []
            local_returns = execute_source_fn(body_source, ltc, local_returns)
            ltc.traceback.pop()
            helper.destroy_frame(ltc)

            if local_returns:
                tokens[i] = local_returns[0]
            else:
                raise RuntimeError(f"User function '{tokens[i].val}' did not return a value")

        i += 1

    return return_values

def function_processing(tokens, i, ltc, return_values) -> list:
    """Process built-ins and return updated stack pointer."""
    t = ltc.t
    helper = ltc.helper
    n = ltc.n
    match tokens[i].val:
        case "printf":
            if len(tokens[i].args) != 1:
                raise SyntaxError("printf() expects exactly one argument")
            arg = tokens[i].args[0]
            if isinstance(arg, t.integer | t.string | t.boolean | t.char):
                print(arg.val, end="\n")
            elif isinstance(arg, t.array):
                rendered = ", ".join(str(element.val) for element in arg.val)
                print(f"array[{rendered}]", end="\n")
            elif isinstance(arg, t.ltctuple):
                rendered = ", ".join(str(element.val) for element in arg.val)
                print(f"tuple({rendered})", end="\n")
            else:
                raise TypeError(f"Unsupported argument type for printf(): {type(arg).__name__}")
            tokens[i] = t.i32(0)

        case "let":
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
                    helper.load_to_mem(ltc, helper.recieve_empty_form(t, var_type_arg.val), var_type_arg.val)
            
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

        case "input":
            if len(tokens[i].args) != 0:
                raise SyntaxError("input does not take any arguments")
            try:
                tokens[i] = t.string(input())
            except EOFError:
                tokens[i] = t.string("")

        case "typeof":
            if len(tokens[i].args) != 1:
                raise SyntaxError("typeof expects exactly one argument")
            tokens[i] = t.string(type(tokens[i].args[0]).__name__)

        case "sizeof":
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
                case _:
                    raise TypeError(f"Unsupported argument type for sizeof: {type(arg).__name__}")
        
        case "concat":
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

        case "length":
            if len(tokens[i].args) != 1:
                raise SyntaxError("length() expects exactly one argument")
            arg = tokens[i].args[0]
            if isinstance(arg, t.string | t.array):
                tokens[i] = t.i32(len(arg.val))
            elif isinstance(arg, t.ltctuple):
                tokens[i] = t.i32(arg.get_size())

        case "aSet":
            if len(tokens[i].args) != 3:
                raise SyntaxError("aSet expects exactly three arguments: aSet(arrayVar, index, value)")

            array_ref = tokens[i].args[0]
            array_index = tokens[i].args[1]
            new_value = tokens[i].args[2]

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
                case "i32" | "i64" | "i8" | "i16" | "u32" | "u64" | "u8" | "u16":
                    elem_addr = base_addr + (array_index.val * helper.integer_type_to_size(elem_type))
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

        case "tSet":
            if len(tokens[i].args) != 3:
                raise SyntaxError("tSet expects exactly three arguments: tSet(tupleVar, index, value)")

            tuple_ref = tokens[i].args[0]
            tuple_index = tokens[i].args[1]
            new_value = tokens[i].args[2]
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

        case "return":
            if len(tokens[i].args) != 1:
                raise SyntaxError("return expects exactly one argument")
            return_values = [tokens[i].args[0]]
        
        case "cast":
            resolve_cast_function(tokens, i, ltc)
        
        case "malloc":
            if len(tokens[i].args) != 1:
                raise SyntaxError("malloc expects exactly one argument")
            arg = tokens[i].args[0]
            if not isinstance(arg, t.integer):
                raise TypeError(f"malloc size argument must be an integer, got {type(arg).__name__}")
            
            helper.malloc(arg.val, ltc)

            tokens[i] = t.ptr(ltc.hp) 
        
        case "coredump":
            if len(tokens[i].args) != 0:
                raise SyntaxError("coredump does not take any arguments")
            with open("coredump.txt", "w") as f:
                annontations: dict[int, str] = {} # memory annontations keyed by memory address for easier reading of the coredump. This is populated by things like variable declarations that know what memory addresses they are using, and can write those addresses along with variable names and types to the annontations dict. The coredump printing logic then checks this dict when printing each memory address, and if an annotation exists for that address, it prints it along with the memory value.
                f.write("===CORE DUMP===\n")
                
                f.write(f"Stack Pointer: {ltc.sp}\n===============================\n")
                f.write(f"Heap Pointer: {ltc.hp}\n===============================\n")
                annontations[ltc.sp] = "(SP)"
                annontations[ltc.hp] = "(HP)"

                f.write(f"Namespace:\n")
                for i, v in enumerate(ltc.namespace):
                    f.write(f"\tFrame {i}:\n")
                    for var_name, var_meta in v.items():
                        f.write(f"\t\t{var_name}:\n")
                        f.write(f"\t\t\ttype: {var_meta['type']}\n")
                        f.write(f"\t\t\taddr: {var_meta['addr']}\n")
                        if var_meta['type'] == 'array':
                            f.write(f"\t\t\tlength: {var_meta['length']}\n")
                            f.write(f"\t\t\telem_type: {var_meta['elem_type']}\n")
                        if var_meta['type'] == 'tuple':
                            f.write(f"\t\t\telem_types: {var_meta['element_types']}\n")
                        
                        if var_meta['addr'] in annontations:                            
                            annontations[var_meta['addr']] += f" | Start of '{var_name}' of type '{var_meta['type']}'"
                        else:
                            annontations[var_meta['addr']] = f"Start of '{var_name}' of type '{var_meta['type']}'"

                f.write(f"===============================\n")
                f.write("Stack Frames:\n")
                for i, v in enumerate(ltc.stack_frames):
                    f.write(f"\tStack Frame {i} SP: {v}\n")
                    if v in annontations:
                        annontations[v] += f" | Stack frame {i} start"
                    else:
                        annontations[v] = f"Stack frame {i} start"

                f.write(f"===============================\n")
                f.write("Memory:\n")
                for i, v in enumerate(ltc.memory):
                    if i in annontations:
                        f.write(f"\t[{i}]: {v}  <-- {annontations[i]}\n")
                    else:
                        f.write(f"\t[{i}]: {v}\n")
            f.close()
        
        case "exit":
            if len(tokens[i].args) != 1:
                raise SyntaxError("exit expects exactly one argument")
            arg = tokens[i].args[0]
            if not isinstance(arg, t.integer):
                raise TypeError(f"exit code argument must be an integer, got {type(arg).__name__}")
            exit(arg.val)
        
        case "@":
            if len(tokens[i].args) != 2:
                raise SyntaxError("@ expects exactly two arguments: @(ptr, type)")
            
            ptr_arg = tokens[i].args[0]
            type_arg = tokens[i].args[1]

            if not isinstance(ptr_arg, t.ptr):
                raise TypeError(f"First argument to @ must be a pointer, got {type(ptr_arg).__name__}")
            if (not isinstance(type_arg, t.token)) or (not type_arg.val in ltc.types.keys()):
                raise TypeError(f"Second argument to @ must be a type name, instead got {type_arg.val}")
            
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
                    
            ptr_deref = helper.read_ltc_type_from_mem(ltc.memory, ptr_arg.val, type_arg.val, ltc) # returns the obj read from memory

            tokens[i] = n.at_func_return(ptr_deref, ptr_arg.val, type_size) # create an at_func_return_obj to hold the dereferenced value along with the original pointer and type size for use in assign_oper

        case "makeTuple":
            if len(tokens[i].args) < 1:
                raise SyntaxError("makeTuple expects at least one argument")
            element_types = []
            for arg in tokens[i].args:
                if not isinstance(arg, t.token) or arg.val not in ltc.types:
                    raise TypeError(f"makeTuple arguments must be type name tokens, got '{arg}'")
                element_types.append(arg.val)

            tokens[i] = t.ltctuple(ltc, elements=(), element_types=element_types)
        
        case "pass":
            tokens[i] = t.i32(0)

    return return_values

def resolve_cast_function(tokens: list, i: int, ltc):
    t = ltc.t
    if len(tokens[i].args) != 2:
        raise SyntaxError(f"cast expects exactly two arguments, not {len(tokens[i].args)}")
    
    # readability
    cast_target: str = tokens[i].args[1].val
    source_object: object = tokens[i].args[0]
    # only used for integer casts but this avoids rewriting
    ltc_target_int_class = t.__dict__[cast_target] # finds the ltc typerizer class referenced by the cast_target string (if cast_target = "i32", ltc_target_int_class = t.i32)

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
