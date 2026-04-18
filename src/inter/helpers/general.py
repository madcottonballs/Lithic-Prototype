"""Helper functions for the interpreter, used across multiple modules. Source import is in main.py."""

def create_frame(ltc) -> None:
    ltc.stack_frames.append(ltc.sp)
    ltc.namespace.append({})
def destroy_frame(ltc) -> None:
    ltc.sp = ltc.stack_frames.pop()
    ltc.namespace.pop()

def resolve_node(node, ltc, return_values, evaluate, execute_source_fn):
    """Resolve a node to its runtime value.

    This is used to evaluate operands before performing operations or calling built-ins.
    """
    t = ltc.t
    # Always dereference var refs directly so we preserve var_name on ptrs.
    if isinstance(node, t.var_ref):
        return dereference_var(ltc, node)

    if evaluate is None:
        raise Exception("evaluate function is required to resolve non-var_ref nodes, check caller of resolve_node")

    # Evaluate any node type by running it through the evaluator.
    temp = [node]
    evaluate(temp, ltc, return_values, execute_source_fn)
    resolved = temp[0]
    if isinstance(resolved, t.var_ref):
        return dereference_var(ltc, resolved)
    return resolved


# helper function for parser: finds the closing parenthesis for a given opening parenthesis index, and replaces the full "(...)" slice with one `subexp` node containing the inner tokens.
def find_closing_parenthesis(IdxOfOpening, tokens, subexp_cls, ltc):
    # Start scanning just after the opening parenthesis.
    i = IdxOfOpening + 1
    # Tracks nested parentheses depth inside this sub-expression.
    extra_layers_deep = 0

    while i < len(tokens):
        match tokens[i].val:
            case ")":
                # If we are inside nested parentheses, this closes one nested layer.
                if extra_layers_deep != 0:
                    extra_layers_deep -= 1
                    i += 1
                    continue

                # Found the matching close for the original opening bracket.
                # Replace the full "(...)" slice with one `subexp` node.
                # i + 1 is required because Python slice end index is exclusive.
                tokens[IdxOfOpening:i + 1] = [subexp_cls(tokens[IdxOfOpening + 1:i])]
                return

            case "(":
                # New nested sub-expression starts.
                extra_layers_deep += 1
                i += 1

            case _:
                # Any other token: just continue scanning.
                i += 1
    else:
        # We exhausted tokens without finding a matching ")".
        ltc.error("No closing bracket found for opening bracket")

# helper function for generate_tree: checks that a binary operator at index `i` has both left and right operands, otherwise raises an error.
def validate_operator(tokens, i, char, ltc):
    # Every binary operator must have both left and right operands.
    if i + 1 >= len(tokens) or i - 1 < 0:
        ltc.error(f"'{char}' is at the start or end of the expression")

def add_string_to_memory(string, memory, ltc) -> None:
    """Returns the new stack pointer after writing the string to memory.
    \n sp updates handled directly on ltc object to ensure consistency across calls and avoid bugs where caller forgets to update sp after calling this helper."""
    byte_rep_of_str = string.val.encode('utf-8') + b'\x00' # null-terminated string
    string.inmemory = True
    string.memloc = ltc.sp
    memory[ltc.sp:ltc.sp + len(byte_rep_of_str)] = byte_rep_of_str
    ltc.sp += len(byte_rep_of_str)

def add_string_to_heap(string, memory, ltc, capacity: int | None = None) -> tuple[int, int]:
    """Write a string to the heap and return (start_addr, capacity)."""
    
    byte_rep_of_str = string.val.encode('utf-8') + b'\x00'
    needed = len(byte_rep_of_str)
    alloc = max(needed, capacity or needed) # if capacity is provided, allocate that much space (or more if needed), otherwise allocate just enough for the string
    start = ltc.hp - alloc
    if start <= ltc.sp:
        ltc.error("Stack and Heap intersect. Out of memory.")
    string.inmemory = True
    string.memloc = start
    # Zero-fill the allocation, then write the string bytes.
    memory[start:start + alloc] = b'\x00' * alloc
    memory[start:start + needed] = byte_rep_of_str
    ltc.hp = start
    return start, alloc

