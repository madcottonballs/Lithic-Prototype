* star denotes a not yet added feature
## To Do
* Stack mechanism broke the free operator
* Function parameters aren't working with arrays
* Cannot do indexed string assignment
* var scoping is broken

# Details
* This is a prototype of a minimalist imperative programming language.
* This language is called Lithic.
* Lithic uses the file extension ".ltc".
* All programs enters at the main() function.
* All functions return a value.
* Lithic has a statically typed, explictly declared, fixed-width primitive type system with block-scoped shadowing. 

# Syntax Highlighting
* There is support for syntax highlighting in VS code.
* To add support to *your* VScode, paste the "ltc-syntax-highlighting" folder in this project into "C:\Users\your user\.vscode\extensions" and reload VScode.

# How to run
>	.\Lithic filename.ltc

# operators
##	arithmatic
* 		Pointer arithmatic is fully supported. Because pointers don't tell what they're pointing to, pointer arithmatic is byte-based, not type-based like in C.

###		[integer] + [integer]
			Add operator adds the values of the numbers together.
###		[integer] - [integer]
			Sub operator subtracts the right number from the left.
###		[integer] * [integer]
			Multiply operator multiplies the values of the numbers together.
###		[integer] / [integer]
			Divide operator divides the value of the left by the right.

###		[integer var_ref] += [integer]
			Addition assignment operator adds the right number to the value of the variable of an integer type.
###		[integer var_ref] -= [integer]
			Subtraction assignment operator subtracts the right number from the value of the variable of an integer type.
###		*[integer var_ref] *= [integer]
			Multiplication assignment operator multiplies the right number with the value of the variable of an integer type.
###		*[integer var_ref] /= [integer]
			Division assignment operator divides the right number from the value of the variable of an integer type.
		
###		[integer var_ref]++
			Increment operator adds 1 to the variable of an integer type.
			Ex: 
>				x++
###		[integer var_ref]--
			Decrement operator subtracts 1 from the variable of an integer type.
			Ex: 
>				x--
###		*[integer var_ref]**
			Double operator multiplies the variable of an integer type by 2.
			Ex:
>				x**
###		*[integer var_ref]//
			Halve operator divides the variable of an integer type by 2.
			Ex: 
>				x//
###		*[array[integer] var_ref] $ [operator] [integer]
			Applies the operation to every number in the array.
			Ex: 
>			x $ * 5 /* every i32 in the array 'x' is multiplied by 5 */
##	logical:
###		![boolean]
			Inverts the boolean. false becomes true, true becomes false.
##	pointers:
###		*@[ptr]
			Dereferences a ptr.
			Ex:
```
				let i32 x = 5;
				let ptr y = &x;
				printf(@y)		*/ output: 5 /*
```
###		&[any]
			Memloc operator.
			Retrieves the address of the object in memory.
			In the interpreter, will only work on data stored in memory (like variables), not literals.
			Ex:
```
				let i32 x = 5;
				let ptr y = &x;
```
##	misc:
###		[any] -> [type]
			Cast operator converts the first obj into the type referenced.
			Ex: 
>			5 -> string		/* where 5 is a i32, then turns into a string */
###		*[integer]~[integer]
			Random operator returns a random number in range of the first i32 and second i32 (inclusive).
			Ex: 
>			 5~9		/* randomly selects either 5, 6, 7, 8, or 9 */
###		[var_ref]^
			Deletes the variable from namespace.
			Memory is not freed, just the variable pointer to it.
			Returns x's last value.
			Ex: 
>			x^	/*deletes the variable 'x', returns 'x's value */
# Functions:
##	Terminal:
###		*print([string | char])
			Unformatted print. Sends the text entered to the terminal, with no extra characters.
			Ex: 
>				print('hello world\n'); 

###		printf([string | char | i32 | array | boolean], [char])
			Formatted print. Sends the text entered to the terminal. 
			Default end character automatically attached is the newline character.
			To change end character, pass in an optional 2nd argument.
			Exs: 
>				printf("hello world") 
>				printf("hello world", '\t')
		
###		input()
			Pauses execution of the program to ask the user to enter text from the terminal.
			The text entered is returned to the functional call as a string.
			Ex:
>				printf( input() );
>				/* This example will display the text the user just entered. */

###		*cmd([string])
			Runs the entered string as a command prompt in the terminal.
##	Inline:
###		*inline_C([string])
			Adds the string you enter as a line in the intermeddiate generated C file.
			Only works in translator versions that have C in the pipeline (compiler version).
			
###		*inline_IR([string])
			Adds the string you enter as a line in the intermeddiate generated C file.
			Only works in translator versions that have the IR in the pipeline (interpreter version).

###		*inline_Asm([string])
			Adds the string you enter as a line in the intermeddiate generated Asm file.
			Only works in translator versions that have Asm in the pipeline (compiler version).
