"""This module contains functions that build specific operator nodes during the noderization process. Each function corresponds to a specific operator and is responsible for transforming the relevant tokens into the appropriate node in the abstract syntax tree (AST). These functions are called by noderizer.py when it encounters the corresponding operators in the token stream."""
# import * only brings functions from noderizer into this file
import AST.noderizer as n

def build_subexp(start_idx, tokens, ltc):
    t = ltc.t
    helper = ltc.helper    
    index = start_idx
    while index < len(tokens):
        symbol = getattr(tokens[index], "val", None)
        if symbol == "(":
            helper.find_closing_parenthesis(index, tokens, n.subexp, ltc)
            # `tokens[index]` is now the new `subexp` at this position.
            n.generate_trees(tokens[index].val, ltc, 0)  # recursively generate trees for the contents of the parentheses
            
            previous_symbol = tokens[index - 1].val
            if isinstance(previous_symbol, str) and previous_symbol in ltc.function_names and not isinstance(tokens[index - 1], t.function):
                # This is a function call with parentheses already collapsed into a `subexp`.
                # Convert it into a function node and keep only that node.
                arguments = tokens[index].val
                if arguments:
                    if not any(getattr(tok, "val", None) == "," for tok in arguments):
                        # Single expression argument; don't wrap if it's already a subexp.
                        if len(arguments) == 1 and isinstance(arguments[0], n.subexp):
                            arguments = [arguments[0]]
                        else:
                            arguments = [n.subexp(arguments)]
                tokens[index - 1] = t.function(tokens[index - 1].val, arguments, ltc)
                del tokens[index]
                index -= 1
            elif isinstance(previous_symbol, str) and previous_symbol in ltc.user_functions and not isinstance(tokens[index - 1], t.user_function):
                # This is a user_function call with parentheses already collapsed into a `subexp`.
                # Convert it into a user_function node and keep only that node.
                arguments = tokens[index].val
                if arguments:
                    if not any(getattr(tok, "val", None) == "," for tok in arguments):
                        # Single expression argument; don't wrap if it's already a subexp.
                        if len(arguments) == 1 and isinstance(arguments[0], n.subexp):
                            arguments = [arguments[0]]
                        else:
                            arguments = [n.subexp(arguments)]
                tokens[index - 1] = t.user_function(tokens[index - 1].val, arguments, ltc)
                del tokens[index]
                index -= 1
            else:
                print(previous_symbol)
        index += 1

def build_assign_oper(tokens, index, ltc):
    t = ltc.t
    # Assignment consumes the whole remaining RHS expression on this statement.
    rhs_tokens = tokens[index + 1:]
    n.generate_trees(rhs_tokens, ltc, 0)
    if len(rhs_tokens) != 1:
        ltc.error("right hand side during assignment did not reduce to a single value")

    if index >= 2:
        # Indexed write rewrite: x[i] = rhs  ->  aSet(...) or tSet(...)
        if isinstance(tokens[index - 1], n.index_oper) and isinstance(tokens[index - 1].node1, t.var_ref):
            lhs_ref = tokens[index - 1].node1
            index_token = tokens[index - 1].node2
            var_meta = ltc.helper.locate_var_in_namespace(ltc.namespace, lhs_ref.val, return_just_the_check=False)[0]
            if var_meta and var_meta.get("type") == "tuple":
                set_call = n.build_tuple_set_call(lhs_ref, index_token, rhs_tokens[0], ltc)
                tokens[index - 1:] = [set_call]
                return
            if var_meta and var_meta.get("type") == "ptr":
                if "tag" not in var_meta:
                    ltc.error(f"Pointer variable '{lhs_ref.val}' is not tagged")
                deref_call = t.function("@", [
                    lhs_ref,
                    t.token(","),
                    t.token(var_meta["tag"]),
                    t.token(","),
                    index_token,
                ], ltc)
                assign_node = n.assign(deref_call, rhs_tokens[0])
                tokens[index - 1:] = [assign_node]
                return
            set_call = n.build_array_set_call(lhs_ref, index_token, rhs_tokens[0], ltc)
            tokens[index - 1:] = [set_call]
            return

        if isinstance(tokens[index - 2], t.var_ref) and isinstance(tokens[index - 1], t.array) and tokens[index - 1].get_size() == 1:
            lhs_ref = tokens[index - 2]
            index_token = tokens[index - 1].val[0]
            var_meta = ltc.helper.locate_var_in_namespace(ltc.namespace, lhs_ref.val, return_just_the_check=False)[0]
            if var_meta and var_meta.get("type") == "tuple":
                set_call = n.build_tuple_set_call(lhs_ref, index_token, rhs_tokens[0], ltc)
                tokens[index - 2:] = [set_call]
                return
            if var_meta and var_meta.get("type") == "ptr":
                if "tag" not in var_meta:
                    ltc.error(f"Pointer variable '{lhs_ref.val}' is not tagged")
                deref_call = t.function("@", [
                    lhs_ref,
                    t.token(","),
                    t.token(var_meta["tag"]),
                    t.token(","),
                    index_token,
                ], ltc)
                assign_node = n.assign(deref_call, rhs_tokens[0])
                tokens[index - 2:] = [assign_node]
                return
            set_call = n.build_array_set_call(lhs_ref, index_token, rhs_tokens[0], ltc)
            tokens[index - 2:] = [set_call]
            return


    assign_node = n.assign(tokens[index - 1], rhs_tokens[0])
    tokens[index - 1:] = [assign_node]

