"""This module turns raw token string literals into typed token nodes, which can then be used for type checking and evaluation. This also includes all LTC data types as token node classes, which can be used to store type information for type checking and evaluation purposes."""

class token:
    def __init__(self, val):
        self.val = val

class ltc_type(token):  # base class for all LTC data types. This is used to distinguish between syntax tokens and typed tokens
    def __init__(self, val):
        self.val = val
        self.inmemory = False
        self.memloc = None

class string(ltc_type):
    def __init__(self, val):
        super().__init__(val)
        self.val = str(val).replace("\\n", "\n").replace("\\t", "\t").replace("\\\"", "\"").replace("\\\'", "\'").replace("\\\\", "\\")
class char(ltc_type):
    def __init__(self, val):
        super().__init__(val)
        self.val = str(val).replace("\\n", "\n").replace("\\t", "\t").replace("\\\"", "\"").replace("\\\'", "\'").replace("\\\\", "\\")
    def load_to_memory(self, memory, addr):
        memory[addr] = self.val.to_bytes(self.size, byteorder='little', signed=False)
    def read_from_memory(self, memory, addr):
        return chr(int.from_bytes(memory[addr], byteorder='little', signed=False))
    
class boolean(ltc_type):
    def __init__(self, val):
        super().__init__(val)
        self.size = 1
    def load_to_memory(self, memory, addr):
        memory[addr] = self.val.to_bytes(self.size, byteorder='little', signed=False)
    def read_from_memory(self, memory, addr):
        return bool(int.from_bytes(memory[addr], byteorder='little', signed=False))

class array(ltc_type):
    def __init__(self, val, arrayType=None, parse=True):
        super().__init__(val)
        self.arrayType = arrayType
        self.parsed = not parse
        if parse:
            self.parse()
    def parse(self):
        """Turns raw tokens between square brackets stored in self.val to a list of just the elements of the array obj\n
        Ex:
            'self.val == [element, comma, element]' -> 'self.val == [element, element]'"""
        if self.parsed:
            return
        if not isinstance(self.val, list):
            self.parsed = True
            return
        if len(self.val) == 0:
            self.parsed = True
            return

        # If arrayType is not specified, infer it from the first element.
        if self.arrayType is None:
            self.arrayType = type(self.val[0]).__name__

        # Single-element array literal: [x]
        if len(self.val) == 1:
            if type(self.val[0]).__name__ != self.arrayType:
                raise TypeError(f"Expected array literal element type '{self.arrayType}', but found '{type(self.val[0]).__name__}'")
            self.parsed = True
            return

        for i, element in enumerate(self.val):
            if i % 2 == 1: # comma expected
                if not (isinstance(element, token) and element.val == ","):
                    raise SyntaxError("Expected ',' between elements in array literal creation")
            else: # element expected
                if type(element).__name__ != self.arrayType:
                    raise TypeError(f"Expected all elements of array literal decleration to be type '{self.arrayType}', but found '{type(element).__name__}'")

        self.val = [element for i, element in enumerate(self.val) if i % 2 == 0]
        self.parsed = True

    def get_size(self):
        declared_size = getattr(self, "size", None)
        if declared_size is None:
            self.parse() # ensures .val is the parsed form
            self.size = len(self.val)
        return self.size

class function(token):
    def __init__(self, name: str, args: list[token]):
        self.val = name
        self.args = args
        self.process_args()
    def process_args(self):
        if self.val == "let":
            # Intended syntax path: let i32 x = 5
            if len(self.args) == 4:
                return
            # Intended syntax path: let i32 x
            if len(self.args) == 2:
                return
            # Backward-compat path: let(i32, x, =, 5)
            if len(self.args) > 1:
                for i, arg in enumerate(self.args):
                    if i % 2 == 1 and not (isinstance(arg, token) and arg.val == ","):
                        raise ValueError("Expected ',' between function arguments")
                self.args = [arg for i, arg in enumerate(self.args) if i % 2 == 0]
                return

        if len(self.args) > 1:
            #if self.val == "let":

            # For multiple args the expected shape is:
            # arg0, ",", arg1, ",", arg2, ...
            for i, arg in enumerate(self.args):
                if i % 2 == 1:
                    if not (isinstance(arg, token) and arg.val == ","):
                        raise ValueError("Expected ',' between function arguments")

            # Keep only actual argument positions and drop commas.
            self.args = [arg for i, arg in enumerate(self.args) if i % 2 == 0]

# integer types are all stored as the same integer node, but can be tagged with their specific type for type checking purposes.

class integer(ltc_type):
    def __init__(self, val):
        super().__init__(val)
        # Store numeric literals as numbers, not strings.
        if isinstance(val, str):
            self.val = int(val)
        elif isinstance(val, float) and val.is_integer():
            self.val = int(val)
        else:
            self.val = int(val)
        self.size = None
        self.signed = None
    def load_to_memory(self, memory, addr):
        memory[addr:addr + self.size] = self.val.to_bytes(self.size, byteorder='little', signed=self.signed)
    def read_from_memory(self, memory, addr):
        return int.from_bytes(memory[addr:addr + self.size], byteorder='little', signed=self.signed)
    def int_bounds_check(self):
        if self.signed:
            self.min_val = -(2 ** (self.size * 8 - 1))
            self.max_val = (2 ** (self.size * 8 - 1)) - 1
        else:
            self.min_val = 0
            self.max_val = (2 ** (self.size * 8)) - 1

        if not ((self.min_val) <= (self.val) <= (self.max_val)):
            raise OverflowError(f"Integer '{self.val}' exceeds the range of type with size {self.size} bytes and signed={self.signed}")
