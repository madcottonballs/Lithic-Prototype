import helper
import evalulation.evaluator as evaluator
import AST.noderizer as noderizer
import token_generation.typerizer as t
import token_generation.tokenizer as tokenizer
import preproccesor as preproccesor
import os
class State:
    def __init__(self):
        self.memory = {}
        self.namespace: list[dict[str, any]] = [{}]
        self.types = {}
        self.stack_frames = []
        self.traceback = []
        self.user_functions: dict[str, dict[str, object]] = {}
        self.t = t
        self.helper = helper
        self.n = noderizer
        self.noderizer = noderizer # alias
        self.tokenizer = tokenizer
        self.evaluator = evaluator
        self.os = os
        self.sp = 0
        self.hp = 0
        self.raw_source = ""
        self.line = 1
        self.current_source = ""
        self.LITHIC_ROOT = os.path.dirname(os.path.abspath(__file__))
        self.STDLIB_PATH = "stdlib" # os.path.join(self.LITHIC_ROOT, "stdlib")   #  os.path.join will be used in final version, but for now we can just use a relative path since the working directory is always the project root 
        self.aliases: list[str] = list()
        self.function_names = (
            "printf",
            "let",
            "input",
            "typeof",
            "sizeof",
            "aSet",
            "return",
            "cast",
            "malloc",
            "coredump",
            "exit",
            "@",
            "makeTuple",
            "tSet",
            "pass",
            "concat",
            "length",
            "tag",
            "untag",
            "getTypeTag",
            "mallocType",
            "cmd",
            "split",
            "print",
            
            "read",
            "readLines",
            "readLine",
            "readByte",
            "readBytes",
            "write",
            "writeLine",
            "writeByte",
            "advanceByte",
            "advanceLine",
            "rewindByte",
            "rewindLine",
            "setCursor",
            "getCursor",
            "atEOF",
            "open",
            "close",
            "flush",
        )
        self.types = {
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
            "tuple": t.ltctuple,
            "file": t.file,
        }
        self.control_flow = (
                "define",
                "if",
                "else",
                "while",
                "for",
                "iterate",
                "enumerate"
            )
        self.primitives = ( # all supported array element types
            "char",
            "i32",
            "boolean",
            "i64",
            "i8",
            "i16",
            "u32",
            "u64",
            "u8",
            "u16",
            "ptr",
        )

        self.reserved_keywords = set(
            [
                # literals
                "true",
                "false",
                # operators-as-keywords
                "not",
            ]
        )
        self.reserved_keywords.update(self.types.keys())
        self.reserved_keywords.update(self.control_flow)
        self.reserved_keywords.update(self.function_names)
    def error(self, message, print_tokens=False, tokens=[]):
        """Centralized error handling for the LTC interpreter. This module defines custom exception classes and error handling functions to provide consistent and informative error messages throughout the interpreter. Not done yet*"""
        print("Lithic Traceback (most recent call last):")
        for i, v in enumerate(self.traceback):
            print(f"In {v}( ... )")
        print(f"Line: '{self.current_stmt}'")
        #print(f"Lithic Error: {message}")
        if print_tokens:
            print("-----TOKENS:-------")
            for v in tokens:
                print(f"\t{type(v).__name__}:\t{v.val}")
        raise RuntimeError(message) # * temporary during development; will implement more sophisticated error handling later
        #exit(1)

def execute_statement(stmt: str, ltc, return_values) -> list:
    """Execute one non-control-flow statement and return return_values."""
    ltc.current_stmt = stmt
    stmt = stmt.strip()
    if not stmt:
        return return_values

    tokens = tokenizer.lexer(stmt) # fixed
    t.parser(tokens, ltc) # fixed
    noderizer.generate_trees(tokens, ltc, 0) # fixed
    return_values = evaluator.evaluate(tokens, ltc, return_values, execute_source)
    return return_values