##	Misc:
###		exit([integer])
			Immediantly ends the program and returns the number as the exit code.
###		import [str]
			Inlines the code in the .ltc file referenced by the string.
			All functions in the imported file will have their named prefixed by the filename. 
			Ex:
```				import "test.ltc";
				define main() {
					test.doSmth();
					return(0);
				}
```		
##	Data:
###		sLength([string])
			Returns (as a i32) the number of characters in the string.
			Ex: 
>				let i32 x = sLength("hello world");

###		let [type] [var_ref] = [value]
			Creates a new variable of the type specified in argument 1 with the name specified in argument 2.
			Optionally assigns it a value with argument 3.
			To only initalize without assignment, do not include "= [value]".
			Exs:
```
				let i32 x = 5;
				let i32[3] y = [5, 2, 9];
```
###		typeof([any])
			You can enter anything into this function.
			Some things may work, some may not.
			Will return the type of the data types as a string.
		
###		sizeof([i32 | char | string | boolean])
			Will return the byte size of each data type as a i32.
			Ex:
>			sizeof(5)	/* This example would return 4, because dwords have a byte size of 4. */

###		sConcat([string], [string])
			All arguments must be strings.
			Must be >= 2 arguments.
			All arguments are joined together and return a single string.
			Ex:
>				sConcat("hello ", "world ", "it's a lovely day!")	/* This would return the string "hello world it's a lovely day!" */

		
###		aConcat([array], [array])
			All arguments must be arrays.
			Must be >= 2 arguments.
			All arrays passed in must be of the same type (ex.: i32[])
			All arguments are joined together and return a single array.
			Ex:
> 				aConcat([3, 2], [9, 21, 4], [2, 9]) 		/* This would return the array [3, 2, 9, 21, 4, 2, 9]. */

###		aLength([array])
			Returns the number (i32) of elements in the array passed in.
		
###		aSet([array], [i32], [any])
			Indexed array element reassignment.
			The first argument is a reference to a array.
			The second argument is the index of where the new value must replace existing data.
			The third argument is the new object replacing the old. 

###		cast([any], [type])
			Equivalent to the cast operator.
			Cast function converts the first obj into the type referenced.
			Ex: 
>				let string x = cast(5, string);	/* where 5 is a i32, then turns into a string assigned to var 'x' */

			If any casts are not mentioned, they are illegal.
			casting to integers:
				from other integer types:
					The destination integer type must be capable of holding the value of the source integer.
					For example, if you want to cast a i32 to a i64, that will always be possible since all i64's can hold any i32.
					But if you want to cast a i32 to a u8, the value of that i32 must be within the bounds of the u8 (0-255).
				from boolean:
					true turns to a 1.
					false turns to a 0.
				from string:
					All characters in the string must be a digit.
					For example, the string "273" can turn to a i32, but the string "hello" cannot turn to any integer type.
				from char:
					The character will return it's ascii index representation.
					Example: char object 'h' will turn to the integer 104.
				from ptr:
					Returns the memory address the ptr is referencing.
			casting to booleans:
				from integers:
					All integers except 0 return true.
					0 returns false.
				from string:
					Empty strings return false.
					Strings with any characters return true.
				from char:
					Empty chars return false.
					Chars with any character return true.
				from ptr:
					Null pointers return false, any other returns true.
			casting to string:
				from integers:
					Each digit in the integer is encoded into the ascii format.
					Example: an i32 with the value of 50 turns to a string with the value "50"
				from booleans:
					false returns "false", true returns "true".
				from char:
					Returns a 1 character string. Example: 'h' -> string == "h"
				from ptr:
					Pointers are just u64's under the hood.
					Each digit in the ptr is encoded into the ascii format.
					Returns the memory address of the ptr as a string.
			casting to char:
				from integers:
					The integer value is used as an index for ascii.
					Example: 104 -> char == 'h'
				from string:
					The string must be only one character.
			casting to ptr:
				from integers:
					The integer must be able to fit in a u64.
					Turns the integer into a memory address.
				from strings:
					All characters in the string must be a digit.
					For example, the string "273" can turn to a u64 (and so can be a ptr), but the string "hello" cannot turn to a ptr type.

### 	malloc([i32])
			Reserves a block of memory in the stack for the programmer to use.
			The size of this new memory is determined by the argument passed in.
			Returns a ptr to the first byte of this block.
			In the interpreted version, if you allocate beyond the range of the virtual memory, it currently throws an error. Eventually *dynamic expansion will be supported.
			Ex:
>				let ptr x = malloc(5);
			This reserves 5 bytes for the programmer to use, x is a ptr to the first byte.

###		coredump()
			In interprter version, currently prints the sp and virtual memory contents.
			Will eventually dump to a *file in both versions.