def build_unified_oper_assign(tokens, index, ltc, oper: str):
    """This function is used to handle operators that have a unified operator for both addition and subtraction (like '+=' and '-='). It checks the operator type and then builds the appropriate operation node (like n.add or n.sub) and then creates an assignment node that assigns the result back to the left hand side variable. This is used to reduce code duplication between similar operators."""
    t = ltc.t
    # Example Build: x += expr  ->  n.assign(x, n.add(value_of_x, expr))
    if index + 2 >= len(tokens):
        ltc.error(f"operator `{oper}` must be followed by a value.")

    lhs_ref = tokens[index - 1]
    lhs_ref = handle_var_ref_or_index(tokens, index, oper, lhs_ref, ltc)

    # Parse and reduce the RHS expression after '+='.
    rhs_tokens = tokens[index + 2:]
    n.generate_trees(rhs_tokens, ltc, 0)
    if len(rhs_tokens) != 1:
        ltc.error(f"right hand side during '{oper}' did not reduce to a single value")

    match oper:
        case "+=":
            operation_node = n.add(lhs_ref, rhs_tokens[0])
        case "-=":
            operation_node = n.sub(lhs_ref, rhs_tokens[0])
        case "*=":
            operation_node = n.mult(lhs_ref, rhs_tokens[0])
        case "/=":
            operation_node = n.div(lhs_ref, rhs_tokens[0])
        case _:
            ltc.error(f"Unsupported operator: {oper}")
    assign_node = n.assign(lhs_ref, operation_node)
    tokens[index - 1:] = [assign_node]

def handle_var_ref_or_index(tokens, index, oper, lhs_ref, ltc):
    """This function is used to handle cases where the left hand side of an operator could be either a variable reference or an index operation (like x[i]). It checks the type of the left hand side and if it's not a variable reference or index operation, it tries to build an index operation if the syntax matches that pattern. If it can't, it raises a TypeError. This is used by operators like '++' and '--' that can operate on both variables and indexed expressions."""
    t = ltc.t
    # check if the left hand side is a variable reference or an index operation (like x[i])    
    if not isinstance(lhs_ref, (t.var_ref, n.index_oper)):
        # last chance: try to build a index oper, if we cant, error
        if index >= 2 and isinstance(tokens[index - 2], t.var_ref) and isinstance(tokens[index - 1], t.array) and tokens[index - 1].get_size() == 1:
            return n.index_oper(tokens[index - 2], tokens[index - 1].val[0])
        else:
            ltc.error(f"Left side of '{oper}' must be a variable reference or index expression")
    return lhs_ref

def build_var_mod_shortcut_oper(tokens, index, oper: str, ltc):
    t = ltc.t
    # Build: x++  ->  n.assign(x, n.add(x, 1))
    lhs_ref = tokens[index - 1]

    lhs_ref = handle_var_ref_or_index(tokens, index, oper, lhs_ref, ltc)
    # Use typed literal when LHS is a plain variable reference to avoid i32-only math.
    literal_factory = None
    if isinstance(lhs_ref, t.var_ref):
        lhs_value = ltc.helper.dereference_var(ltc, lhs_ref)
        if isinstance(lhs_value, t.integer):
            literal_factory = type(lhs_value)

    match oper:
        case "++":
            operation_node = n.add(lhs_ref, (literal_factory(1, ltc) if literal_factory else t.i32(1, ltc)))
        case "--":
            operation_node = n.sub(lhs_ref, (literal_factory(1, ltc) if literal_factory else t.i32(1, ltc)))
        case "**":
            operation_node = n.mult(lhs_ref, (literal_factory(2, ltc) if literal_factory else t.i32(2, ltc)))
        case "//":
            operation_node = n.div(lhs_ref, (literal_factory(2, ltc) if literal_factory else t.i32(2, ltc)))
        case _:
            ltc.error(f"Unsupported operator: {oper}")

    assign_node = n.assign(lhs_ref, operation_node)
    tokens[index - 1:index + 2] = [assign_node]


