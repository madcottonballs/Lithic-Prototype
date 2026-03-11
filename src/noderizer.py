"""This module builds operator nodes for expressions, such as addition, subtraction, equality checks, etc. It also handles parsing of array type declarations and literals, as well as variable dereferencing."""
from src.typerizer import integer
from src.noderizer_build_oper import *

class oper():
    def __init__(self, node1, node2):
        self.node1 = node1
        self.node2 = node2

class assign(oper):
    pass
class increment(oper):
    pass
class decrement(oper):
    pass

class mono_oper():
    def __init__(self, node):
        self.node = node

class equal(oper):
    pass
class not_equal(oper):
    pass
class invert(mono_oper):
    pass
class gtr_than(oper):
    pass
class less_than(oper):
    pass
class gtr_than_or_equal(oper):
    pass
class less_than_or_equal(oper):
    pass

class free(mono_oper):
    pass

class mult(oper):
    pass
class div(oper):
    pass
class add(oper):
    pass
class sub(oper):
    pass
class subexp():
    # Parenthesized sub-expression node, containing a nested token list/tree.
    def __init__(self, val: list):
        self.val = val

# mother function
def generate_trees(t, function_names, helper, tokens, namespace, memory, user_functions, types, start_index=0):
    # Non-list inputs are already single nodes and do not need list-based passes.
    if not isinstance(tokens, list):
        return

    #_build_function_calls(tokens, t, helper, start_index)

    # Pass 0: collapse array type declarations like `i32[4]` into one array token.
    _build_array_type_tokens(tokens, t, start_index)

    # Pass 1: collapse raw parenthesized ranges into `subexp` nodes.
    build_subexp(start_index, tokens, helper, t, function_names, namespace, memory, user_functions, types)
    # Pass 1.25: collapse array literals like `[1, 2]` into one `array` token.
    _build_array_literals(tokens, t, function_names, helper, namespace, memory, start_index)
    # Pass 1.5: convert let statements in intended syntax to a function node.
    # Examples:
    #   let i32 x = 5  -> function("let", [i32, x, =, 5])
    #   let i32 x      -> function("let", [i32, x])
    _build_let_stmts(start_index, tokens, t, function_names, helper, namespace, memory, user_functions, types)

    _build_opers(t, function_names, helper, tokens, namespace, memory, start_index, user_functions, types)

    _dereference_vars(start_index, tokens, t, helper, namespace, memory)
    
    _build_add_sub_mult_div_nodes(start_index, tokens, helper, t, function_names, namespace, memory, user_functions, types)

    _build_indexing(start_index, t, function_names, helper, tokens, namespace, memory)

def _build_indexing(start_index, t, function_names, helper, tokens, namespace, memory):
    index = start_index
    while index < len(tokens):

        if index + 1 >= len(tokens):
            return # no more indexing possible, might as well return
        
        current_token = tokens[index]
        next_token = tokens[index + 1]
        if type(current_token).__name__ == "array":
            if type(next_token).__name__ == "array" and next_token.get_size() == 1: # condition of ex. [5, 3, 2][0] -> should return 5
                _build_array_indexing(current_token, next_token, t, helper, namespace, memory, tokens, index)
        if type(current_token).__name__ == "string":
            if type(next_token).__name__ == "array" and next_token.get_size() == 1: # condition of ex. "hello"[0] -> should return 'h'
                _build_string_indexing(current_token, next_token, t, helper, namespace, memory, tokens, index)

        index += 1