def find_matching(source_text: str, opening_index: int, opening_char: str, closing_char: str, ltc) -> int:
    """Return index of the closing delimiter matching opening_index.

    This matcher is nesting-aware and ignores delimiters inside quoted strings.
    """
    # Start one character after the known opening delimiter.
    nesting_depth = 1
    cursor = opening_index + 1
    in_string = False
    active_quote = ""

    while cursor < len(source_text):
        current_char = source_text[cursor]
        if in_string:
            # Ignore delimiters while inside a quoted string.
            if current_char == active_quote:
                in_string = False
        else:
            if current_char == '"' or current_char == "'":
                in_string = True
                active_quote = current_char
            elif current_char == opening_char:
                # Found a nested opener, so one extra close is now required.
                nesting_depth += 1
            elif current_char == closing_char:
                nesting_depth -= 1
                if nesting_depth == 0:
                    # This close matches the original opening delimiter.
                    return cursor
        cursor += 1

    ltc.error(f"Unmatched '{opening_char}'")

def skip_whitespace(source_text: str, start_index: int) -> int:
    """Advance cursor over whitespace and return the first non-whitespace index."""
    cursor = start_index
    while cursor < len(source_text) and source_text[cursor].isspace():
        cursor += 1
    return cursor

def is_controlflow_keyword_at(source_text: str, cursor: int, keyword: str, get_paren=True) -> bool:
    """Check whether keyword starts at cursor as a standalone token."""
    if not source_text.startswith(keyword, cursor):
        return False

    left_ok = cursor == 0 or not (source_text[cursor - 1].isalnum() or source_text[cursor - 1] == "_")
    right_index = cursor + len(keyword)

    if get_paren:
        right_ok = (
            right_index >= len(source_text)
            or source_text[right_index].isspace()
            or source_text[right_index] == "("
        )
    else:
        right_ok = (
            right_index >= len(source_text)
            or source_text[right_index].isspace()
            or source_text[right_index].isalnum()
            or source_text[right_index] == "_"
        )

    return left_ok and right_ok

def _parse_struct_declaration(source_text: str, struct_index: int, ltc):
    """Parse `struct Name { ... }` and return (name, block_source, next_cursor)."""
    keyword = "struct"
    name_start = skip_whitespace(source_text, struct_index + len(keyword))
    if name_start >= len(source_text):
        ltc.error("Expected struct name after struct")

    name_end = name_start
    while name_end < len(source_text) and (
        source_text[name_end].isalnum() or source_text[name_end] == "_"
    ):
        name_end += 1

    struct_name = source_text[name_start:name_end].strip()
    if not struct_name:
        ltc.error("Expected struct name after struct")
    if struct_name in ltc.reserved_keywords:
        ltc.error(f"Struct name '{struct_name}' is a reserved keyword")
    if not (struct_name[0].isalpha() or struct_name[0] == "_"):
        ltc.error("Struct name must start with a letter or underscore")

    block_open_index = skip_whitespace(source_text, name_end)
    if block_open_index >= len(source_text) or source_text[block_open_index] != "{":
        ltc.error("Expected '{' after struct name")

    block_close_index = find_matching(source_text, block_open_index, "{", "}", ltc)
    block_source = source_text[block_open_index + 1:block_close_index]

    return struct_name, block_source, block_close_index + 1
def parse_control_block(source_text: str, keyword_index: int, keyword: str, ltc) -> tuple[str, str, int]:
    """Parse `<keyword> (<condition>) { <block> }` and return condition/body/next index.

    Returns: (condition_expression, block_source, next_cursor_after_block)
    """
    keyword_len = len(keyword)
    # 1) Find the start of the condition: if ( ... )
    condition_open_index = skip_whitespace(source_text, keyword_index + keyword_len)
    if condition_open_index >= len(source_text) or source_text[condition_open_index] != "(":
        ltc.error(f"Expected '(' after {keyword}")

    # 2) Extract raw condition text between matching parentheses.
    condition_close_index = find_matching(source_text, condition_open_index, "(", ")", ltc)
    condition_expression = source_text[condition_open_index + 1:condition_close_index]

    # 3) Find the start of the block body: { ... }
    block_open_index = skip_whitespace(source_text, condition_close_index + 1)
    if block_open_index >= len(source_text) or source_text[block_open_index] != "{":
        ltc.error(f"Expected '{{' after {keyword} condition")

    # 4) Extract block source between matching curly braces.
    block_close_index = find_matching(source_text, block_open_index, "{", "}", ltc)
    block_source = source_text[block_open_index + 1:block_close_index]

    # Return parsed parts plus the next cursor position after the block.
    return condition_expression, block_source, block_close_index + 1