def build_equal_oper(tokens, index, ltc):
    equal_node = n.equal(tokens[index - 1], tokens[index + 2])
    tokens[index - 1:index + 3] = [equal_node]
    
    n.generate_trees(equal_node.node1, ltc, 0)
    n.generate_trees(equal_node.node2, ltc, 0)

def build_invert_oper(tokens, index, ltc):
    new_node = n.invert(tokens[index + 1])
    tokens[index:index + 2] = [new_node]
    
    n.generate_trees(new_node.node, ltc, 0)

def build_not_equal_oper(tokens, index, ltc):
    new_node = n.not_equal(tokens[index - 1], tokens[index + 2])
    tokens[index - 1:index + 3] = [new_node]

    n.generate_trees(new_node.node1, ltc, 0)
    n.generate_trees(new_node.node2, ltc, 0)

def build_greater_oper(tokens, index, ltc):
    new_node = n.gtr_than(tokens[index - 1], tokens[index + 1])
    tokens[index - 1:index + 2] = [new_node]

    n.generate_trees(new_node.node1, ltc, 0)
    n.generate_trees(new_node.node2, ltc, 0)

def build_less_oper(tokens, index, ltc):
    new_node = n.less_than(tokens[index - 1], tokens[index + 1])
    tokens[index - 1:index + 2] = [new_node]

    n.generate_trees(new_node.node1, ltc, 0)
    n.generate_trees(new_node.node2, ltc, 0)

def build_greater_equal_oper(tokens, index, ltc):
    new_node = n.gtr_than_or_equal(tokens[index - 1], tokens[index + 2])
    tokens[index - 1:index + 3] = [new_node]

    n.generate_trees(new_node.node1, ltc, 0)
    n.generate_trees(new_node.node2, ltc, 0)

def build_less_equal_oper(tokens, index, ltc):
    new_node = n.less_than_or_equal(tokens[index - 1], tokens[index + 2])
    tokens[index - 1:index + 3] = [new_node]

    n.generate_trees(new_node.node1, ltc, 0)
    n.generate_trees(new_node.node2, ltc, 0)

def build_free_oper(tokens, index, ltc):
    if index <= 0:
        ltc.error("Tried to call a free operator before the var_ref")
    
    new_node = n.free(tokens[index - 1])
    tokens[index-1:index + 1] = [new_node]

def build_cast_oper(tokens, index, ltc):
    if index + 2 >= len(tokens):
        ltc.error("operator `->` must be followed by a type to cast to.")
    type_token = tokens[index + 2]
    if not isinstance(type_token, ltc.t.token) or type_token.val not in ltc.types.keys():
        ltc.error("operator `->` must be followed by a valid type token like 'i32' or 'string'.")
    
    cast_node = ltc.t.function("cast", [tokens[index - 1], ltc.t.token(","), type_token], ltc) # turns the operator into a function call like cast(x, i32)
    tokens[index - 1:index + 3] = [cast_node]
    
def build_memloc_oper(tokens, index, ltc):
    if index >= len(tokens):
        ltc.error("Tried to call a memloc operator without a following object to take the memloc of")
    
    new_node = n.memloc(tokens[index + 1])
    tokens[index:index + 2] = [new_node]

def build_dot_oper(tokens, index, ltc):
    lhs = tokens[index-1]
    rhs = tokens[index+1]

    if lhs.val in ltc.aliases: # means this is a library function call e.g.: strarr.load()

        lhs = ltc.t.token(lhs.val + "." + rhs.val)
        tokens[index - 1:index + 2] = [lhs]

    else: # this means its a struct.attr e.g.: player.x

        new_node = n.dot_oper(tokens[index - 1], tokens[index + 1])
        tokens[index - 1:index + 2] = [new_node]