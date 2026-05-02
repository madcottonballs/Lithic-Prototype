## Style
###     [operation] [type] [inputs] -> [output]
###     $[int_lit]
        Creates an integer literal.
###     "[str_lit]"
###     '[char_lit]'
###     |[bool_lit]
###     ![file]
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

## Info
*       Entry point is the #main function.
*       To return a value from the #main function, you must use exit [any], NOT ret [type] [any]
*       No errors but syntax errors are checked for.
*       The star '*' is used to denote comments


## Arithmatic
###     add integer integer -> var
        Adds the first 2 args and saves in the last.

###    sub integer integer -> var 
        Subtracts the first 2 args and saves in the last.

###    mult integer integer -> var
        Multiplies the first 2 args and saves in the last.

###    div integer integer -> var
        Adds the first 2 args and saves in the last.
## Terminal
###     printf any
        Prints the 1st argument with a newline character.
        Does not flush.
###     print any
        Prints the 1st argument with no newline character.
        Does not flush.
###     flush
        Flushes the IO stream.
###     input -> var
Prompts user input from the terminal and stores the result into the var.
Prints a newline character after the input is read.

## misc functions

###     make_var type -> var
        Initalizes a variable with that type.

###     mov any -> var
        Sets an existing variable to have the value of arg 1.
###     typeof any -> var
        Loads the type of the data entered into the variable as a string.
###    *inlineCpp string
        Writes the text entered into the generated C++ file.
###    *inlineAsm string
        Writes the text entered into the generated Asm file.
## file IO
###   *file_open [string] [string] -> [file]
        Opens the file referenced by the first string and saves it in the file reference. The mode of the file opening is the 2nd string. Valid modes are "r" for reading and "w" for write.  
###   *file_close [file]
        Closes the file, freeing it from your programs memory. The file reference cannot be used in future file operations unless opened again. 
###   *file_write_all [file] [string]
       Overwrites the content of a file to be the string. File cursor moves to the end of the file after writing. 
###   *file_write_line [file] [string]
       Overwrites the content of a single line of a file to be the string. The line index is the file cursor which is implicitly incremented the length of the string by this operation. A line is defined by a newline character. 
###   *file_write_byte [file] [integer]
       Writes the content of a single byte of an integer (must be u8 or i8) into a file. The byte index is the file cursor which is implicitly incremented by 1 by this operation.
###   *file_read_all [file] -> [var]
       Reads all the contents of a file into a string represented by the var.
###   *file_read_line [file] -> [var]
       Reads the content of a single line of a file into a string represented by the var. The line index is the file cursor which is implicitly incremented the length of the string by this operation. A line is defined by a newline character. The newline character is not included in the saved string.
###   *file_read_byte [file] -> [var]
       Reads the content of a single byte of a file into a string represented by the var. The byte index is the file cursor which is implicitly incremented by 1 by this operation.
###   *file_eof [file] -> [var]
        Checks if the next byte after the file cursor is an EOF (end of file) byte and saves it into the Boolean (represented by the var).

###   *file_seek [file] [integer byte_offset] [string whence] -> [var]
        Whence = "start", "current", "end"
        Moves the file cursor to a specific byte. If whence is "start", the byte offset is starting from byte 0 of the file. If whence is "end", the byte offset is based around the last byte of the file. If whence is "current", the byte offset is based on the current file cursor. Returns either false or true to the var arg depending on if the operation was successful. 
###   *file_tell [file] -> [var]   
        returns current cursor position as an integer to the var. 
###   *file_line_advance [file] [integer]   
        moves file cursor forward N lines. String based, not byte based. A line is defined by a newline character. 
###   *file_line_rewind [file] [integer]    
        moves file cursor backward N lines. String based, not byte based. A line is defined by the newline character. 
###   *file_byte_advance [file] [integer]   
        moves file cursor forward N bytes. 
###   *file_byte_rewind [file] [integer]    
        moves file cursor backward N bytes. 
###   *file_flush [file]
        Immediately writes all content stored in the file buffer to disk. 

###     define #[func] [arg_type]
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
Basic set up for a function:
```
define #ltc_main

    ret i32 $0

end #ltc_main
```

###    end #[func]
        Ends a function body.
###    call #[func] [any] -> [type] [var]
        Executes a function's block.
        All tokens following the function name but before the arrow oper are passed in as the arguments to the function.
        The 2 tokens after arrow oper are the destination variable and it's type. 
        Example where %add_result will be loaded with the result of the function:
```
               make_var i32 -> %add_result 
               call #add $9 $ 6 -> i32 %add_result
```
###     ret [type] [any]
        Exits the function, returning to caller.
        Also returns the specified value (arg 2) to the caller. 

## boolean functions
###     equal any any -> var
Checks if both are the same, stores result in the variable.
###     greater integer integer -> var
Checks if the left side is greater than the right side, stores result in the variable.
###     less integer integer -> var
Checks if the left side is less than the right side, stores result in the variable.

###     and boolean boolean -> var
Runs a logical and operation on the boolean arguments and saves the result in the variable.
###     or boolean boolean -> var
Runs a logical or operation on the boolean arguments and saves the result in the variable.
###     not boolean -> var
Runs a logical not operation on the boolean argument and saves the result in the variable.