def evaluate_condition(condition_expr: str, ltc: State) -> bool:
    """Evaluate condition expression; return bool_result."""
    tokens = tokenizer.lexer(condition_expr)
    t.parser(tokens, ltc)
    noderizer.generate_trees(tokens, ltc, 0)
    evaluator.evaluate(tokens, ltc, [], execute_source)

    if len(tokens) != 1:
        ltc.error("condition must reduce to a single value")

    value = tokens[0]
    if isinstance(value, t.boolean):
        return value.val
    if isinstance(value, t.i32):
        return value.val != 0
    if isinstance(value, t.string):
        return len(value.val) > 0
    ltc.error(f"Unsupported condition type: {type(value)}")

def _parse_function_declaration(source_text: str, def_index: int, ltc: State) -> tuple[str, list[str], list[str], str, int]:
    """Parse `define name(type arg, ...) { ... }`.

    Returns: (function_name, arg_types, arg_names, function_body_source, next_cursor_after_block)
    """
    keyword = "define"
    name_start = helper.skip_whitespace(source_text, def_index + len(keyword))
    if name_start >= len(source_text):
        ltc.error("Expected function name after define")

    name_end = name_start
    while name_end < len(source_text) and (
        source_text[name_end].isalnum() or source_text[name_end] in {"_", "."}
    ):
        name_end += 1

    function_name = source_text[name_start:name_end].strip()
    if not function_name:
        ltc.error("Expected function name after define")
    if function_name in ltc.reserved_keywords:
        ltc.error(f"Function name '{function_name}' is a reserved keyword")

    header_open_index = helper.skip_whitespace(source_text, name_end)
    if header_open_index >= len(source_text) or source_text[header_open_index] != "(":
        ltc.error(f"Expected '(' after function name, instead got '{source_text[header_open_index]}'")

    header_close_index = helper.find_matching(source_text, header_open_index, "(", ")", ltc)
    header_text = source_text[header_open_index + 1:header_close_index].strip()

    arg_types: list[str] = []
    arg_names: list[str] = []
    if header_text:
        header_parts = helper._split_top_level_commas(header_text)
        for arg_decl in header_parts:
            arg_decl = arg_decl.strip()
            if not arg_decl:
                ltc.error("Empty argument declaration in function header")
            pieces = arg_decl.split()
            if len(pieces) != 2:
                ltc.error("Invalid argument declaration in function header")
            arg_types.append(pieces[0])
            arg_names.append(pieces[1])
            if arg_names[-1] in ltc.reserved_keywords:
                ltc.error(f"Argument name '{arg_names[-1]}' is a reserved keyword")

    block_open_index = helper.skip_whitespace(source_text, header_close_index + 1)
    if block_open_index >= len(source_text) or source_text[block_open_index] != "{":
        ltc.error("Expected '{' after function header")

    block_close_index = helper.find_matching(source_text, block_open_index, "{", "}", ltc)
    function_body = source_text[block_open_index + 1:block_close_index]

    return function_name, arg_types, arg_names, function_body, block_close_index + 1