def _build_array_indexing(current_token, next_token, t, helper, namespace, memory, tokens, index):
    index_value_token = next_token.val[0]
    if isinstance(index_value_token, t.var_ref):
        index_value_token = helper.dereference_var(t, namespace, memory, index_value_token)
    elif isinstance(index_value_token, t.token):
        # Handle unresolved plain tokens defensively.
        if helper.locate_var_in_namespace(namespace, index_value_token.val, return_just_the_check=True):
            index_value_token = helper.dereference_var(t, namespace, memory, t.var_ref(index_value_token.val))
        elif str(index_value_token.val).isdigit():
            index_value_token = t.i32(index_value_token.val)

    if not isinstance(index_value_token, t.integer):
        raise TypeError(f"Tried to index an array with a non-integer index of type '{type(index_value_token).__name__}'. This error is usually thrown when you try indexing with an undeclared variable. (did you miss a ';' before this statement?)")
    
    array_index = index_value_token.val

    if array_index < 0 or array_index >= current_token.get_size():
        raise SyntaxError(f"Tried to index an array of size {current_token.get_size()} with an index of {array_index}")
        
    match current_token.arrayType:
        case "i32" | "i64" | "i8" | "i16" | "u32" | "u64" | "u8" | "u16":
            temp = t.__dict__[current_token.arrayType] # get the correct integer type constructor based on arrayType
            element = current_token.val[array_index]
            tokens[index:index + 2] = [temp(element.val if hasattr(element, "val") else element)]
        case "string":
            element = current_token.val[array_index]
            tokens[index:index + 2] = [t.string(element.val if hasattr(element, "val") else element)]
        case "boolean":
            element = current_token.val[array_index]
            tokens[index:index + 2] = [t.boolean(element.val if hasattr(element, "val") else element)]
        case _:
            raise TypeError("Unsupported type of array used for array indexing")

def _resolve_index_token_to_dword(index_token, t, helper, namespace, memory):
    """Resolve index token to i32 for indexed write rewrites."""
    resolved_index = index_token
    if isinstance(resolved_index, t.var_ref):
        resolved_index = helper.dereference_var(t, namespace, memory, resolved_index)
    elif isinstance(resolved_index, t.token):
        if helper.locate_var_in_namespace(namespace, resolved_index.val, return_just_the_check=True):
            resolved_index = helper.dereference_var(t, namespace, memory, t.var_ref(resolved_index.val))
        elif str(resolved_index.val).isdigit():
            resolved_index = t.i32(resolved_index.val)

    if not isinstance(resolved_index, t.integer):
        raise TypeError("Array index must resolve to an integer")

    return resolved_index

def build_array_set_call(t, helper, tokens, lhs_ref, lhs_index_array, rhs_value, namespace, memory):
    """Build aSet(arrayRef, index, rhs) function node and replace current statement."""
    if not isinstance(lhs_ref, t.var_ref):
        raise TypeError("Indexed assignment requires a variable reference as the array base")
    if not isinstance(lhs_index_array, t.array) or lhs_index_array.get_size() != 1:
        raise SyntaxError("Indexed assignment expects exactly one index: arr[idx]")

    index_token = _resolve_index_token_to_dword(lhs_index_array.val[0], t, helper, namespace, memory)
    args = [
        lhs_ref,
        t.token(","),
        index_token,
        t.token(","),   
        rhs_value,
    ]

    return t.function("aSet", args)

def _build_string_indexing(current_token, next_token, t, helper, namespace, memory, tokens, index):
    index_value_token = next_token.val[0]
    if isinstance(index_value_token, t.var_ref):
        index_value_token = helper.dereference_var(t, namespace, memory, index_value_token)
    elif isinstance(index_value_token, t.token):
        # Handle unresolved plain tokens defensively.
        if helper.locate_var_in_namespace(namespace, index_value_token.val, return_just_the_check=True):
            index_value_token = helper.dereference_var(t, namespace, memory, t.var_ref(index_value_token.val))
        elif str(index_value_token.val).isdigit():
            index_value_token = t.i32(index_value_token.val)

    if not isinstance(index_value_token, t.integer):
        raise TypeError("Can only use an integer as an index for an array (did you miss a ';' before this statement?)")
    
    array_index = index_value_token.val

    if array_index < 0 or array_index >= len(current_token.val):
        raise SyntaxError(f"Tried to index a string of size {len(current_token.val)} with an index of {array_index}")
    
    element = current_token.val[array_index]
    tokens[index:index + 2] = [t.char(element.val if hasattr(element, "val") else element)]

