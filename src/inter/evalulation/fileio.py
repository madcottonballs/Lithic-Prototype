def _update_cursor_metadata(file_obj, new_cursor, ltc):
    file_obj.cursor = new_cursor
    # Persist cursor back into variable metadata when this file came from a var_ref.
    if hasattr(file_obj, "var_name") and file_obj.var_name is not None:
        var_meta, scope_level = ltc.helper.locate_var_in_namespace(
            ltc.namespace, file_obj.var_name, return_just_the_check=False
        )
        if var_meta is not None and var_meta.get("type") == "file":
            ltc.namespace[scope_level][file_obj.var_name]["cursor"] = new_cursor

def resolve_open(tokens, i, ltc) -> None:
    t = ltc.t
    func_node = tokens[i]
    if len(func_node.args) != 2:
        ltc.error("open expects exactly two arguments: a string literal for the file path and a string literal for the mode (e.g. 'r' for read, 'w' for write)")

    if not (isinstance(func_node.args[0], t.string) and isinstance(func_node.args[1], t.string)):
        ltc.error("both arguments to open must be strings")
    mode = func_node.args[1].val
    name = func_node.args[0].val

    if mode not in ['r', 'w']:
        ltc.error("invalid file mode: " + mode + ". Valid modes are \"r\" for read and \"w\" for write.")
    if mode == 'r':
        try:
            with open(name, 'r') as f:
                contents = f.read()
        except FileNotFoundError:
            ltc.error(f"file not found: {name}")
    elif mode == 'w':
        with open(name, 'w') as f:
            try:
                with open(name, 'r') as f2:
                    contents = f2.read() # if file already exists, read its contents so we can persist them in the file object in case the user only wants to alter a lil bit of data
            except FileNotFoundError:
                contents = str() # if file doesn't exist yet, start with empty contents


    ret_obj = t.file(func_node.args[0].val)
    ret_obj.mode = mode
    ret_obj.contents = contents

    tokens[i] = ret_obj

def resolve_read(tokens, i, ltc) -> None:
    t = ltc.t
    func_node = tokens[i]
    if len(func_node.args) != 1:
        ltc.error("read expects exactly one argument: either a file object returned by open() or a string representing a file path to read from")

    if isinstance(func_node.args[0], t.file):
        file_obj = func_node.args[0]
        if file_obj.mode != 'r':
            ltc.error("can only read from files opened in read mode ('r')")
        contents = file_obj.contents
    elif isinstance(func_node.args[0], t.string):
        file_path = func_node.args[0].val
        try:
            with open(file_path, 'r') as f:
                contents = f.read()
        except FileNotFoundError:
            ltc.error(f"file not found: {file_path}")
    else:
        ltc.error(f"argument to read must be either a file object returned by open() or a string representing a file path to read from, not type {type(func_node.args[0]).__name__}")
    

    tokens[i] = t.string(contents)

def resolve_readline(tokens, i, ltc) -> None:
    t = ltc.t
    func_node = tokens[i]
    if len(func_node.args) == 0 or len(func_node.args) > 2:
        ltc.error("readLine expects one unconditional and one optional argument: readLine(file) or readLine(file, idx)")

    if isinstance(func_node.args[0], t.file):
        file_obj = func_node.args[0]
        if file_obj.mode != 'r':
            ltc.error("can only read from files opened in read mode ('r')")
        if file_obj.contents is None:
            ltc.error("file is empty")
        lines = file_obj.contents.splitlines()
        if not lines:
            ltc.error("file is empty")

        if len(func_node.args) > 1:
            idx = func_node.args[1].val
        else:
            idx = file_obj.cursor

        if idx >= len(lines):
            ltc.error(f"line index {idx} out of range for file with {len(lines)} lines")
        
        line = lines[idx]
        # Persist cursor back into variable metadata when this file came from a var_ref.
        _update_cursor_metadata(func_node.args[0], func_node.args[0].cursor + 1, ltc)# implicit increment of the file cursor after reading a line
    else:
        ltc.error(f"First argument to readLine must be a file object returned by open(), not type {type(func_node.args[0]).__name__}")
    
    tokens[i] = t.string(line)