def parse_else_block(source_text: str, else_index: int, ltc) -> tuple[str, int]:
    """Parse `else { <block> }` and return block source plus next cursor index."""
    keyword = "else"
    block_open_index = skip_whitespace(source_text, else_index + len(keyword))
    if block_open_index >= len(source_text) or source_text[block_open_index] != "{":
        ltc.error("Expected '{' after else")

    block_close_index = find_matching(source_text, block_open_index, "{", "}", ltc)
    block_source = source_text[block_open_index + 1:block_close_index]
    return block_source, block_close_index + 1

def parse_if_block(source_text: str, if_index: int, ltc) -> tuple[str, str, int]:
    """Parse `if (<condition>) { <block> }` starting at if_index."""
    return parse_control_block(source_text, if_index, "if", ltc)

def parse_while_block(source_text: str, while_index: int, ltc) -> tuple[str, str, int]:
    """Parse `while (<condition>) { <block> }` starting at while_index."""
    return parse_control_block(source_text, while_index, "while", ltc)

def _split_top_level_commas(text: str) -> list[str]:
    """Split by commas that are not nested in parentheses/braces/brackets or strings."""
    parts: list[str] = []
    start = 0
    paren_depth = 0
    brace_depth = 0
    bracket_depth = 0
    in_string = False
    active_quote = ""
    index = 0

    while index < len(text):
        current_char = text[index]
        if in_string:
            if current_char == active_quote:
                in_string = False
        else:
            if current_char == '"' or current_char == "'":
                in_string = True
                active_quote = current_char
            elif current_char == "(":
                paren_depth += 1
            elif current_char == ")":
                paren_depth -= 1
            elif current_char == "{":
                brace_depth += 1
            elif current_char == "}":
                brace_depth -= 1
            elif current_char == "[":
                bracket_depth += 1
            elif current_char == "]":
                bracket_depth -= 1
            elif (
                current_char == ","
                and paren_depth == 0
                and brace_depth == 0
                and bracket_depth == 0
            ):
                parts.append(text[start:index].strip())
                start = index + 1
        index += 1

    parts.append(text[start:].strip())
    return parts

def parse_for_block(source_text: str, for_index: int, ltc) -> tuple[str, str, str, str, int]:
    """Parse `for (init, condition, step) { block }`.

    Returns: (init_statement, condition_expression, step_statement, block_source, next_cursor_after_block)
    """
    keyword = "for"
    header_open_index = skip_whitespace(source_text, for_index + len(keyword))
    if header_open_index >= len(source_text) or source_text[header_open_index] != "(":
        ltc.error("Expected '(' after for")

    header_close_index = find_matching(source_text, header_open_index, "(", ")", ltc)
    header_text = source_text[header_open_index + 1:header_close_index]
    header_parts = _split_top_level_commas(header_text)
    if len(header_parts) != 3:
        ltc.error("for expects exactly 3 header expressions: init, condition, step")

    init_statement = header_parts[0]
    condition_expression = header_parts[1]
    step_statement = header_parts[2]

    block_open_index = skip_whitespace(source_text, header_close_index + 1)
    if block_open_index >= len(source_text) or source_text[block_open_index] != "{":
        ltc.error("Expected '{' after for header")

    block_close_index = find_matching(source_text, block_open_index, "{", "}", ltc)
    block_source = source_text[block_open_index + 1:block_close_index]

    return init_statement, condition_expression, step_statement, block_source, block_close_index + 1