def _build_let_stmts(start_index, tokens, t, function_names, helper, namespace, memory, user_functions, types):
    index = start_index
    while index < len(tokens):
        symbol = getattr(tokens[index], "val", None)

        if symbol == "let" and not isinstance(tokens[index], t.function):
            next_symbol = tokens[index + 1].val if index + 1 < len(tokens) else None
            if next_symbol == "(":
                index += 1
                continue
            if index + 2 >= len(tokens):
                raise SyntaxError("let expects syntax: let [type] [varname] OR let [type] [varname] = [value]")

            # Support bare declarations: let <type> <name>
            if index + 3 >= len(tokens) or tokens[index + 3].val != "=":
                arguments = tokens[index + 1:index + 3]
                tokens[index:index + 3] = [t.function("let", arguments)]
            else:
                # Support declarations with assignment: let <type> <name> = <full expression>
                if index + 4 >= len(tokens):
                    raise SyntaxError("let assignment expects syntax: let [type] [varname] = [value]")

                rhs_tokens = tokens[index + 4:]
                generate_trees(t, function_names, helper, rhs_tokens, namespace, memory, user_functions, types, 0)
                if len(rhs_tokens) != 1:
                    raise SyntaxError("let assignment RHS did not reduce to a single value")

                arguments = [tokens[index + 1], tokens[index + 2], tokens[index + 3], rhs_tokens[0]]
                tokens[index:] = [t.function("let", arguments)]
                return
        index += 1

def _build_array_type_tokens(tokens, t, start_index=0):
    """Convert `<type>[<i32>]` into one `t.array` type token.

    Example:
      [token('i32'), token('['), i32(2), token(']')]
      -> [array_token(val='array', arrayType='i32', size=2)]
    """
    index = start_index
    while index + 3 < len(tokens):
        type_token = tokens[index]
        open_bracket = tokens[index + 1]
        size_token = tokens[index + 2]
        close_bracket = tokens[index + 3]

        is_primitive_type = (
            isinstance(type_token, t.token)
            and not isinstance(type_token, (t.var_ref, t.function, t.i32, t.string, t.boolean, t.array))
            and getattr(type_token, "val", None) in {"i32", "string", "boolean"}
        )
        if not is_primitive_type:
            index += 1
            continue

        if getattr(open_bracket, "val", None) != "[":
            index += 1
            continue

        if not isinstance(size_token, t.i32):
            raise SyntaxError("Array size must be a i32 literal in type declaration")
        if size_token.val < 0:
            raise SyntaxError("Array size cannot be negative")
        if getattr(close_bracket, "val", None) != "]":
            raise SyntaxError("Array type declaration is missing closing ']'")

        # Reuse your existing array class as a type token.
        array_type_token = t.array([], arrayType=type_token.val, parse=False)
        array_type_token.val = "array"
        array_type_token.size = size_token.val
        tokens[index:index + 4] = [array_type_token]
        # Do not increment index so chained patterns still get parsed correctly.

def _build_array_literals(tokens, t, function_names, helper, namespace, memory, types, start_index=0):
    """Convert `[elem1, elem2, ...]` into one `t.array` token."""
    index = start_index
    while index < len(tokens):
        symbol = getattr(tokens[index], "val", None)
        if symbol != "[":
            index += 1
            continue

        # Skip array type declarations that were not reduced for any reason.
        prev_symbol = getattr(tokens[index - 1], "val", None) if index > 0 else None
        if prev_symbol in {"i32", "string", "boolean"}:
            index += 1
            continue

        depth = 1
        close_index = index + 1
        while close_index < len(tokens):
            close_symbol = getattr(tokens[close_index], "val", None)
            if close_symbol == "[":
                depth += 1
            elif close_symbol == "]":
                depth -= 1
                if depth == 0:
                    break
            close_index += 1
        if close_index >= len(tokens):
            raise SyntaxError("No closing ']' found for array literal")

        element_tokens = tokens[index + 1:close_index]
        generate_trees(t, function_names, helper, element_tokens, namespace, memory, types, 0)
        array_literal = t.array(element_tokens)
        tokens[index:close_index + 1] = [array_literal]
        index += 1