def execute_source(source, ltc: State, return_values) -> list:
    """Execute source recursively with runtime control-flow and stack-frame push/pop.
    \n Returns return value(s) if executing a function body"""
    
    source_text = helper.strip_comments(source, ltc)
    source_text = preproccesor.process_imports(source_text, ltc)
    ltc.current_source = source_text
    cursor = 0
    source_length = len(source_text)


    while cursor < source_length:
        cursor = helper.skip_whitespace(source_text, cursor)
        if cursor >= source_length:
            break

        if helper.is_controlflow_keyword_at(source_text, cursor, "define", get_paren=False):
            function_name, arg_types, arg_names, function_body, next_cursor = _parse_function_declaration(source_text, cursor, ltc)
            ltc.user_functions[function_name] = {
                "arg_types": arg_types,
                "arg_names": arg_names,
                "body": function_body,
            }
            cursor = next_cursor
            continue

        if helper.is_controlflow_keyword_at(source_text, cursor, "while"):
            condition_expression, block_source, next_cursor = helper.parse_while_block(source_text, cursor, ltc)

            condition_true = evaluate_condition(condition_expression, ltc)
            while condition_true:
                helper.create_frame(ltc)
                return_values = execute_source(block_source, ltc, return_values)
                helper.destroy_frame(ltc)
                condition_true = evaluate_condition(condition_expression, ltc)

            cursor = next_cursor
            continue

        if helper.is_controlflow_keyword_at(source_text, cursor, "iterate"):
            iterator_name, end_value, block_source, next_cursor = helper.parse_iterate_block(source_text, cursor, ltc)

            helper.create_frame(ltc)
            return_values = execute_statement(f"let i32 {iterator_name} = 0", ltc, return_values)

            condition_true = evaluate_condition(f"{iterator_name} < {end_value}", ltc)
            while condition_true:
                helper.create_frame(ltc)
                return_values = execute_source(block_source, ltc, return_values)
                return_values = execute_statement(f"{iterator_name}++", ltc, return_values)
                helper.destroy_frame(ltc)
                condition_true = evaluate_condition(f"{iterator_name} < {end_value}", ltc)

            return_values = execute_statement(f"{iterator_name}^", ltc, return_values) # destroy iterator variable
            helper.destroy_frame(ltc)

            cursor = next_cursor
            continue

        if helper.is_controlflow_keyword_at(source_text, cursor, "for"):
            init_statement, condition_expression, step_statement, block_source, next_cursor = helper.parse_for_block(source_text, cursor, ltc)

            helper.create_frame(ltc)
            return_values = execute_statement(init_statement, ltc, return_values)

            condition_true = evaluate_condition(condition_expression, ltc)
            while condition_true:
                helper.create_frame(ltc)
                return_values = execute_source(block_source, ltc, return_values)
                return_values = execute_statement(step_statement, ltc, return_values)
                helper.destroy_frame(ltc)
                condition_true  = evaluate_condition(condition_expression, ltc)

            helper.destroy_frame(ltc)
            cursor = next_cursor
            continue

        if helper.is_controlflow_keyword_at(source_text, cursor, "if"):
            condition_expression, if_block_source, next_cursor = helper.parse_if_block(source_text, cursor, ltc)
            condition_true = evaluate_condition(condition_expression, ltc)

            else_cursor = helper.skip_whitespace(source_text, next_cursor)
            has_else = helper.is_controlflow_keyword_at(source_text, else_cursor, "else")

            if has_else:
                else_block_source, after_else_cursor = helper.parse_else_block(source_text, else_cursor, ltc)
                if condition_true:
                    helper.create_frame(ltc)
                    return_values = execute_source(if_block_source, ltc, return_values)
                    helper.destroy_frame(ltc)
                else:
                    helper.create_frame(ltc)
                    return_values = execute_source(else_block_source, ltc, return_values)
                    helper.destroy_frame(ltc)
                cursor = after_else_cursor
            else:
                if condition_true:
                    helper.create_frame(ltc)
                    return_values = execute_source(if_block_source, ltc, return_values)
                    helper.destroy_frame(ltc)
                cursor = next_cursor
            continue

        statement_text, cursor = helper.read_statement(source_text, cursor)
        if statement_text:
            return_values = execute_statement(statement_text, ltc, return_values)

        if cursor < source_length and (source_text[cursor] == ";" or source_text[cursor] == "}"):
            cursor += 1

    helper.memory_bounds_check(ltc)

    return return_values

def main(raw_source: str, memory_size: int=1024) -> int:
    ltc = State()
    ltc.raw_source = raw_source + "\nmain();"
    ltc.memory = bytearray(memory_size)
    ltc.namespace = [{}] # global scope is the first dict in the list; new dicts are pushed for new scopes. Each dict maps variable names to {"type": type_name, "addr": mem_address} entries.
    ltc.sp = 0
    ltc.hp = memory_size - 1
    ltc.user_functions = {} # maps function names to {"arg_types": [...], "arg_names": [...], "body": "..."}
    return_values = []
    return_values= execute_source(ltc.raw_source, ltc, return_values)
    if return_values == None:
        ltc.error("Program did not return a value")
    return return_values[0] if len(return_values) == 1 else return_values


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
