"""This module contains functions that build specific operator nodes during the noderization process. Each function corresponds to a specific operator and is responsible for transforming the relevant tokens into the appropriate node in the abstract syntax tree (AST). These functions are called by noderizer.py when it encounters the corresponding operators in the token stream."""
# import * only brings functions from noderizer into this file
import noderizer as n 

def build_subexp(start_idx, tokens, helper, t, function_names, namespace, memory, user_functions, types):
    index = start_idx
    while index < len(tokens):
        symbol = getattr(tokens[index], "val", None)
        if symbol == "(":
            helper.find_closing_parenthesis(index, tokens, n.subexp)
            # `tokens[index]` is now the new `subexp` at this position.
            n.generate_trees(t, function_names, helper, tokens[index].val, namespace, memory, user_functions, types)
            previous_symbol = getattr(tokens[index - 1], "val", None)
            if isinstance(previous_symbol, str) and previous_symbol in function_names and not isinstance(tokens[index - 1], t.function):
                # This is a function call with parentheses already collapsed into a `subexp`.
                # Convert it into a function node and keep only that node.
                arguments = tokens[index].val
                if not any(getattr(tok, "val", None) == "," for tok in arguments):
                    arguments = [n.subexp(arguments)]
                tokens[index - 1] = t.function(tokens[index - 1].val, arguments)
                del tokens[index]
                index -= 1
            if isinstance(previous_symbol, str) and previous_symbol in user_functions and not isinstance(tokens[index - 1], t.user_function):
                # This is a user_function call with parentheses already collapsed into a `subexp`.
                # Convert it into a user_function node and keep only that node.
                arguments = tokens[index].val
                if not any(getattr(tok, "val", None) == "," for tok in arguments):
                    arguments = [n.subexp(arguments)]
                tokens[index - 1] = t.user_function(tokens[index - 1].val, arguments)
                del tokens[index]
                index -= 1
        index += 1

def build_assign_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types):
    # Assignment consumes the whole remaining RHS expression on this statement.
    rhs_tokens = tokens[index + 1:]
    n.generate_trees(t, function_names, helper, rhs_tokens, namespace, memory, user_functions, types, 0)
    if len(rhs_tokens) != 1:
        raise SyntaxError("right hand side during assignment did not reduce to a single value")

    # Indexed write rewrite: x[i] = rhs  ->  aSet(x, i, rhs)
    if index >= 2 and isinstance(tokens[index - 2], t.var_ref) and isinstance(tokens[index - 1], t.array) and tokens[index - 1].get_size() == 1:
        set_call = n.build_array_set_call(t, helper, tokens, tokens[index - 2], tokens[index - 1], rhs_tokens[0], namespace, memory)
        tokens[index - 2:] = [set_call]
        return

    assign_node = n.assign(tokens[index - 1], rhs_tokens[0])
    tokens[index - 1:] = [assign_node]

def build_var_add_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types):
    # Build: x += expr  ->  n.assign(x, n.add(value_of_x, expr))
    if index + 2 >= len(tokens):
        raise SyntaxError("operator `+=` must be followed by a value.")

    lhs_ref = tokens[index - 1]
    if not isinstance(lhs_ref, t.var_ref):
        raise TypeError("Left side of '+=' must be a variable reference")

    # Parse and reduce the RHS expression after '+='.
    rhs_tokens = tokens[index + 2:]
    n.generate_trees(t, function_names, helper, rhs_tokens, namespace, memory, user_functions, types, 0)
    if len(rhs_tokens) != 1:
        raise SyntaxError("right hand side during '+=' did not reduce to a single value")

    lhs_value = helper.dereference_var(t, namespace, memory, lhs_ref)
    add_node = n.add(lhs_value, rhs_tokens[0])
    assign_node = n.assign(lhs_ref, add_node)
    tokens[index - 1:] = [assign_node]