def parse_iterate_block(source_text: str, iterate_index: int, ltc) -> tuple[str, int, str, int]:
    """Parse `iterate (<var_name>, <end_dword>) { block }`.

    Returns: (iterator_name, end_value, block_source, next_cursor_after_block)
    """
    keyword = "iterate"
    header_open_index = skip_whitespace(source_text, iterate_index + len(keyword))
    if header_open_index >= len(source_text) or source_text[header_open_index] != "(":
        ltc.error("Expected '(' after iterate")

    header_close_index = find_matching(source_text, header_open_index, "(", ")", ltc)
    header_text = source_text[header_open_index + 1:header_close_index]
    header_parts = _split_top_level_commas(header_text)
    if len(header_parts) != 2:
        ltc.error("iterate expects exactly 2 values: iterate(<var_name>, <end_dword>)")

    iterator_name = header_parts[0].strip()
    if not iterator_name or not (iterator_name[0].isalpha() or iterator_name[0] == "_"):
        ltc.error("iterate first value must be a valid variable name")
    if not all(ch.isalnum() or ch == "_" for ch in iterator_name):
        ltc.error("iterate variable name contains invalid characters")
    if iterator_name in ltc.reserved_keywords:
        ltc.error(f"iterate variable name '{iterator_name}' is a reserved keyword")

    end_text = header_parts[1].strip()
    #if not end_text.isdigit():
    #    ltc.error("iterate second value must be a i32 literal")
    #end_value = int(end_text)
    end_value = end_text

    block_open_index = skip_whitespace(source_text, header_close_index + 1)
    if block_open_index >= len(source_text) or source_text[block_open_index] != "{":
        ltc.error("Expected '{' after iterate header")

    block_close_index = find_matching(source_text, block_open_index, "{", "}", ltc)
    block_source = source_text[block_open_index + 1:block_close_index]

    return iterator_name, end_value, block_source, block_close_index + 1

def read_statement(source_text: str, start_index: int) -> tuple[str, int]:
    """Read a statement until `;` or `}` (ignoring delimiters inside strings)."""
    cursor = start_index
    in_string = False
    active_quote = ""

    while cursor < len(source_text):
        current_char = source_text[cursor]
        if in_string:
            if current_char == active_quote:
                in_string = False
        else:
            if current_char == '"' or current_char == "'":
                # Enter quoted mode so separators inside strings are ignored.
                in_string = True
                active_quote = current_char
            elif current_char == ";" or current_char == "}" or current_char == "\n":
                # End of this statement at top-level source scanning.
                break
        cursor += 1

    statement_text = source_text[start_index:cursor].strip()
    return statement_text, cursor

def dereference_var(ltc, var_ref_token) -> object:
    """Enter a var_ref token, recieve its obj from memory"""
    var_meta = locate_var_in_namespace(ltc.namespace, var_ref_token.val, return_just_the_check=False)[0]
    var_type: str = var_meta["type"]
    addr: int = var_meta["addr"]
    t = ltc.t
    match var_type:
        case "i32"|"i64"|"i8"|"i16"|"u32"|"u64"|"u8"|"u16":
            class_ref = ltc.types[var_type]                        # gathers the class reference for the variable type (e.g. t.i32)
            temp_instance = class_ref(0, ltc)                        # create a temporary instance to call read_from_memory
            temp_instance = temp_instance.read_from_memory(ltc.memory, addr, ltc)  # read_from_memory returns a typed value
            temp_instance.inmemory = True                     # mark as inmemory (used for memloc oper)
            temp_instance.memloc = addr                       # store the memory address (used for memloc oper)
            return temp_instance
        case "string":
            end = addr
            while end < len(ltc.memory) and ltc.memory[end] != 0:
                end += 1
            temp_instance = t.string(ltc.memory[addr:end].decode("utf-8"))
            temp_instance.inmemory = True                     # mark the temp instance as inmemory (used for memloc oper)
            temp_instance.memloc = addr                       # store the memory address in the temp instance (used for memloc oper)
            return temp_instance
        case "char":
            temp_instance = t.char(chr(ltc.memory[addr]))
            temp_instance.inmemory = True                     # mark the temp instance as inmemory (used for memloc oper)
            temp_instance.memloc = addr                       # store the memory address in the temp instance (used for memloc oper)
            return temp_instance
        case "boolean":
            temp_instance = t.boolean(ltc.memory[addr] != 0)
            temp_instance.inmemory = True                     # mark the temp instance as inmemory (used for memloc oper)
            temp_instance.memloc = addr                       # store the memory address in the temp instance (used for memloc oper)
            return temp_instance
        case "ptr":
            temp_instance = t.ptr(0, ltc, var_name=var_ref_token.val)                          # create a temporary instance to call read_from_memory
            temp_instance = temp_instance.read_from_memory(ltc.memory, addr, ltc)
            temp_instance.inmemory = True                     # mark as inmemory (used for memloc oper)
            temp_instance.memloc = addr                       # store the memory address (used for memloc oper)
            return temp_instance
        case "array":
            elem_type = var_meta["elem_type"]
            length = var_meta["length"]
            values = []
            match elem_type:
                case "i32"|"i64"|"i8"|"i16"|"u32"|"u64"|"u8"|"u16"|"ptr":
                    integer_type = ltc.types[elem_type]
                    for index in range(length):
                        element_addr = addr + (index * get_ltc_type_size(elem_type, ltc))
                        element_value = int.from_bytes(ltc.memory[element_addr:element_addr + get_ltc_type_size(elem_type, ltc)], byteorder='little', signed=integer_type_to_signedness(elem_type, ltc))
                        element = integer_type(element_value, ltc)
                        values.append(element)
                case "boolean":
                    for index in range(length):
                        element_addr = addr + index
                        values.append(t.boolean(ltc.memory[element_addr] != 0))
                case "char":
                    for index in range(length):
                        element_addr = addr + index
                        values.append(t.char(chr(ltc.memory[element_addr])))
                case _:
                    ltc.error(f"Unsupported array element type: {elem_type}")

            array_obj = t.array(values, ltc, arrayType=elem_type, parse=False)
            array_obj.size = length
            array_obj.inmemory = True                     # mark the array object as inmemory (used for memloc oper)
            array_obj.memloc = addr                       # store the memory address in the array object (used for memloc oper)
            return array_obj
        case "tuple":
            element_types = var_meta["element_types"]
            return t.ltctuple.read_from_memory(addr, element_types, ltc) # returns the ltctuple obj
        case "file":
            contents = var_meta["contents"]
            mode = var_meta["mode"]
            file_obj = t.file(var_ref_token.val)
            file_obj.contents = contents
            file_obj.mode = mode
            file_obj.cursor = var_meta.get("cursor", 0)
            file_obj.var_name = var_ref_token.val
            return file_obj
        case _:
            if var_type in ltc.structs:
                struct_obj = ltc.structshelper.read_struct_from_memory(ltc, var_type, addr)
                struct_obj.inmemory = True
                struct_obj.memloc = addr
                return struct_obj
            ltc.error(f"Unsupported variable type: {var_type}")

