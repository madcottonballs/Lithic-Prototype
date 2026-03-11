from resolve_oper import *
def _reduce_argument_value(argument, memory, namespace, types, n, t, helper, user_functions, stack_frames, return_values, sp, execute_source_fn=None):
    """Reduce an argument token to a concrete runtime value token."""
    value = argument

    if isinstance(value, n.oper | n.mono_oper | n.subexp | n.add | n.sub | n.mult | n.div | t.function | t.user_function):
        temp = [value]
        sp, return_values = evaluate(temp, memory, namespace, types, n, t, helper, user_functions, stack_frames, return_values, sp, execute_source_fn)
        value = temp[0]
    elif isinstance(value, t.var_ref):
        value = helper.dereference_var(t, namespace, memory, value)

    return value, sp, return_values

def _bind_user_function_args(call_node, arg_types, arg_names, memory, namespace, types, t, helper, sp):
    """Load user-function arguments into the current frame namespace."""
    # We do not need to check argument count or types here, as that should have been done by user_function.validate_args() already. We just need to load the values into memory and bind their addresses in the namespace.
    for idx, (expected_type, arg_name) in enumerate(zip(arg_types, arg_names)):
        argument_value = call_node.arguments[idx]

        var_addr = sp
        sp = helper.load_to_mem(memory, argument_value, sp, expected_type)
        namespace[len(namespace) - 1][arg_name] = {
            "type": expected_type,
            "addr": var_addr,
        }

    return sp

def evaluate(tokens, memory, namespace, types, n, t, helper, user_functions, stack_frames, return_values=None, stack_ptr=0, execute_source_fn=None):
    """Walk the tree/list and reduce operations. Returns updated stack pointer."""
    if return_values is None:
        return_values = []

    sp = stack_ptr
    i = 0
    while i < len(tokens):
        if isinstance(tokens[i], n.oper | n.mono_oper):
            retry_current, sp = resolve_opers(tokens, i, t, n, helper, namespace, memory, types, sp, user_functions, stack_frames, return_values, evaluate, execute_source_fn)
            if retry_current:
                continue

        if isinstance(tokens[i], n.subexp):
            sp, return_values = evaluate(tokens[i].val, memory, namespace, types, n, t, helper, user_functions, stack_frames, return_values, sp, execute_source_fn)
            tokens[i] = t.i32(tokens[i].val)

        if isinstance(tokens[i], t.function):
            for arg_idx, arg_val in enumerate(tokens[i].args):
                # aSet needs the array variable reference as its first argument.
                if tokens[i].val == "aSet" and arg_idx == 0 and isinstance(arg_val, t.var_ref):
                    tokens[i].args[arg_idx] = arg_val
                    continue

                reduced, sp, return_values = _reduce_argument_value(arg_val, memory, namespace, types, n, t, helper, user_functions, stack_frames, return_values, sp, execute_source_fn)
                # Do not force all function args to be runtime values here.
                # `let` intentionally carries identifier/operator tokens through to function_processing.
                tokens[i].args[arg_idx] = reduced
            sp, return_values = function_processing(tokens, i, memory, namespace, types, t, helper, stack_frames, return_values, sp)
            if isinstance(tokens[i], t.function) and tokens[i].val == "return":
                return sp, return_values

        if isinstance(tokens[i], t.user_function): # resolves user function calls
            if execute_source_fn is None:
                raise RuntimeError("user_function execution requires execute_source_fn")

            for arg_idx, arg_val in enumerate(tokens[i].arguments):
                reduced, sp, return_values = _reduce_argument_value(arg_val, memory, namespace, types, n, t, helper, user_functions, stack_frames, return_values, sp, execute_source_fn)
                tokens[i].arguments[arg_idx] = reduced

            tokens[i].validate_args(user_functions)
            arg_types, arg_names, body_source = helper._get_user_function_meta(user_functions, tokens[i].val)

            helper.create_frame(stack_frames, sp, namespace)
            sp = _bind_user_function_args(tokens[i], arg_types, arg_names, memory, namespace, types, t, helper, sp)
            local_returns = []
            sp, local_returns = execute_source_fn(body_source, memory, namespace, types, stack_frames, sp, user_functions, local_returns)
            sp = helper.destroy_frame(stack_frames, namespace)

            if local_returns:
                tokens[i] = local_returns[0]
            else:
                raise RuntimeError(f"User function '{tokens[i].val}' did not return a value")

        i += 1

    return sp, return_values