def build_var_sub_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types):
    # Build: x -= expr  ->  n.assign(x, n.sub(value_of_x, expr))
    if index + 2 >= len(tokens):
        raise SyntaxError("operator `-=` must be followed by a value.")

    lhs_ref = tokens[index - 1]
    if not isinstance(lhs_ref, t.var_ref):
        raise TypeError("Left side of '-=' must be a variable reference")

    # Parse and reduce the RHS expression after '-='.
    rhs_tokens = tokens[index + 2:]
    n.generate_trees(t, function_names, helper, rhs_tokens, namespace, memory, user_functions, types, 0)
    if len(rhs_tokens) != 1:
        raise SyntaxError("right hand side during '-=' did not reduce to a single value")

    lhs_value = helper.dereference_var(t, namespace, memory, lhs_ref)
    sub_node = n.sub(lhs_value, rhs_tokens[0])
    assign_node = n.assign(lhs_ref, sub_node)
    tokens[index - 1:] = [assign_node]

def build_decrement_oper(t, helper, tokens, index, namespace, memory):
    # Build: x--  ->  n.assign(x, n.sub(value_of_x, 1))
    lhs_ref = tokens[index - 1]

    # Indexed decrement rewrite: x[i]--  ->  aSet(x, i, x[i] - 1)
    if index >= 2 and isinstance(tokens[index - 2], t.var_ref) and isinstance(tokens[index - 1], t.array) and tokens[index - 1].get_size() == 1:
        array_ref = tokens[index - 2]
        index_token = n._resolve_index_token_to_dword(tokens[index - 1].val[0], t, helper, namespace, memory)
        array_value = helper.dereference_var(t, namespace, memory, array_ref)
        if index_token.val < 0 or index_token.val >= array_value.get_size():
            raise SyntaxError(f"Tried to index an array of size {array_value.get_size()} with an index of {index_token.val}")
        current_value = array_value.val[index_token.val]
        if not isinstance(current_value, t.integer):
            raise TypeError("array[idx]-- currently supports integer array elements only")

        sub_node = n.sub(current_value, type(current_value)(1))
        set_call = n.build_array_set_call(t, helper, tokens, array_ref, tokens[index - 1], sub_node, namespace, memory)
        tokens[index - 2:index + 2] = [set_call]
        return

    if not isinstance(lhs_ref, t.var_ref):
        raise TypeError("Left side of '--' must be a variable reference")

    lhs_value = helper.dereference_var(t, namespace, memory, lhs_ref)
    sub_node = n.sub(lhs_value, type(lhs_value)(1))
    assign_node = n.assign(lhs_ref, sub_node)
    tokens[index - 1:index + 2] = [assign_node]

def build_increment_oper(t, helper, tokens, index, namespace, memory):
    # Build: x++  ->  n.assign(x, n.add(value_of_x, 1))
    lhs_ref = tokens[index - 1]

    # Indexed increment rewrite: x[i]++  ->  aSet(x, i, x[i] + 1)
    if index >= 2 and isinstance(tokens[index - 2], t.var_ref) and isinstance(tokens[index - 1], t.array) and tokens[index - 1].get_size() == 1:
        array_ref = tokens[index - 2]
        index_token = n._resolve_index_token_to_dword(tokens[index - 1].val[0], t, helper, namespace, memory)
        array_value: list[n.integer] = helper.dereference_var(t, namespace, memory, array_ref)

        if index_token.val < 0 or index_token.val >= array_value.get_size():
            raise SyntaxError(f"Tried to index an array of size {array_value.get_size()} with an index of {index_token.val}")
        
        current_value = array_value.val[index_token.val]
        if not isinstance(current_value, t.integer):
            raise TypeError(f"For arrays, increment operator currently supports incrementing integer[] arrays, not {type(current_value).__name__}")

        add_node = n.add(current_value, type(current_value)(1))
        set_call = n.build_array_set_call(t, helper, tokens, array_ref, tokens[index - 1], add_node, namespace, memory)
        tokens[index - 2:index + 2] = [set_call]
        return

    if not isinstance(lhs_ref, t.var_ref):
        raise TypeError("Left side of '++' must be a variable reference")

    lhs_value = helper.dereference_var(t, namespace, memory, lhs_ref)
    add_node = n.add(lhs_value, type(lhs_value)(1))
    assign_node = n.assign(lhs_ref, add_node)
    tokens[index - 1:index + 2] = [assign_node]