def get_ltc_type_size(type_name: str, ltc, array_obj=None) -> int:
    """Helper function to get the byte size of any LTC type."""
    if type_name in ltc.structs:
        return ltc.structshelper.get_struct_size(ltc, type_name)
    match type_name:
        case "i8"|"u8"|"char"|"boolean":
            return 1
        case "i16"|"u16":
            return 2
        case "i32"|"u32":
            return 4
        case "i64"|"u64"|"ptr":
            return 8
        case "array": # if youre looking for the size of an array, you must pass in the array obj so size and arrayType can be known
            return array_obj.get_size()
        case "string" | "tuple" | "ltctuple":
            ltc.error(f"Dynamically sized types like '{type_name}' do not have a fixed byte size")
        case _:
            ltc.error(f"Unknown LTC type: {type_name}")

def integer_type_to_signedness(type_name: str, ltc) -> bool:
    """Helper function to determine if an integer type is signed."""
    match type_name:
        case "i8"|"i16"|"i32"|"i64":
            return True
        case "u8"|"u16"|"u32"|"u64"|"ptr":
            return False
        case _:
            ltc.error(f"Unknown integer type: {type_name}")

def load_to_mem(ltc, object, input_type="no type entered", memidx: int | None = None) -> None:
    """Load an ltc_type into memory.

    - Allocation mode (memidx is None): write at stack_ptr and advance sp.
    - Overwrite mode (memidx is set): write at memidx and keep sp unchanged.
    """
    write_ptr = ltc.sp if memidx is None else memidx

    if input_type == "no type entered":
        resolved_type = type(object).__name__
    else:
        resolved_type = input_type

    if resolved_type in ltc.structs:
        if not isinstance(object, ltc.t.struct_instance):
            ltc.error("Struct memory write requires a struct instance")
        ltc.structshelper.write_struct_to_memory(
            ltc,
            object.struct_name,
            object,
            memidx=None if memidx is None else write_ptr,
        )
        ltc.helper.memory_bounds_check(ltc)
        return

    match resolved_type:
        case "i32" | "i64" | "i8" | "i16" | "u32" | "u64" | "u8" | "u16":
            byte_rep_of_val = object.val.to_bytes(get_ltc_type_size(resolved_type, ltc), byteorder='little', signed=integer_type_to_signedness(resolved_type, ltc))
            ltc.memory[write_ptr:write_ptr + get_ltc_type_size(resolved_type, ltc)] = byte_rep_of_val
            if memidx is None:
                ltc.sp += get_ltc_type_size(resolved_type, ltc)
        case "string":
            if memidx is None:
                add_string_to_memory(object, ltc.memory, ltc)
            else:
                byte_rep_of_str = object.val.encode('utf-8') + b'\x00'
                ltc.memory[write_ptr:write_ptr + len(byte_rep_of_str)] = byte_rep_of_str
        case "boolean":
            byte_rep_of_val = 1 if object.val else 0
            ltc.memory[write_ptr] = byte_rep_of_val
            if memidx is None:
                ltc.sp += 1
        case "array":
            array_ptr = write_ptr
            match object.arrayType:
                case "i32" | "i64" | "i8" | "i16" | "u32" | "u64" | "u8" | "u16" | "ptr":
                    element_width = get_ltc_type_size(object.arrayType, ltc)
                    for i, element in enumerate(object.val):
                        element_ptr = array_ptr + (i * element_width)
                        load_to_mem(ltc, element, input_type=object.arrayType, memidx=element_ptr)
                    if memidx is None:
                        ltc.sp += element_width * object.get_size()
                case "string":
                    ltc.error("strings are not currently supported for arrays")
                case "boolean":
                    element_width = 1
                    for i, element in enumerate(object.val):
                        element_ptr = array_ptr + i
                        load_to_mem(ltc, element, input_type=object.arrayType, memidx=element_ptr)
                    if memidx is None:
                        ltc.sp += element_width * object.get_size()
        case "char":
            byte_rep_of_char = object.val.encode('utf-8')
            ltc.memory[write_ptr] = byte_rep_of_char[0]
            if memidx is None:
                ltc.sp += 1
        case "ptr":
            # Handle pointer type loading
            ptr_size = get_ltc_type_size("ptr", ltc)
            byte_rep_of_val = object.val.to_bytes(ptr_size, byteorder='little', signed=False)
            ltc.memory[write_ptr:write_ptr + ptr_size] = byte_rep_of_val
            if memidx is None:
                ltc.sp += ptr_size
        case "tuple":
                object.load_to_memory(ltc.memory, write_ptr, ltc)
                if memidx is None:
                    ltc.sp += object.get_byte_size(ltc) 
        case _:
            ltc.error(f"Tried to load an unrecognized type '{resolved_type}' into memory")
            
    memory_bounds_check(ltc)
    return