def _dereference_vars(start_index, tokens, t, helper, namespace, memory):
    index = start_index
    # Pass 2: dereference variables.
    while index < len(tokens):
        if isinstance(tokens[index], t.var_ref):
            tokens[index] = helper.dereference_var(t, namespace, memory, tokens[index])
        index += 1

def _build_add_sub_mult_div_nodes(start_index, tokens, helper, t, function_names, namespace, memory, user_functions, types):
    index = start_index

    def _is_unary_context(operator_index: int) -> bool:
        """Return True when '+' or '-' is being used as a unary sign."""
        if operator_index == 0:
            return True

        previous_token = tokens[operator_index - 1]
        previous_symbol = getattr(previous_token, "val", None)

        # If previous token is value-like, sign should be treated as binary.
        if previous_symbol in (")", "]"):
            return False
        if isinstance(previous_token, (t.integer, t.boolean, t.string, t.char, t.array, t.var_ref)):
            return False

        # Delimiters/operators indicate a new expression segment.
        return previous_symbol in {"(", "[", "{", ",", "=", "+", "-", "*", "/", "%", "!", "<", ">", "->"}

    # Pass 3: build multiplication/division nodes first (higher precedence).
    while index < len(tokens):
        symbol = getattr(tokens[index], "val", None)
        if symbol == "*":
            helper.validate_operator(tokens, index, "*")
            operation_node = mult(tokens[index - 1], tokens[index + 1])
            # Replace "left op right" with one operator node.
            tokens[index - 1:index + 2] = [operation_node]
            # Ensure the right side is also reduced if it is complex.
            generate_trees(t, function_names, helper, operation_node.node2, namespace, memory, user_functions, types, 0)

        elif symbol == "/":
            helper.validate_operator(tokens, index, "/")
            operation_node = div(tokens[index - 1], tokens[index + 1])
            tokens[index - 1:index + 2] = [operation_node]
            generate_trees(t, function_names, helper, operation_node.node2, namespace, memory, user_functions, types, 0)

        else:
            # Advance only when we did not collapse a slice.
            index += 1

    index = start_index
    # Pass 4: build addition/subtraction nodes (lower precedence).
    while index < len(tokens):
        symbol = getattr(tokens[index], "val", None)
        if symbol == "+":
            if _is_unary_context(index):
                if index + 1 >= len(tokens):
                    raise SyntaxError("Unary '+' must be followed by a value.")
                # Unary '+' is a no-op for the following expression/value.
                tokens.pop(index)
                continue

            helper.validate_operator(tokens, index, "+")
            operation_node = add(tokens[index - 1], tokens[index + 1])
            tokens[index - 1:index + 2] = [operation_node]
            generate_trees(t, function_names, helper, operation_node.node2, namespace, memory, user_functions, types, 0)

        elif symbol == "-":
            if _is_unary_context(index):
                if index + 1 >= len(tokens):
                    raise SyntaxError("Unary '-' must be followed by a value.")

                # Fast path: fold negative numeric literals (e.g. '-15').
                if isinstance(tokens[index + 1], t.integer):
                    tokens[index + 1].val *= -1
                    tokens.pop(index)
                    continue

                # General path: rewrite unary negation as (0 - rhs_expression).
                unary_rhs = tokens[index + 1]

                # Keep numeric node types aligned (e.g. i8 rhs => i8 zero) to avoid mixed-int errors.
                if isinstance(unary_rhs, t.integer) and type(unary_rhs) is not t.integer:
                    zero_node = type(unary_rhs)(0)
                else:
                    zero_node = t.i32(0)

                operation_node = sub(zero_node, unary_rhs)
                tokens[index:index + 2] = [operation_node]
                generate_trees(t, function_names, helper, operation_node.node2, namespace, memory, user_functions, types, 0)
                continue

            # Binary subtraction.
            helper.validate_operator(tokens, index, "-")
            operation_node = sub(tokens[index - 1], tokens[index + 1])
            tokens[index - 1:index + 2] = [operation_node]
            generate_trees(t, function_names, helper, operation_node.node2, namespace, memory, user_functions, types, 0)

        else:
            # Advance only when we did not collapse a slice.
            index += 1

