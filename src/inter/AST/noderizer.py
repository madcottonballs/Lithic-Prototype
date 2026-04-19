"""This module builds operator nodes for expressions, such as addition, subtraction, equality checks, etc. It also handles parsing of array type declarations and literals, as well as variable dereferencing."""
from AST.noderizer_build_oper import *

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
class double(oper):
    pass
class halve(oper):
    pass


class equal(oper):
    pass
class not_equal(oper):
    pass
class gtr_than(oper):
    pass
class less_than(oper):
    pass
class gtr_than_or_equal(oper):
    pass
class less_than_or_equal(oper):
    pass

class mono_oper():
    def __init__(self, node):
        self.node = node
class invert(mono_oper):
    pass
class free(mono_oper):
    pass
class memloc(mono_oper):
    pass

class mult(oper):
    pass
class div(oper):
    pass
class add(oper):
    pass
class sub(oper):
    pass
class index_oper(oper):
    pass
class subexp():
    # Parenthesized sub-expression node, containing a nested token list/tree.
    def __init__(self, val: list):
        self.val = val
class dot_oper(oper): # used for accessing an attribute
    pass

class at_func_return:
    """Exists so @(ptr, type, idx) function can return a obj to be fed specifically to assign_oper. self.val holds a ltc_type read from memory."""
    def __init__(self, val, addr, type_size, index=0):
        self.val = val
        self.addr = addr
        self.type_size = type_size
        self.index = index


# mother function
def generate_trees(tokens, ltc, start_index=0):
    """Build nodes"""
    # Non-list inputs are already single nodes and do not need list-based passes.
    if not isinstance(tokens, list):
        return

    # Pass 0: collapse raw parenthesized ranges into `subexp` nodes.
    build_subexp(start_index, tokens, ltc)
    # Pass 1: collapse array type declarations like `i32[4]` or `ptr[length(x)]`
    # into one array token.
    _build_array_type_tokens(tokens, ltc, start_index)
    # Pass 1.25: collapse array literals like `[1, 2]` into one `array` token.
    _build_array_literals(tokens, ltc, start_index)
    # Pass 1.5: convert let statements in intended syntax to a function node.
    # Examples:
    #   let i32 x = 5  -> function("let", [i32, x, =, 5])
    #   let i32 x      -> function("let", [i32, x])
    _build_let_stmts(start_index, tokens, ltc)

    # Indexing has higher precedence than arithmetic/comparisons.
    _build_indexing(start_index, tokens, ltc)
    _build_dot_access(start_index, tokens, ltc)
    
    _build_add_sub_mult_div_nodes(start_index, tokens, ltc)
    _build_opers(tokens, start_index, ltc)

def _build_dot_access(start_index, tokens, ltc):
    t = ltc.t
    index = start_index
    while index < len(tokens):
        if type(tokens[index]) is not t.token or getattr(tokens[index], "val", None) != ".":
            index += 1
            continue

        build_dot_oper(tokens, index, ltc)
        collapsed_index = max(index - 1, 0)
        if (
            collapsed_index + 1 < len(tokens)
            and isinstance(tokens[collapsed_index], dot_oper | index_oper)
            and isinstance(tokens[collapsed_index + 1], t.array)
            and tokens[collapsed_index + 1].get_size() == 1
        ):
            _build_index_node(tokens[collapsed_index], tokens[collapsed_index + 1], tokens, collapsed_index, ltc)

        index = max(collapsed_index, start_index)

def _build_indexing(start_index, tokens, ltc):
    index = start_index
    while index < len(tokens):

        if index + 1 >= len(tokens):
            return # no more indexing possible, might as well return
        
        current_token = tokens[index]
        next_token = tokens[index + 1]
        type_of_current_token = type(current_token).__name__
        type_of_next_token = type(next_token).__name__
        match type_of_current_token:
            case "var_ref" | "ptr" | "array" | "string" | "ltctuple":
                if type_of_next_token == "array" and next_token.get_size() == 1:
                    _build_index_node(current_token, next_token, tokens, index, ltc)
            case "memloc":
                if type_of_next_token == "array" and next_token.get_size() == 1:
                    index_token = next_token.val[0]
                    current_token.node = index_oper(current_token.node, index_token)
                    tokens[index:index + 2] = [current_token]
        index += 1