def function_processing(tokens, i, memory, namespace, types, t, helper, stack_frames, return_values, stack_ptr) -> tuple[int, list]:
    """Process built-ins and return updated stack pointer."""
    sp = stack_ptr
    match tokens[i].val:
        case "printf":
            if len(tokens[i].args) != 1:
                raise SyntaxError("printf() expects exactly one argument")
            arg = tokens[i].args[0]
            if isinstance(arg, t.integer | t.string | t.boolean | t.char):
                print(arg.val, end="\n")
            elif isinstance(arg, t.array):
                rendered = ", ".join(str(element.val) for element in arg.val)
                print(f"[{rendered}]", end="\n")
            else:
                raise TypeError(f"Unsupported argument type for printf(): {type(arg).__name__}")
            tokens[i] = t.i32(0)

        case "let":
            if len(tokens[i].args) not in (2, 4):
                raise SyntaxError("let expects: let [type] [varname] OR let [type] [varname] = [value]")

            let_type = len(tokens[i].args)
            var_type_arg = tokens[i].args[0]
            var_name_arg = tokens[i].args[1]

            if not isinstance(var_name_arg, t.token):
                raise TypeError("Second argument to let must be a variable name token")

            var_mem_addr = sp

            if let_type == 4:
                equals_arg = tokens[i].args[2]
                var_value_arg = tokens[i].args[3]

                if not (isinstance(equals_arg, t.token) and equals_arg.val == "="):
                    raise SyntaxError("let expects '=' as the third argument")
                if type(var_value_arg) != types[var_type_arg.val]:
                    raise TypeError(
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
                    sp = helper.load_to_mem(memory, var_value_arg, sp, "array")
                else:
                    sp = helper.load_to_mem(memory, var_value_arg, sp, var_type_arg.val)
            else:
                if isinstance(var_type_arg, t.array):
                    empty_array = t.array([], arrayType=var_type_arg.arrayType, parse=False)
                    empty_array.size = var_type_arg.size
                    sp = helper.load_to_mem(memory, empty_array, sp, "array")
                else:
                    sp = helper.load_to_mem(memory, helper.recieve_empty_form(t, var_type_arg.val), sp, var_type_arg.val)
            
            if isinstance(var_type_arg, t.array):
                namespace[len(namespace) - 1][var_name_arg.val] = {
                    "type": "array",
                    "addr": var_mem_addr,
                    "length": var_type_arg.size,
                    "elem_type": var_type_arg.arrayType,
                }
            else:
                namespace[len(namespace) - 1][var_name_arg.val] = {
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
                case t.i32 | t.u32:
                    tokens[i] = t.i32(4)
                case t.i64 | t.u64:
                    tokens[i] = t.i32(8)
                case t.i8 | t.u8:
                    tokens[i] = t.i32(1)
                case t.i16 | t.u16:
                    tokens[i] = t.i32(2)
                case t.boolean:
                    tokens[i] = t.i32(1)
                case t.array:
                    tokens[i] = t.i32(arg.get_size())
                case t.char:
                    tokens[i] = t.i32(1)
                case _:
                    raise TypeError(f"Unsupported argument type for sizeof: {type(arg).__name__}")

        case "sConcat":
            if len(tokens[i].args) < 2:
                raise SyntaxError("sConcat expects at least two arguments")
            concatenated = ""
            for arg in tokens[i].args:
                if not isinstance(arg, t.string):
                    raise TypeError(f"Unsupported argument type for sConcat: {type(arg).__name__}")
                concatenated += arg.val
            tokens[i] = t.string(concatenated)

        case "sLength":
            if len(tokens[i].args) != 1:
                raise SyntaxError("sLength() expects exactly one argument")
            arg = tokens[i].args[0]
            if not isinstance(arg, t.string):
                raise TypeError(f"Unsupported argument type for sLength(): {type(arg).__name__}")
            tokens[i] = t.i32(len(arg.val))

        case "aConcat":
            if len(tokens[i].args) < 2:
                raise SyntaxError("aConcat expects at least two arguments")

            expected_array_type = tokens[i].args[0].arrayType
            concatenated = []

            for arg in tokens[i].args:
                if not isinstance(arg, t.array):
                    raise TypeError(
                        f"Unsupported argument type for aConcat: '{type(arg).__name__}'. "
                        "Array concatenation only supports array arguments."
                    )
                if arg.arrayType != expected_array_type:
                    raise TypeError(
                        f"Array type mismatch in aConcat: expected {expected_array_type}[], got {arg.arrayType}[]"
                    )
                concatenated.extend(arg.val)

            tokens[i] = t.array(concatenated, arrayType=expected_array_type, parse=False)

        case "aLength":
            if len(tokens[i].args) != 1:
                raise SyntaxError("aLength() expects exactly one argument")
            arg = tokens[i].args[0]
            if not isinstance(arg, t.array):
                raise TypeError(f"aLength() only takes arrays, not '{type(arg).__name__}'")
            tokens[i] = t.i32(arg.get_size())

        case "aSet":
            if len(tokens[i].args) != 3:
                raise SyntaxError("aSet expects exactly three arguments: aSet(arrayVar, index, value)")

            array_ref = tokens[i].args[0]
            array_index = tokens[i].args[1]
            new_value = tokens[i].args[2]

            if not isinstance(array_ref, t.var_ref):
                raise TypeError("aSet first argument must be an array variable reference")
            if not isinstance(array_index, t.i32):
                raise TypeError("aSet index must be a i32")

            var_data = helper.locate_var_in_namespace(namespace, array_ref.val, return_just_the_check=False)
            var_meta = var_data[0]
            if var_meta is None:
                raise NameError(f"Variable '{array_ref.val}' not found")
            if var_meta["type"] != "array":
                raise TypeError("aSet first argument must reference an array variable")

            elem_type = var_meta["elem_type"]
            array_len = var_meta["length"]
            if array_index.val < 0 or array_index.val >= array_len:
                raise SyntaxError(f"Array index out of range: {array_index.val} for length {array_len}")

            if type(new_value).__name__ != elem_type:
                raise TypeError(f"aSet type mismatch: expected {elem_type}, got {type(new_value).__name__}")

            base_addr = var_meta["addr"]
            match elem_type:
                case "i32" | "i64" | "i8" | "i16" | "u32" | "u64" | "u8" | "u16":
                    elem_addr = base_addr + (array_index.val * helper.integer_type_to_size(elem_type))
                    helper.load_to_mem(memory, new_value, sp, elem_type, memidx=elem_addr)
                case "boolean":
                    elem_addr = base_addr + array_index.val
                    helper.load_to_mem(memory, new_value, sp, "boolean", memidx=elem_addr)
                case "char":
                    elem_addr = base_addr + array_index.val
                    helper.load_to_mem(memory, new_value, sp, "char", memidx=elem_addr)
                case _:
                    raise TypeError(f"aSet does not support element type '{elem_type}' yet")

            tokens[i] = t.i32(0)

        case "return":
            if len(tokens[i].args) != 1:
                raise SyntaxError("return expects exactly one argument")
            return_values = [tokens[i].args[0]]
        
        case "cast":
            resolve_cast_function(tokens, i, t, helper)

    return sp, return_values

def resolve_cast_function(tokens: list, i: int, t: object, helper: object):
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