def resolve_readbyte(tokens, i, ltc) -> None:
    t = ltc.t
    func_node = tokens[i]
    if len(func_node.args) == 0 or len(func_node.args) > 2:
        ltc.error("readByte expects one unconditional and one optional argument: readByte(file) or readByte(file, idx)")

    if isinstance(func_node.args[0], t.file):
        file_obj = func_node.args[0]
        if file_obj.mode != 'r':
            ltc.error("can only read from files opened in read mode ('r')")
        if file_obj.contents is None:
            ltc.error("file is empty")
        contents = file_obj.contents.encode("utf-8")
        
        if not contents:
            ltc.error("file is empty")

        if len(func_node.args) > 1:
            idx = func_node.args[1].val
        else:
            idx = file_obj.cursor

        if idx >= len(contents):
            ltc.error(f"byte index {idx} out of range for file with {len(contents)} bytes")
        
        byte = contents[idx]
        # Persist cursor back into variable metadata when this file came from a var_ref.
        _update_cursor_metadata(func_node.args[0], func_node.args[0].cursor + 1, ltc)# implicit increment of the file cursor after reading a line. Always pass in the real ref to the obj so it can be modified, not the copied version
    else:
        ltc.error(f"First argument to readByte must be a file object returned by open(), not type {type(func_node.args[0]).__name__}")
    
    tokens[i] = t.u8(byte, ltc)


def resolve_advanceByte(tokens, i, ltc) -> None:
    t = ltc.t
    func_node = tokens[i]
    if len(func_node.args) != 2:
        ltc.error("advanceByte expects exactly two arguments: a file object returned by open() and the number of bytes to advance the cursor by")
    file_obj = func_node.args[0]
    advance = func_node.args[1]

    if isinstance(file_obj, t.file):
        if not isinstance(advance, t.integer):
            ltc.error(f"second argument to advanceByte must be an integer representing the number of bytes to advance the cursor by, not type {type(advance).__name__}")
        new_cursor = file_obj.cursor + advance.val
        if new_cursor < 0:
            ltc.error("cannot move file cursor to a negative position")
        if file_obj.contents is not None and new_cursor > len(file_obj.contents):
            ltc.error("cannot move file cursor beyond end of file")
        
        _update_cursor_metadata(file_obj, new_cursor, ltc)
    else:
        ltc.error(f"first argument to advanceByte must be a file object returned by open(), not type {type(func_node.args[0]).__name__}")
    
    tokens[i] = t.i32(0, ltc)

def resolve_advanceLine(tokens, i, ltc) -> None:
    t = ltc.t
    func_node = tokens[i]
    if len(func_node.args) != 2:
        ltc.error("advanceLine expects exactly two arguments: a file object returned by open() and the number of lines to advance the cursor by")
    file_obj = func_node.args[0]
    advance = func_node.args[1]

    if isinstance(file_obj, t.file):
        if not isinstance(advance, t.integer):
            ltc.error(f"second argument to advanceLine must be an integer representing the number of lines to advance the cursor by, not type {type(advance).__name__}")
        new_cursor = file_obj.cursor + advance.val
        if new_cursor < 0:
            ltc.error("cannot move file cursor to a negative position")
        if file_obj.contents is not None and new_cursor > len(file_obj.contents):
            ltc.error("cannot move file cursor beyond end of file")
        
        _update_cursor_metadata(file_obj, new_cursor, ltc)
    else:
        ltc.error(f"first argument to advanceLine must be a file object returned by open(), not type {type(func_node.args[0]).__name__}")
    
    tokens[i] = t.i32(0, ltc)

def resolve_rewindByte(tokens, i, ltc) -> None:
    t = ltc.t
    func_node = tokens[i]
    if len(func_node.args) != 2:
        ltc.error("rewindByte expects exactly two arguments: a file object returned by open() and the number of bytes to rewind the cursor by")
    file_obj = func_node.args[0]
    rewind = func_node.args[1]

    if isinstance(file_obj, t.file):
        if not isinstance(rewind, t.integer):
            ltc.error(f"second argument to rewindByte must be an integer representing the number of bytes to rewind the cursor by, not type {type(rewind).__name__}")
        new_cursor = file_obj.cursor - rewind.val
        if new_cursor < 0:
            ltc.error("cannot move file cursor to a negative position")
        if file_obj.contents is not None and new_cursor > len(file_obj.contents):
            ltc.error("cannot move file cursor beyond end of file")
        
        _update_cursor_metadata(file_obj, new_cursor, ltc)
    else:
        ltc.error(f"first argument to rewindByte must be a file object returned by open(), not type {type(func_node.args[0]).__name__}")
    
    tokens[i] = t.i32(0, ltc)
    