def _build_index_node(current_token, next_token, tokens, index, ltc):
    t = ltc.t
    if not isinstance(next_token, t.array) or next_token.get_size() != 1:
        ltc.error("Indexed access expects exactly one index: obj[idx]")
    index_token = next_token.val[0]
    tokens[index:index + 2] = [index_oper(current_token, index_token)]

def build_array_set_call(lhs_ref, lhs_index_token, rhs_value, ltc):
    t = ltc.t
    """Build aSet(arrayRef, index, rhs) function node and replace current statement."""
    if not isinstance(lhs_ref, t.var_ref):
        ltc.error("Indexed assignment requires a variable reference as the array base")
    args = [
        lhs_ref,
        t.token(","),
        lhs_index_token,
        t.token(","),   
        rhs_value,
    ]

    return t.function("aSet", args, ltc)

def build_tuple_set_call(lhs_ref, lhs_index_token, rhs_value, ltc):
    t = ltc.t
    """Build tSet(tupleRef, index, rhs) function node and replace current statement."""
    if not isinstance(lhs_ref, t.var_ref):
        ltc.error("Indexed assignment requires a variable reference as the tuple base")
    args = [
        lhs_ref,
        t.token(","),
        lhs_index_token,
        t.token(","),   
        rhs_value,
    ]

    return t.function("tSet", args, ltc)


def _build_let_stmts(start_index, tokens, ltc):
    t = ltc.t
    index = start_index
    while index < len(tokens):
        if type(tokens[index]) is not t.token:
            index += 1
            continue
        symbol = getattr(tokens[index], "val", None)

        if symbol == "let" and not isinstance(tokens[index], t.function):
            next_symbol = tokens[index + 1].val if index + 1 < len(tokens) else None
            if next_symbol == "(":
                index += 1
                continue
            if index + 2 >= len(tokens):
                ltc.error("let expects syntax: let [type] [varname] OR let [type] [varname] = [value]")

                # Support bare declarations: let <type> <name>
            if index + 3 >= len(tokens) or tokens[index + 3].val != "=":
                arguments = tokens[index + 1:index + 3]
                tokens[index:index + 3] = [t.function("let", arguments, ltc)]
            else:
                # Support declarations with assignment: let <type> <name> = <full expression>
                if index + 4 >= len(tokens):
                    ltc.error("let assignment expects syntax: let [type] [varname] = [value]")

                rhs_tokens = tokens[index + 4:]
                generate_trees(rhs_tokens, ltc, 0)
                if len(rhs_tokens) != 1:
                    ltc.error("let assignment RHS did not reduce to a single value")

                arguments = [tokens[index + 1], tokens[index + 2], tokens[index + 3], rhs_tokens[0]]
                tokens[index:] = [t.function("let", arguments, ltc)]
                return
        index += 1

def _build_array_type_tokens(tokens, ltc, start_index=0):
    """Convert `<type>[<expr>]` into one `t.array` type token.

    Example:
      [token('i32'), token('['), i32(2), token(']')]
      -> [array_token(val='array', arrayType='i32', size=2)]
    """
    t = ltc.t
    index = start_index
    while index + 2 < len(tokens):
        type_token = tokens[index]
        open_bracket = tokens[index + 1]

        is_primitive_type = (
            isinstance(type_token, t.token)
            and not isinstance(type_token, (t.var_ref, t.function, t.i32, t.string, t.boolean, t.array))
            and getattr(type_token, "val", None) in {
                "i32", "i64", "i16", "i8",
                "u32", "u64", "u16", "u8",
                "boolean", "char", "ptr",
            }
        )
        if not is_primitive_type:
            index += 1
            continue

        if getattr(open_bracket, "val", None) != "[":
            index += 1
            continue

        bracket_depth = 1
        close_index = index + 2
        while close_index < len(tokens):
            current_symbol = getattr(tokens[close_index], "val", None)
            if current_symbol == "[":
                bracket_depth += 1
            elif current_symbol == "]":
                bracket_depth -= 1
                if bracket_depth == 0:
                    break
            close_index += 1

        if close_index >= len(tokens) or getattr(tokens[close_index], "val", None) != "]":
            ltc.error("Array type declaration is missing closing ']'")

        size_tokens = tokens[index + 2:close_index]
        if not size_tokens:
            ltc.error("Array type declaration requires a size expression")

        generate_trees(size_tokens, ltc, 0)
        if len(size_tokens) != 1:
            ltc.error("Array size expression did not reduce to a single value")

        size_token = size_tokens[0]

        # Reuse your existing array class as a type token.
        array_type_token = t.array([], ltc, arrayType=type_token.val, parse=False)
        array_type_token.val = "array"
        if isinstance(size_token, t.integer):
            if size_token.val < 0:
                ltc.error("Array size cannot be negative")
            array_type_token.size = size_token.val
        else:
            array_type_token.size = None
            array_type_token.size_expr = size_token
        array_type_token.is_type_constructor = True
        tokens[index:close_index + 1] = [array_type_token]
        # Do not increment index so chained patterns still get parsed correctly.

