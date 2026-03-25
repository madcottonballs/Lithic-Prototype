"""This module contains the main evaluation loop for walking the token tree and reducing operations, as well as processing built-in functions."""

from evalulation.resolve_oper import *
import evalulation.cmd as cmd
import evalulation.data as data

def _bind_user_function_args(call_node, arg_types, arg_names, ltc) -> None:
    """Load user-function arguments into the current frame namespace."""
    # We do not need to check argument count or types here, as that should have been done by user_function.validate_args() already. We just need to load the values into memory and bind their addresses in the namespace.
    for idx, (expected_type, arg_name) in enumerate(zip(arg_types, arg_names)):
        argument_value = call_node.arguments[idx]

        var_addr = ltc.sp
        ltc.helper.load_to_mem(ltc, argument_value, expected_type)
        entry = {
            "type": expected_type,
            "addr": var_addr,
        }
        if expected_type == "tuple" and isinstance(argument_value, ltc.t.ltctuple):
            entry["element_types"] = argument_value.element_types
        if expected_type == "array" and isinstance(argument_value, ltc.t.array):
            entry["length"] = argument_value.get_size()
            entry["elem_type"] = argument_value.arrayType
        ltc.namespace[len(ltc.namespace) - 1][arg_name] = entry

def evaluate(tokens, ltc, return_values, execute_source_fn) -> list:
    """Walk the tree/list and reduce operations. Returns return_values: list
    Params: tokens, ltc, return_values, execute_source_fn."""

    n = ltc.n
    t = ltc.t
    helper = ltc.helper
    i = 0
    while i < len(tokens):
        if isinstance(tokens[i], n.oper | n.mono_oper):
            retry_current = resolve_opers(tokens, i, ltc, return_values, evaluate, execute_source_fn)
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
            cmd.ltc_print(ltc, tokens, i)
        case "let":
            data.resolve_let(tokens, i, ltc)
        case "input":
            cmd.ltc_input(tokens, i, ltc)
        case "typeof":
            data.resolve_typeof(tokens, i, ltc)
        case "sizeof":
            data.resolve_sizeof(tokens, i, ltc)
        case "concat":
            data.resolve_concat(tokens, i, ltc)
        case "length":
            if len(tokens[i].args) != 1:
                raise SyntaxError("length() expects exactly one argument")
            arg = tokens[i].args[0]
            if isinstance(arg, t.string | t.array):
                tokens[i] = t.i32(len(arg.val))
            elif isinstance(arg, t.ltctuple):
                tokens[i] = t.i32(arg.get_size())

        case "aSet":
            data.resolve_aset(tokens, i, ltc)
        case "tSet":
            data.resolve_tset(tokens, i, ltc)
        case "return":
            if len(tokens[i].args) != 1:
                raise SyntaxError("return expects exactly one argument")
            return_values = [tokens[i].args[0]]
        
        case "cast":
            data.resolve_cast_function(tokens, i, ltc)
        
        case "malloc":
            if len(tokens[i].args) != 1:
                raise SyntaxError("malloc expects exactly one argument")
            arg = tokens[i].args[0]
            if not isinstance(arg, t.integer):
                raise TypeError(f"malloc size argument must be an integer, got {type(arg).__name__}")
            
            helper.malloc(arg.val, ltc)

            tokens[i] = t.ptr(ltc.hp) 
        
        case "coredump":
            cmd.resolve_coredump(tokens, i, ltc)
        case "exit":
            if len(tokens[i].args) != 1:
                raise SyntaxError("exit expects exactly one argument")
            arg = tokens[i].args[0]
            if not isinstance(arg, t.integer):
                raise TypeError(f"exit code argument must be an integer, got {type(arg).__name__}")
            exit(arg.val)
        
        case "@":
            data.resolve_deref(tokens, i, ltc)
        case "makeTuple":
            data.resolve_maketuple(tokens, i, ltc)        
        case "pass":
            tokens[i] = t.i32(0)

    return return_values