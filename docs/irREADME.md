## Style
###     [operation] [type] [inputs] -> [output]
###     $[int_lit]
        Creates an integer literal.
###     "[str_lit]"
###     '[char_lit]'
###     |[bool_lit]
###     %[var]
        Always use when you're referencing a var.
###     #[func]
        Function reference

## Types
###     i32
###     i64
###     i16
###     i8
###     u32
###     u64
###     u16
###     u8
###     string
###     char
###     boolean

## functions
###     add [var | int_lit] [int_lit | var ] -> [var]
        Adds the first 2 args and saves in the last.

###    *sub [type] [var | int_lit] [int_lit | var ] -> [var] 
        Subtracts the first 2 args and saves in the last.

###    *mult [type] [var | int_lit] [int_lit | var ] -> [var]
        Multiplies the first 2 args and saves in the last.

###    *div [type] [var | int_lit] [int_lit | var ] -> [var]
        Adds the first 2 args and saves in the last.

###     print [any]
        Prints the 1st argument with a \n.
        Does not flush.

###     make_var [type] -> [var]
        Initalizes a variable with that type.

###     mov [type] [value] -> [var]
        Sets an existing variable to have that value.
        Value must have the same type as the variable.

###    *inlineCpp [string_lit]
        Writes the text entered into the generated C file.

###     define #[func]
        Opens a function body. 
        All following tokens should be type references that equate to the types of the parameters.
        In the function block, all parameters passed into the function are automatically made into sequential variables.
        Ex:
```
                define #add i32 i32
                        make_var i32 -> %return_val
                        add i32 %arg0 %arg1 -> %return_val
                        ret %return_val
                end #add

                define #main i32
                        make_var i32 -> %return_val
                        call add $5 $9 -> i32 %return_val
                        ret %return_val
                end #main
```
###    end #[func]
        Ends a function body.
###    call #[func] [any] -> [type] [var]
        Executes a function's block.
        All tokens following the function name but before the arrow oper are passed in as the arguments to the function.
        The 2 tokens after arrow oper are the destination variable and it's type. Example:
```
               make_var i32 -> %add_result 
               call #add $9 $ 6 -> i32 %add_result
```
###     flush
        Flushes the IO stream.