def _build_opers(t, function_names, helper, tokens, namespace, memory, start_idx, user_functions, types):
    index = start_idx
    while index < len(tokens):
        symbol = getattr(tokens[index], "val", None)
        match symbol:
            case "=":
                _check_oper_syntax_errors('=', tokens, index)

                # If previous token is !, <, or >, this '=' belongs to a two-char comparator
                # and should be handled by that previous operator token.
                prev_symbol = getattr(tokens[index - 1], "val", None) if index - 1 >= 0 else None
                if prev_symbol in ("!", "<", ">"):
                    index += 1
                    continue

                next_symbol = getattr(tokens[index + 1], "val", None)
                match next_symbol: # next token
                    case "=": # '==' equality operator
                        build_equal_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types)
                    case _: # '=' assignment operator
                        build_assign_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types)
            case "!":

                match tokens[index + 1].val: # next token 
                    case "!": # '!!' truthy operator
                        _check_oper_syntax_errors('!!', tokens, index)
                        pass
                    case "=": # '!=' not equal to operator
                        _check_oper_syntax_errors('!=', tokens, index)
                        build_not_equal_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types)
                    case _: # '!' boolean invert operator
                        if index + 1 >= len(tokens):
                            raise SyntaxError("operator `!` must be followed by a value.")
                        
                        build_invert_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types)
            case ">":
                _check_oper_syntax_errors('>', tokens, index)
                next_symbol = getattr(tokens[index + 1], "val", None)
                if next_symbol == "=":
                    build_greater_equal_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types)
                else:
                    build_greater_oper(t, function_names, helper, tokens, index, namespace, memory)
            case "<":
                _check_oper_syntax_errors('<', tokens, index)
                next_symbol = getattr(tokens[index + 1], "val", None)
                if next_symbol == "=":
                    build_less_equal_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types)
                else:
                    build_less_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types)
            case "+":
                match tokens[index + 1].val: # next token 
                    case "=": # '+=' 
                        _check_oper_syntax_errors('+=', tokens, index)
                        build_var_add_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types)
                    case "+": # '++' increment operator
                        _check_oper_syntax_errors('++', tokens, index)
                        build_increment_oper(t, helper, tokens, index, namespace, memory)
                    case _: # '+' add operator
                        pass # handled at a different time
            case "-":
                match tokens[index + 1].val: # next token 
                    case "=": # '-=' 
                        _check_oper_syntax_errors('-=', tokens, index)
                        build_var_sub_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types)
                    case "-": # '--' decrement operator
                        _check_oper_syntax_errors('--', tokens, index)
                        build_decrement_oper(t, helper, tokens, index, namespace, memory)
                    case ">": # -> arrow operator for type casting
                        _check_oper_syntax_errors('->', tokens, index)
                        build_cast_oper(t, tokens, index, types)
                    case _: # '+' add operator
                        pass # handled at a different time
            case "^":
                build_free_oper(tokens, index)
        index += 1

def _check_oper_syntax_errors(oper: str, tokens, index):
    if index + 1 >= len(tokens):
        raise SyntaxError(f"operator `{oper}` must be followed by a value.")
    if index < 1:
        raise SyntaxError(f"operator `{oper}` must be preceded by a value.")