# Control Flow:
##	if ([boolean]) { ... }
		If the boolean resolves to true, the code inside the brackets is run.
		If the boolean resolves to false, the code inside the brackets is skipped.
##	else { ... }
		If the above if-statement boolean resolves to true, the code inside the else-brackets does not run.
		If the if-statement boolean resolves to false, the code inside the else-brackets runs.
##	iterate ([var_ref], [i32]) { ... }
		Implictly creates a new variable of type i32 based on argument 1.
		Implictly adds 1 to this variable per loop.
		Implictly checks if the variable is less than the 2nd argument every loop.
		Implicit version of "for (let i32 x = 0, x < 10, x++) { ... }"
		Ex: 
```		
			iterate (x, 5) {
				printf(x);
			} 
			/* 
			this code will output
			0
			1
			2
			3
			4
			/*
```
##	while (boolean) { ... }
		While the boolean is true, the code block will loop.
		Boolean is checked at the start of each loop.
		Ex:
```
		let i32 x = 0;
		while (x < 5) {
			printf(x);
			x++;
		}
			/* 
			this code will output
			0
			1
			2
			3
			4
			/*		
```
##	for ([let statement], [boolean], [var_ref][operator]) { ... }
		Creates a new variable based on the let statement in the first argument.
		Loops over the code in the block until the boolean is false.
		Runs the operator on the variable referenced in the third argument during every pass.
		Ex: 
```
		for (let i32 x = 0, x < 10, x++) {
			pass();
		}
 		/* creates 'x' variable, adds 1 to x every pass, until x reaches 10. pass() does nothing. */ 	
```
##	*enumerate ([let statement], [let statement], [array | string])
		Creates a new variable from the first argument.
		Every pass, the first variable is incremented. This variable is the index.
		Creates a new variable from the second argument.	
		Every pass, the second variable is the element indexed in the third argument.
		Ex: 
>			enumerate (let i32 i, let char v, "hello world") { ...}	/* This would go character by character in "hello world". i = 0, v = 'h', then i = 1, v = 'e', etc. /*
##	*#[label]
		Assigns that line of code a label.
		This can be referenced later in a goto() function.
##	*goto([label])
		Jumps to the labeled line of code. There is no return.
## 	pass
		Does nothing.
##	define [func_name]([type] [arg_name]) { ... }
		Creates a custom user function.
		All functions must return a single object.
		To return multiple objects, wrap them in a array and return the array.
		To return multiple objects of different types, wrap them in a ptr array with the elements being ptr's to your objects.
		The program enters at define main() {}.
		Ex:
```
			define print_hello_world(string appendage) {
				let string new = sConcat("hello ", appendage);
				printf(new);
				return(0);
			}

			define main() {
				print_hello_world("world");  /* output: "hello world" */
				return(0);
			}
```
		Arguments passed into the function can be modified.
		Changes to variables passed into the function will not affect the variable outside the function. 
		Ex:
```
			define example(i32 var_test) {
				var_test++; 	/* var_test is now 6 */
				return(0);
			}
			define main() {
				let i32 x = 5;
				example(x);
				printf(x); 		/* output: 5 */
				return(0);
			}
```
# Types
*	All integer types are "true" when cast to boolean if they're not 0.
*	When casted to char, returns the ascii
##	i64
		64 bit signed integer
		8 bytes.
##	i32
		32 bit signed integer
		This is the default return type of most functions.
		All integer literals default to an i32.
		You'll need to cast every integer literal to a different integer type if you need an integer of that type.
		4 bytes.
##	i16
		16 bit signed integer
		2 bytes.
##	i8
		8 bit signed integer
		1 byte.
##	u64
		64 bit unsigned integer
		8 bytes.
##	u32
		32 bit unsigned integer
		4 bytes.
##	u16
		16 bit unsigned integer
		2 bytes.
##	u8
		8 bit unsigned integer
		1 byte.

##	*f64
		64 Bit signed float

##	string
		Stored as an array of characters. Holds text. Auto-Null-terminated.
		Resolves to true when cast to boolean if string is not empty.
		Ex: 
>			let string x = 'hello world';
##	char
		A ubyte interpreted as a character code. Holds a single letter, number, etc.
		Resolves to true when cast to boolean if char is not empty.
		Ex: 
>			let char x = 'h';
##	ptr
		Resolves to true when cast to boolean if not a null ptr.
		A u64 that references a memory location.
##	type[array]
		Fixed-sized immutable continous memory structure that can hold primitive types.
		If the arrayType is not specified, it is assumed based on the type of the first element.
		Matrixes (including string[]) are not supported and will never be supported.

		Ex:
>			let i32[3] x = [3, 5, 7]; /* creates an array 'x' of size 3 preloaded with the numbers 3, 5, and 7 */
##	label
		Named line of code.