def build_equal_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types):
    equal_node = n.equal(tokens[index - 1], tokens[index + 2])
    tokens[index - 1:index + 3] = [equal_node]
    
    n.generate_trees(t, function_names, helper, equal_node.node1, namespace, memory, user_functions, types, 0)
    n.generate_trees(t, function_names, helper, equal_node.node2, namespace, memory, user_functions, types, 0)

def build_invert_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types):
    new_node = n.invert(tokens[index + 1])
    tokens[index:index + 2] = [new_node]
    
    n.generate_trees(t, function_names, helper, new_node.node, namespace, memory, user_functions, types, 0)

def build_not_equal_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types):
    new_node = n.not_equal(tokens[index - 1], tokens[index + 2])
    tokens[index - 1:index + 3] = [new_node]

    n.generate_trees(t, function_names, helper, new_node.node1, namespace, memory, user_functions, types, 0)
    n.generate_trees(t, function_names, helper, new_node.node2, namespace, memory, user_functions, types, 0)

def build_greater_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types):
    new_node = n.gtr_than(tokens[index - 1], tokens[index + 1])
    tokens[index - 1:index + 2] = [new_node]

    n.generate_trees(t, function_names, helper, new_node.node1, namespace, memory, user_functions, types, 0)
    n.generate_trees(t, function_names, helper, new_node.node2, namespace, memory, 0)

def build_less_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types):
    new_node = n.less_than(tokens[index - 1], tokens[index + 1])
    tokens[index - 1:index + 2] = [new_node]

    n.generate_trees(t, function_names, helper, new_node.node1, namespace, memory, user_functions, types, 0)
    n.generate_trees(t, function_names, helper, new_node.node2, namespace, memory, user_functions, types, 0)

def build_greater_equal_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types):
    new_node = n.gtr_than_or_equal(tokens[index - 1], tokens[index + 2])
    tokens[index - 1:index + 3] = [new_node]

    n.generate_trees(t, function_names, helper, new_node.node1, namespace, memory, user_functions,0)
    n.generate_trees(t, function_names, helper, new_node.node2, namespace, memory, user_functions, types, 0)

def build_less_equal_oper(t, function_names, helper, tokens, index, namespace, memory, user_functions, types):
    new_node = n.less_than_or_equal(tokens[index - 1], tokens[index + 2])
    tokens[index - 1:index + 3] = [new_node]

    n.generate_trees(t, function_names, helper, new_node.node1, namespace, memory, user_functions, types, 0)
    n.generate_trees(t, function_names, helper, new_node.node2, namespace, memory, user_functions, types, 0)

def build_free_oper(tokens, index):
    if index <= 0:
        raise SyntaxError("Tried to call a free operator before the var_ref")
    
    new_node = n.free(tokens[index - 1])
    tokens[index-1:index + 1] = [new_node]

def build_cast_oper(t, tokens, index, types: dict[str, type]):
    if index + 2 >= len(tokens):
        raise SyntaxError("operator `->` must be followed by a type to cast to.")
    type_token = tokens[index + 2]
    if not isinstance(type_token, t.token) or type_token.val not in types.keys():
        raise SyntaxError("operator `->` must be followed by a valid type token like 'i32' or 'string'.")
    
    cast_node = t.function("cast", [tokens[index - 1], t.token(","), type_token]) # turns the operator into a function call like cast(x, i32)
    tokens[index - 1:index + 3] = [cast_node]
    
def build_memloc_oper(tokens, index):
    if index >= len(tokens):
        raise SyntaxError("Tried to call a memloc operator without a following object to take the memloc of")
    
    new_node = n.memloc(tokens[index + 1])
    tokens[index:index + 2] = [new_node]