import helper as helper
import evaluator as evaluator
import noderizer as noderizer
import typerizer as t
import tokenizer as tokenizer


def execute_statement(stmt: str, memory, namespace, types, stack_frames, sp, user_functions, return_values):
    """Execute one non-control-flow statement and return updated stack pointer."""
    stmt = stmt.strip()
    if not stmt:
        return sp, return_values

    tokens = tokenizer.lexer(stmt)
    t.parser(tokens, namespace, helper, user_functions)
    noderizer.generate_trees(t, function_names, helper, tokens, namespace, memory, user_functions, types, 0)
    sp, return_values = evaluator.evaluate(tokens, memory, namespace, types, noderizer, t, helper, user_functions, stack_frames, return_values, sp, execute_source)
    return sp, return_values

def evaluate_condition(condition_expr: str, memory, namespace, types, sp, user_functions, stack_frames) -> tuple[bool, int]:
    """Evaluate condition expression; return (bool_result, updated_sp)."""
    tokens = tokenizer.lexer(condition_expr)
    t.parser(tokens, namespace, helper, user_functions)
    noderizer.generate_trees(t, function_names, helper, tokens, namespace, memory, user_functions, types)
    sp, _ = evaluator.evaluate(tokens, memory, namespace, types, noderizer, t, helper, user_functions, stack_frames, [], sp, execute_source)

    if len(tokens) != 1:
        raise SyntaxError("condition must reduce to a single value")

    value = tokens[0]
    if isinstance(value, t.boolean):
        return value.val, sp
    if isinstance(value, t.i32):
        return value.val != 0, sp
    if isinstance(value, t.string):
        return len(value.val) > 0, sp
    raise TypeError(f"Unsupported condition type: {type(value)}")

def _parse_function_declaration(source_text: str, def_index: int) -> tuple[str, list[str], list[str], str, int]:
    """Parse `define name(type arg, ...) { ... }`.

    Returns: (function_name, arg_types, arg_names, function_body_source, next_cursor_after_block)
    """
    keyword = "define"
    name_start = helper.skip_whitespace(source_text, def_index + len(keyword))
    if name_start >= len(source_text):
        raise SyntaxError("Expected function name after define")

    name_end = name_start
    while name_end < len(source_text) and (source_text[name_end].isalnum() or source_text[name_end] == "_"):
        name_end += 1

    function_name = source_text[name_start:name_end].strip()
    if not function_name:
        raise SyntaxError("Expected function name after define")

    header_open_index = helper.skip_whitespace(source_text, name_end)
    if header_open_index >= len(source_text) or source_text[header_open_index] != "(":
        raise SyntaxError("Expected '(' after function name")

    header_close_index = helper.find_matching(source_text, header_open_index, "(", ")")
    header_text = source_text[header_open_index + 1:header_close_index].strip()

    arg_types: list[str] = []
    arg_names: list[str] = []
    if header_text:
        header_parts = helper._split_top_level_commas(header_text)
        for arg_decl in header_parts:
            arg_decl = arg_decl.strip()
            if not arg_decl:
                raise SyntaxError("Empty argument declaration in function header")
            pieces = arg_decl.split()
            if len(pieces) != 2:
                raise SyntaxError("Invalid argument declaration in function header")
            arg_types.append(pieces[0])
            arg_names.append(pieces[1])

    block_open_index = helper.skip_whitespace(source_text, header_close_index + 1)
    if block_open_index >= len(source_text) or source_text[block_open_index] != "{":
        raise SyntaxError("Expected '{' after function header")

    block_close_index = helper.find_matching(source_text, block_open_index, "{", "}")
    function_body = source_text[block_open_index + 1:block_close_index]

    return function_name, arg_types, arg_names, function_body, block_close_index + 1