def _build_array_literals(tokens, ltc, start_index=0):
    """Convert `[elem1, elem2, ...]` into one `t.array` token."""
    index = start_index
    while index < len(tokens):
        if type(tokens[index]) is not ltc.t.token:
            index += 1
            continue
        symbol = getattr(tokens[index], "val", None)
        if symbol != "[":
            index += 1
            continue

        # Skip array type declarations that were not reduced for any reason.
        prev_symbol = getattr(tokens[index - 1], "val", None) if index > 0 else None
        if prev_symbol in {"i32", "i64", "i16", "i8", "u32", "u64", "u16", "u8", "ptr", "boolean", "char"}:
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
            ltc.error("No closing ']' found for array literal")

        element_tokens = tokens[index + 1:close_index]
        generate_trees(element_tokens, ltc, 0)
        array_literal = ltc.t.array(element_tokens, ltc, arrayType=None, parse=True)
        tokens[index:close_index + 1] = [array_literal]
        index += 1

def _dereference_vars(start_index, tokens, ltc):
    t = ltc.t
    helper = ltc.helper    
    index = start_index
    # Pass 2: dereference variables.
    while index < len(tokens):
        if isinstance(tokens[index], t.var_ref):
            tokens[index] = helper.dereference_var(ltc, tokens[index])
        index += 1