def memory_bounds_check(ltc) -> None:
    if ltc.hp <= ltc.sp:
        ltc.error("Stack and Heap intersect. Out of memory.")

def recieve_empty_form(ltc, type):
    """give the name of the type you want, this function returns an empty instance of that type"""
    if type in ltc.structs:
        return ltc.structshelper.create_struct_instance(ltc, type)
    match type:
        case "i32" | "i64" | "i8" | "i16" | "u32" | "u64" | "u8" | "u16":
            return ltc.types[type](0, ltc)
        case "string":
            return ltc.t.string("")
        case "boolean":
            return ltc.t.boolean(False)
        case "array":
            return ltc.t.array([], ltc, None, False)
        case "ptr":
            return ltc.t.ptr(0, ltc)
        case "char":
            return ltc.t.char('')
        case "tuple":
            return ltc.t.ltctuple(ltc, ())


def locate_var_in_namespace(namespace, var_name, return_just_the_check=True):
    """Search for a variable in the namespace stack and return its metadata and scope level.
    \n The namespace is a list of dicts, where each dict represents a scope level and maps variable names to their metadata (type and memory address). The search starts from the innermost scope and moves outward.
    \n return_just_the_check parameter controls whether to return just a boolean indicating presence (True/False) or the full metadata and scope level. If True, returns True if variable is found, otherwise False. If False, returns (var_metadata, scope_level) if found, otherwise (None, None).
    \nReturns: (var_metadata, scope_level) where var_metadata is a dict with 'type' and 'addr' keys, and scope_level is the index in the namespace list where the variable was found."""
    for scope_level in range(len(namespace) - 1, -1, -1):
        scope = namespace[scope_level]
        if var_name in scope:
            if return_just_the_check:
                return True
            else:
                return scope[var_name], scope_level
    if return_just_the_check:
        return False
    else:
        return None, None