def resolve_rewindLine(tokens, i, ltc) -> None:
    t = ltc.t
    func_node = tokens[i]
    if len(func_node.args) != 2:
        ltc.error("rewindLine expects exactly two arguments: a file object returned by open() and the number of lines to rewind the cursor by")
    file_obj = func_node.args[0]
    rewind = func_node.args[1]

    if isinstance(file_obj, t.file):
        if not isinstance(rewind, t.integer):
            ltc.error(f"second argument to rewindLine must be an integer representing the number of lines to rewind the cursor by, not type {type(rewind).__name__}")
        new_cursor = file_obj.cursor - rewind.val
        if new_cursor < 0:
            ltc.error("cannot move file cursor to a negative position")
        if file_obj.contents is not None and new_cursor > len(file_obj.contents):
            ltc.error("cannot move file cursor beyond end of file")
        
        _update_cursor_metadata(file_obj, new_cursor, ltc)
    else:
        ltc.error(f"first argument to rewindLine must be a file object returned by open(), not type {type(func_node.args[0]).__name__}")
    
    tokens[i] = t.i32(0, ltc)

def resolve_getCursor(tokens, i, ltc) -> None:
    t = ltc.t
    func_node = tokens[i]
    if len(func_node.args) != 1:
        ltc.error("getCursor expects exactly one argument: a file object returned by open()")
    file_obj = func_node.args[0]

    if isinstance(file_obj, t.file):
        cursor = file_obj.cursor
    else:
        ltc.error(f"argument to getCursor must be a file object returned by open(), not type {type(func_node.args[0]).__name__}")
    
    tokens[i] = t.u32(cursor, ltc)

def resolve_readlines(tokens, i, ltc) -> None:
    t = ltc.t
    func_node = tokens[i]
    if len(func_node.args) != 1:
        ltc.error("readLines expects one argument: readLines(file | String)")
    file_obj = func_node.args[0]

    if isinstance(file_obj, t.file): # this is used to get the lines of the file as an array of strings regardless of if a file obj or a file path string is passed in
        if file_obj.mode != 'r':
            ltc.error("can only read from files opened in read mode ('r')")
        if file_obj.contents is None:
            ltc.error("file is empty")
        lines = file_obj.contents.splitlines()
        if not lines:
            ltc.error("file is empty")
    elif isinstance(file_obj, t.string):
        file_path = file_obj.val
        try:
            with open(file_path, 'r') as f:
                contents = f.read()
        except FileNotFoundError:
            ltc.error(f"file not found: {file_path}")
        lines = contents.splitlines()
        if not lines:
            ltc.error("file is empty")
    else:
        ltc.error(f"First argument to readLines must be a file object returned by open(), not type {type(func_node.args[0]).__name__}")
    
    tokens[i] = ltc.helper.create_string_array(ltc, lines)

def resolve_readbytes(tokens, i, ltc) -> None:
    t = ltc.t
    func_node = tokens[i]
    if len(func_node.args) != 1:
        ltc.error("readBytes expects one argument: readBytes(file | String)")
    file_obj = func_node.args[0]

    if isinstance(file_obj, t.file): # this is used to get the lines of the file as an array of strings regardless of if a file obj or a file path string is passed in
        if file_obj.mode != 'r':
            ltc.error("can only read from files opened in read mode ('r')")
        if file_obj.contents is None:
            ltc.error("file is empty")
        contents = file_obj.contents
        if not contents:
            ltc.error("file is empty")
    elif isinstance(file_obj, t.string):
        file_path = file_obj.val
        try:
            with open(file_path, 'r') as f:
                contents = f.read()
        except FileNotFoundError:
            ltc.error(f"file not found: {file_path}")
        if not contents:
            ltc.error("file is empty")
    else:
        ltc.error(f"First argument to readBytes must be a file object returned by open(), not type {type(func_node.args[0]).__name__}")
    
    contents = contents.encode("utf-8") # convert string to bytes
    contents = [t.u8(b, ltc) for b in contents] # convert each byte to a u8 object
    contents = t.array(contents, ltc, arrayType="u8", parse=False) # convert list of u8 objects to an array of u8 objects

    tokens[i] = contents

def resolve_atEOF(tokens, i, ltc) -> None:
    t = ltc.t
    func_node = tokens[i]
    if len(func_node.args) != 1:
        ltc.error("atEOF expects exactly one argument: a file object returned by open()")
    file_obj = func_node.args[0]
    EOF = 26

    if isinstance(file_obj, t.file):
        if file_obj.mode != 'r':
            ltc.error("can only read from files opened in read mode ('r')")
        if file_obj.contents is None:
            ltc.error("file is empty")
        contents = file_obj.contents
        if not contents:
            ltc.error("file is empty")

        contents = contents.encode("utf-8") # convert string to bytes for accurate byte length

        at_eof = contents[file_obj.cursor] == EOF if file_obj.cursor < len(contents) else True # if cursor is at or beyond end of contents, we're at EOF. Otherwise, check if the current byte is a EOF (26)
    else:
        ltc.error(f"argument to atEOF must be a file object returned by open(), not type {type(func_node.args[0]).__name__}")
    
    tokens[i] = t.boolean(at_eof)