def _build_add_sub_mult_div_nodes(start_index, tokens, ltc):
    t = ltc.t
    helper = ltc.helper
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
        if isinstance(previous_token, (t.ltc_type, t.var_ref, subexp, oper, mono_oper)):
            return False

        # Non-string previous symbols are value-like (e.g. numeric literals), so treat '+'/'-' as binary.
        if not isinstance(previous_symbol, str):
            return False

        return previous_symbol in {"(", "[", "{", ",", "=", "+", "-", "*", "/", "%", "!", "<", ">", "->"}

    # Pass 3: build multiplication/division nodes first (higher precedence).
    while index < len(tokens):
        if type(tokens[index]) is not t.token:
            index += 1
            continue
        symbol = getattr(tokens[index], "val", None)
        if symbol == "*":
            next_symbol = getattr(tokens[index + 1], "val", None) if index + 1 < len(tokens) else None
            if next_symbol in ("=", "*"):
                index += 2
                continue
            helper.validate_operator(tokens, index, "*", ltc)
            operation_node = mult(tokens[index - 1], tokens[index + 1])
            # Replace "left op right" with one operator node.
            tokens[index - 1:index + 2] = [operation_node]
            # Ensure the right side is also reduced if it is complex.
            generate_trees(operation_node.node2, ltc, 0)

        elif symbol == "/":
            next_symbol = getattr(tokens[index + 1], "val", None) if index + 1 < len(tokens) else None
            if next_symbol in ("=", "/"):
                index += 2
                continue
            helper.validate_operator(tokens, index, "/", ltc)
            operation_node = div(tokens[index - 1], tokens[index + 1])
            tokens[index - 1:index + 2] = [operation_node]
            generate_trees(operation_node.node2, ltc, 0)

        else:
            # Advance only when we did not collapse a slice.
            index += 1

    index = start_index
    # Pass 4: build addition/subtraction nodes (lower precedence).
    while index < len(tokens):
        if type(tokens[index]) is not t.token:
            index += 1
            continue
        symbol = getattr(tokens[index], "val", None)
        if symbol == "+":
            next_symbol = getattr(tokens[index + 1], "val", None) if index + 1 < len(tokens) else None
            if next_symbol in ("=", "+"):
                index += 2
                continue
            if _is_unary_context(index):
                if index + 1 >= len(tokens):
                    ltc.error("Unary '+' must be followed by a value.")
                # Unary '+' is a no-op for the following expression/value.
                tokens.pop(index)
                continue

            helper.validate_operator(tokens, index, "+", ltc)
            operation_node = add(tokens[index - 1], tokens[index + 1])
            tokens[index - 1:index + 2] = [operation_node]
            generate_trees(operation_node.node2, ltc, 0)

        elif symbol == "-":
            # Preserve arrow operator "->" for the cast pass.
            next_symbol = getattr(tokens[index + 1], "val", None) if index + 1 < len(tokens) else None
            if next_symbol in (">", "=", "-"):
                index += 2
                continue
            if _is_unary_context(index):
                if index + 1 >= len(tokens):
                    ltc.error("Unary '-' must be followed by a value.")

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
                    zero_node = t.i32(0, ltc)

                operation_node = sub(zero_node, unary_rhs)
                tokens[index:index + 2] = [operation_node]
                generate_trees(operation_node.node2, ltc, 0)
                continue

            # Binary subtraction.
            helper.validate_operator(tokens, index, "-", ltc)
            operation_node = sub(tokens[index - 1], tokens[index + 1])
            tokens[index - 1:index + 2] = [operation_node]
            generate_trees(operation_node.node2, ltc, 0)

        else:
            # Advance only when we did not collapse a slice.
            index += 1

def _resolve_index_token_to_dword(index_token, ltc):
    """Resolve index token to i32 for indexed operations."""
    t = ltc.t
    helper = ltc.helper    
    resolved_index = index_token
    if isinstance(resolved_index, t.var_ref):
        resolved_index = helper.dereference_var(ltc, resolved_index)
    elif isinstance(resolved_index, t.token):
        if helper.locate_var_in_namespace(ltc.namespace, resolved_index.val, return_just_the_check=True):
            resolved_index = helper.dereference_var(ltc, t.var_ref(resolved_index.val))
        elif str(resolved_index.val).isdigit():
            resolved_index = t.i32(resolved_index.val, ltc)

    if not isinstance(resolved_index, t.integer):
        ltc.error("Index must resolve to an integer")

    return resolved_index