def strip_comments(source_text: str, ltc) -> str:
    """Remove /* */ comments while preserving quoted strings."""
    output_chars: list[str] = []
    cursor = 0
    in_string = False
    active_quote = ""

    while cursor < len(source_text):
        current_char = source_text[cursor]
        next_char = source_text[cursor + 1] if cursor + 1 < len(source_text) else ""

        if in_string:
            output_chars.append(current_char)
            if current_char == active_quote:
                in_string = False
                active_quote = ""
            cursor += 1
            continue

        if current_char == '"' or current_char == "'":
            in_string = True
            active_quote = current_char
            output_chars.append(current_char)
            cursor += 1
            continue

        if current_char == "/" and next_char == "*":
            cursor += 2
            while cursor + 1 < len(source_text):
                if source_text[cursor] == "*" and source_text[cursor + 1] == "/":
                    cursor += 2
                    break
                cursor += 1
            else:
                ltc.error("Unterminated block comment '/* ... */'")
            continue

        output_chars.append(current_char)
        cursor += 1

    return "".join(output_chars)

def _get_user_function_meta(user_functions, function_name: str, ltc) -> tuple[list[str], list[str], str]:
    """Return (arg_types, arg_names, body) for a user function."""
    if function_name not in user_functions:
        ltc.error(f"Function '{function_name}' is not declared")

    entry = user_functions[function_name]
    if isinstance(entry, dict):
        arg_types = entry.get("arg_types", [])
        arg_names = entry.get("arg_names", [])
        body = entry.get("body", "")
    elif isinstance(entry, list):
        # Backward compatibility with old shape: [arg_types, body]
        arg_types = entry[0] if len(entry) > 0 else []
        arg_names = [f"arg{i}" for i in range(len(arg_types))]
        body = entry[1] if len(entry) > 1 else ""
    else:
        ltc.error(f"Invalid function metadata for '{function_name}'")

    if len(arg_types) != len(arg_names):
        ltc.error(f"Function '{function_name}' has mismatched arg type/name metadata")
    return arg_types, arg_names, body

def malloc(size: int, ltc) -> None:
    """Reserves memory. Returns starting address of the allocated block."""

    if ltc.hp - size <= ltc.sp:
        ltc.error("Heap grew into stack. Out of memory.")
    
    ltc.hp -= size

def read_ltc_type_from_mem(memory, addr, type_str, ltc):
    ltc_type = ltc.types[type_str]
    match type_str:
        case "i32" | "i64" | "i8" | "i16" | "u32" | "u64" | "u8" | "u16":
            return ltc_type(int.from_bytes(memory[addr:addr + get_ltc_type_size(type_str, ltc)], byteorder='little', signed=integer_type_to_signedness(type_str, ltc)), ltc)
        case "string":
            end = addr
            while end < len(memory) and memory[end] != 0:
                end += 1
            return ltc_type(memory[addr:end].decode("utf-8"))
        case "boolean":
            return ltc_type(memory[addr] != 0)
        case "char":
            return ltc_type(chr(memory[addr]))
        case "ptr":
            return ltc_type(int.from_bytes(memory[addr:addr + 8], byteorder='little', signed=False), ltc)
        case _:
            if type_str in ltc.types: # if we want to add support in the future for more types
                ltc.error(f"Type '{type_str}' is supposed to be supported but has no defined behavior for reading from memory. Please implement read behavior for this type in read_ltc_type_from_mem helper function.")
            else:
                ltc.error(f"Unsupported type for reading from mem: {type_str}")

def create_string_array(ltc, strings):
    """Takes in a list of str and returns a ltc.array of ptr to the ltc.Strings loaded"""
    t = ltc.t
    # arrays cannot hold strings directly, so we store the split strings on the heap and create an array of pointers to them
    ltc_strings = [t.string(s) for s in strings]

    ltc_strings_addresses = [add_string_to_heap(s, ltc.memory, ltc)[0] for s in ltc_strings] # store the split strings on the heap and get their memory locations
    
    ptrs_to_the_strings = [t.ptr(s, ltc) for s in ltc_strings_addresses] # create ptr tokens for the memory locations of the split strings

    return t.array(ptrs_to_the_strings, ltc, arrayType="ptr", parse=False)