def execute_source(source_text: str, memory, namespace, types, stack_frame: list[int], sp: int, functions: dict[str, list], return_values) -> (int | list):
    """Execute source recursively with runtime control-flow and stack-frame push/pop.
    \n Returns updated sp and optionally return value(s) if executing a function body."""
    source_text = helper.strip_comments(source_text)
    cursor = 0
    source_length = len(source_text)


    while cursor < source_length:
        cursor = helper.skip_whitespace(source_text, cursor)
        if cursor >= source_length:
            break

        if helper.is_controlflow_keyword_at(source_text, cursor, "def", get_paren=False):
            function_name, arg_types, arg_names, function_body, next_cursor = _parse_function_declaration(source_text, cursor)
            functions[function_name] = {
                "arg_types": arg_types,
                "arg_names": arg_names,
                "body": function_body,
            }
            cursor = next_cursor
            continue

        if helper.is_controlflow_keyword_at(source_text, cursor, "while"):
            condition_expression, block_source, next_cursor = helper.parse_while_block(source_text, cursor)

            condition_true, sp = evaluate_condition(condition_expression, memory, namespace, types, sp, functions, stack_frame)
            while condition_true:
                helper.create_frame(stack_frame, sp, namespace)
                sp, return_values = execute_source(block_source, memory, namespace, types, stack_frame, sp, functions, return_values)
                sp = helper.destroy_frame(stack_frame, namespace)
                condition_true, sp = evaluate_condition(condition_expression, memory, namespace, types, sp, functions, stack_frame)

            cursor = next_cursor
            continue

        if helper.is_controlflow_keyword_at(source_text, cursor, "iterate"):
            iterator_name, end_value, block_source, next_cursor = helper.parse_iterate_block(source_text, cursor)

            helper.create_frame(stack_frame, sp, namespace)
            sp, return_values = execute_statement(f"let i32 {iterator_name} = 0", memory, namespace, types, stack_frame, sp, functions, return_values)

            condition_true, sp = evaluate_condition(f"{iterator_name} < {end_value}", memory, namespace, types, sp, functions, stack_frame)
            while condition_true:
                helper.create_frame(stack_frame, sp, namespace)
                sp, return_values = execute_source(block_source, memory, namespace, types, stack_frame, sp, functions, return_values)
                sp, return_values = execute_statement(f"{iterator_name}++", memory, namespace, types, stack_frame, sp, functions, return_values)
                sp = helper.destroy_frame(stack_frame, namespace)
                condition_true, sp = evaluate_condition(f"{iterator_name} < {end_value}", memory, namespace, types, sp, functions, stack_frame)

            sp, return_values = execute_statement(f"{iterator_name}^", memory, namespace, types, stack_frame, sp, functions, return_values)
            sp = helper.destroy_frame(stack_frame, namespace)

            cursor = next_cursor
            continue

        if helper.is_controlflow_keyword_at(source_text, cursor, "for"):
            init_statement, condition_expression, step_statement, block_source, next_cursor = helper.parse_for_block(source_text, cursor)

            helper.create_frame(stack_frame, sp, namespace)
            sp, return_values = execute_statement(init_statement, memory, namespace, types, stack_frame, sp, functions, return_values)

            condition_true, sp = evaluate_condition(condition_expression, memory, namespace, types, sp, functions, stack_frame)
            while condition_true:
                helper.create_frame(stack_frame, sp, namespace)
                sp, return_values = execute_source(block_source, memory, namespace, types, stack_frame, sp, functions, return_values)
                sp, return_values = execute_statement(step_statement, memory, namespace, types, stack_frame, sp, functions, return_values)
                sp = helper.destroy_frame(stack_frame, namespace)
                condition_true, sp = evaluate_condition(condition_expression, memory, namespace, types, sp, functions, stack_frame)

            sp = helper.destroy_frame(stack_frame, namespace)
            cursor = next_cursor
            continue

        if helper.is_controlflow_keyword_at(source_text, cursor, "if"):
            condition_expression, if_block_source, next_cursor = helper.parse_if_block(source_text, cursor)
            condition_true, sp = evaluate_condition(condition_expression, memory, namespace, types, sp, functions, stack_frame)

            else_cursor = helper.skip_whitespace(source_text, next_cursor)
            has_else = helper.is_controlflow_keyword_at(source_text, else_cursor, "else")

            if has_else:
                else_block_source, after_else_cursor = helper.parse_else_block(source_text, else_cursor)
                if condition_true:
                    helper.create_frame(stack_frame, sp, namespace)
                    sp, return_values = execute_source(if_block_source, memory, namespace, types, stack_frame, sp, functions, return_values)
                    sp = helper.destroy_frame(stack_frame, namespace)
                else:
                    helper.create_frame(stack_frame, sp, namespace)
                    sp, return_values = execute_source(else_block_source, memory, namespace, types, stack_frame, sp, functions, return_values)
                    sp = helper.destroy_frame(stack_frame, namespace)
                cursor = after_else_cursor
            else:
                if condition_true:
                    helper.create_frame(stack_frame, sp, namespace)
                    sp, return_values = execute_source(if_block_source, memory, namespace, types, stack_frame, sp, functions, return_values)
                    sp = helper.destroy_frame(stack_frame, namespace)
                cursor = next_cursor
            continue

        statement_text, cursor = helper.read_statement(source_text, cursor)
        if statement_text:
            sp, return_values = execute_statement(statement_text, memory, namespace, types, stack_frame, sp, functions, return_values)

        if cursor < source_length and (source_text[cursor] == ";" or source_text[cursor] == "}"):
            cursor += 1

    return sp, return_values


function_names = [
    "printf",
    "let",
    "input",
    "typeof",
    "sizeof",
    "sConcat",
    "sLength",
    "aLength",
    "aConcat",
    "aSet",
    "return",
    "cast",
    "malloc",
    "coredump"
]


def main(raw_source: str, memory_size: int=1024) -> int:
    memory = bytearray(memory_size)
    namespace: list[dict[str, any]] = [{}] # global scope is the first dict in the list; new dicts are pushed for new scopes. Each dict maps variable names to {"type": type_name, "address": mem_address} entries.
    types = {
        "string": t.string,
        "i32": t.i32,
        "boolean": t.boolean,
        "array": t.array,
        "char": t.char,
        "i64": t.i64,
        "i8": t.i8,
        "i16": t.i16,
        "u32": t.u32,
        "u64": t.u64,
        "u8": t.u8,
        "u16": t.u16,
        "ptr": t.ptr,
    }

    sp = 0
    stack_frame: list[int] = []
    user_functions: dict[str, dict[str, object]] = {} # maps function names to {"arg_types": [...], "arg_names": [...], "body": "..."}
    sp, return_values = execute_source(raw_source + "\nmain();", memory, namespace, types, stack_frame, sp, user_functions, return_values=[])
    if return_values == None:
        raise RuntimeError("Program did not return a value")
    return return_values[0] if len(return_values) == 1 else return_values
    #print("---DEBUG---")
    #print("Memory contents:", memory[0:40])
    #print("Namespace:", namespace)
    #print("Functions:", user_functions)


import sys

if __name__ == "__main__":
    with open(sys.argv[1], "r") as f:
        raw_source = f.read()
    if len(sys.argv) == 3: # custom bytearray initalize size
        memory_size = int(sys.argv[2])
        if memory_size <= 0:
            print("Memory size must be a positive integer")
            sys.exit(1)
        print("===OUTPUT===")
        return_values = main(raw_source, memory_size)
    else:
        print("===OUTPUT===")
        return_values = main(raw_source)
    #print(return_values)