def _build_opers(tokens, start_idx, ltc):
    t = ltc.t
    index = start_idx
    while index < len(tokens):
        if type(tokens[index]) is not t.token:
            index += 1
            continue
        symbol = getattr(tokens[index], "val", None)
        match symbol:
            case "=":
                _check_oper_syntax_errors(ltc, '=', tokens, index)

                # If previous token is !, <, or >, this '=' belongs to a two-char comparator
                # and should be handled by that previous operator token.
                prev_symbol = getattr(tokens[index - 1], "val", None) if index - 1 >= 0 else None
                if prev_symbol in ("!", "<", ">"):
                    index += 1
                    continue

                next_symbol = getattr(tokens[index + 1], "val", None)
                match next_symbol: # next token
                    case "=": # '==' equality operator
                        build_equal_oper(tokens, index, ltc)
                    case _: # '=' assignment operator
                        build_assign_oper(tokens, index, ltc)
            case "!":

                match tokens[index + 1].val: # next token 
                    case "!": # '!!' truthy operator
                        _check_oper_syntax_errors(ltc, '!!', tokens, index)
                        pass
                    case "=": # '!=' not equal to operator
                        _check_oper_syntax_errors(ltc, '!=', tokens, index)
                        build_not_equal_oper(tokens, index, ltc)
                    case _: # '!' boolean invert operator
                        if index + 1 >= len(tokens):
                            ltc.error("operator `!` must be followed by a value.")
                        
                        build_invert_oper(tokens, index, ltc)
            case "not":
                if index + 1 >= len(tokens):
                    ltc.error("operator `not` must be followed by a value.")
                build_invert_oper(tokens, index, ltc)
            case ">":
                _check_oper_syntax_errors(ltc, '>', tokens, index)
                next_symbol = getattr(tokens[index + 1], "val", None)
                if next_symbol == "=":
                    build_greater_equal_oper(tokens, index, ltc)
                else:
                    build_greater_oper(tokens, index, ltc)
            case "<":
                _check_oper_syntax_errors(ltc, '<', tokens, index)
                next_symbol = getattr(tokens[index + 1], "val", None)
                if next_symbol == "=":
                    build_less_equal_oper(tokens, index, ltc)
                else:
                    build_less_oper(tokens, index, ltc)
            case "+":
                match tokens[index + 1].val: # next token 
                    case "=": # '+=' 
                        _check_oper_syntax_errors(ltc, '+=', tokens, index)
                        build_unified_oper_assign(tokens, index, ltc, "+=")
                    case "+": # '++' increment operator
                        _check_oper_syntax_errors(ltc, '++', tokens, index)
                        build_var_mod_shortcut_oper(tokens, index, "++", ltc)
                    case _: # '+' add operator
                        pass # handled at a different time
            case "-":
                match tokens[index + 1].val: # next token 
                    case "=": # '-=' 
                        _check_oper_syntax_errors(ltc, '-=', tokens, index)
                        build_unified_oper_assign(tokens, index, ltc, "-=")
                    case "-": # '--' decrement operator
                        _check_oper_syntax_errors(ltc, '--', tokens, index)
                        build_var_mod_shortcut_oper(tokens, index, "--", ltc)
                    case ">": # -> arrow operator for type casting
                        _check_oper_syntax_errors(ltc, '->', tokens, index)
                        build_cast_oper(tokens, index, ltc)
                        index -= 1  # re-scan after in-place replacement
                    case _: # '+' add operator
                        pass # handled at a different time
            case "*":
                match tokens[index + 1].val: # next token 
                    case "=": # '*=' 
                        _check_oper_syntax_errors(ltc, '*=', tokens, index)
                        build_unified_oper_assign(tokens, index, ltc, "*=")
                    case "*": # '**' exponentiation operator
                        _check_oper_syntax_errors(ltc, '**', tokens, index)
                        build_var_mod_shortcut_oper(tokens, index, "**", ltc)
                    case _: # '*' multiply operator
                        pass # handled at a different time
            case "/":
                match tokens[index + 1].val: # next token 
                    case "=": # '/=' 
                        _check_oper_syntax_errors(ltc, '/=', tokens, index)
                        build_unified_oper_assign(tokens, index, ltc, "/=")
                    case "/": # '//' floor division operator
                        _check_oper_syntax_errors(ltc, '//', tokens, index)
                        build_var_mod_shortcut_oper(tokens, index, "//", ltc)
                    case _: # '*' multiply operator
                        pass # handled at a different time
            case "^":
                build_free_oper(tokens, index, ltc)
            case "&":
                build_memloc_oper(tokens, index, ltc)
            case ".":
                build_dot_oper(tokens, index, ltc)
                collapsed_index = max(index - 1, 0)
                if (
                    collapsed_index + 1 < len(tokens)
                    and isinstance(tokens[collapsed_index], dot_oper | index_oper)
                    and type(tokens[collapsed_index + 1]).__name__ == "array"
                    and tokens[collapsed_index + 1].get_size() == 1
                ):
                    _build_index_node(tokens[collapsed_index], tokens[collapsed_index + 1], tokens, collapsed_index, ltc)
                # Re-scan from the replacement point so chained dots and a following
                # assignment like `b.x = 20` both get collapsed in the same pass.
                index -= 1
        index += 1

def _check_oper_syntax_errors(ltc, oper: str, tokens, index):
    if index + 1 >= len(tokens):
        ltc.error(f"operator `{oper}` must be followed by a value.")
    if index < 1:
        ltc.error(f"operator `{oper}` must be preceded by a value.")