class i32(integer): # i32
    def __init__(self, val):
        super().__init__(val)
        self.signed = True
        self.size = 4
        self.int_bounds_check()
    def read_from_memory(self, memory, addr):
        return i32(super().read_from_memory(memory, addr))
class i64(integer): # i64
    def __init__(self, val):
        super().__init__(val)
        self.signed = True
        self.size = 8
        self.int_bounds_check()
    def read_from_memory(self, memory, addr):
        return i64(super().read_from_memory(memory, addr))
class i16(integer): # i16
    def __init__(self, val):
        super().__init__(val)
        self.signed = True
        self.size = 2
        self.int_bounds_check()
    def read_from_memory(self, memory, addr):
        return i16(super().read_from_memory(memory, addr))
class i8(integer): # i8
    def __init__(self, val):
        super().__init__(val)
        self.signed = True
        self.size = 1
        self.int_bounds_check()
    def read_from_memory(self, memory, addr):
        return i8(super().read_from_memory(memory, addr))
class u32(integer): # u32
    def __init__(self, val):
        super().__init__(val)
        self.signed = False
        self.size = 4
        self.int_bounds_check()
    def read_from_memory(self, memory, addr):
        return u32(super().read_from_memory(memory, addr))
class u64(integer): # u64
    def __init__(self, val):
        super().__init__(val)
        self.signed = False
        self.size = 8
        self.int_bounds_check()
    def read_from_memory(self, memory, addr):
        return u64(super().read_from_memory(memory, addr))
class u8(integer): # u8
    def __init__(self, val):
        super().__init__(val)
        self.signed = False
        self.size = 1
        self.int_bounds_check()
    def read_from_memory(self, memory, addr):
        return u8(super().read_from_memory(memory, addr))
class u16(integer): # u16
    def __init__(self, val):
        super().__init__(val)
        self.signed = False
        self.size = 2
        self.int_bounds_check()
    def read_from_memory(self, memory, addr):
        return u16(super().read_from_memory(memory, addr))
class ptr(u64): # ptr (64-bit unsigned integer representing a memory address)
    def __init__(self, val):
        super().__init__(val)
    def read_from_memory(self, memory, addr):
        return ptr(super().read_from_memory(memory, addr).val) # ptr is a wrapper around u64, so we need to extract the integer value and wrap it back in a ptr
   
class var_ref(token):
    pass

class user_function():
    def __init__(self, func_name: str, arguments: list):
        self.val = func_name
        self.arguments = arguments
        self.process_args()

    def process_args(self):
        if len(self.arguments) > 1:
            # For multiple args the expected shape is:
            # arg0, ",", arg1, ",", arg2, ...
            for i, arg in enumerate(self.arguments):
                if i % 2 == 1:
                    if not (isinstance(arg, token) and arg.val == ","):
                        raise ValueError("Expected ',' between function arguments")

            # Keep only actual argument positions and drop commas.
            self.arguments = [arg for i, arg in enumerate(self.arguments) if i % 2 == 0]

    def validate_args(self, user_functions):
        if self.val not in user_functions:
            raise NameError(f"Function '{self.val}' is not declared")

        entry = user_functions[self.val]
        if isinstance(entry, dict):
            expected_arg_types = entry.get("arg_types", [])
        elif isinstance(entry, list) and len(entry) > 0:
            # Backward compatibility with old shape: [arg_types, body]
            expected_arg_types = entry[0]
        else:
            raise TypeError(f"Invalid function metadata for '{self.val}'")

        if len(expected_arg_types) != len(self.arguments):
            raise SyntaxError(
                f"Function '{self.val}' expected {len(expected_arg_types)} arguments, but got {len(self.arguments)}"
            )

        for i, expected_type_name in enumerate(expected_arg_types):
            actual_arg = self.arguments[i]
            actual_type_name = type(actual_arg).__name__
            if isinstance(actual_arg, array):
                actual_type_name = f"{actual_arg.arrayType}[{actual_arg.get_size()}]"

            if actual_type_name != expected_type_name:
                raise TypeError(
                    f"Function '{self.val}' expected argument {i+1} to be type '{expected_type_name}', "
                    f"but got '{actual_type_name}'"
                )

def parser(tokens, ltc): # tokens is not always ltc.tokens
    default_int = i32
    # Convert raw token strings into typed token nodes.
    for token_index, token_text in enumerate(tokens):
        is_int = True
        char_index = 0

        # handle variable references
        if ltc.helper.locate_var_in_namespace(ltc.namespace, token_text, return_just_the_check=True):
            tokens[token_index] = var_ref(token_text)
            continue

        # handle boolean literals
        if token_text == "false":
            tokens[token_index] = boolean(False)
            continue
        if token_text == "true":
            tokens[token_index] = boolean(True)
            continue

        # for every character in the token, check if it is a digit. If any character is not a digit, this token cannot be an integer literal.
        while char_index < len(token_text):
            current_char = token_text[char_index]

            is_char_literal = ( len(token_text) == 3 and token_text[0] == "\'" and token_text[-1] == token_text[0] )
            is_string_literal = ( len(token_text) >= 2 and token_text[0] == "\"" and token_text[-1] == token_text[0] )
            
            if is_char_literal:  # Quoted token is a char literal; strip surrounding quotes.
                is_int = False
                tokens[token_index] = char(token_text[1])
                break
            elif is_string_literal:  # Quoted token is a string literal; strip surrounding quotes.
                is_int = False
                tokens[token_index] = string(token_text[1:-1])
                break
            if current_char not in "0123456789":
                is_int = False
                break

            char_index += 1

        # If all characters were digits, convert token to numeric node.
        if is_int:
            tokens[token_index] = default_int(token_text)
        
        # Default case: leave unknown identifiers/symbols as generic token nodes.
        if isinstance(tokens[token_index], str):
            tokens[token_index] = token(token_text)

    return tokens