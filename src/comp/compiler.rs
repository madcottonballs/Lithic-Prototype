use crate::helper::{self, format_param_list, resolve_includes};
use crate::parser::{find_functions, parser, Func, Token};
use crate::{lexer, resolve_typeof_type, Compiler};

pub fn compile_file(source_code: &str) -> Vec<String> {
    let mut compiler = Compiler::new();  // create a new compiler instance

    // find all functions in the source code, for simplicity, we'll assume that the entire source code is main() function
    let functions: Vec<Func> = find_functions(source_code);
    let mut prototypes: Vec<String> = Vec::new();

    let int_type_redefs: Vec<String> = vec![ // add typedefs for types from stdint.h and std::string, this is needed because we're using custom type names like i32, u32, etc. in the source code, and we want to map them to the corresponding C types in the generated code
        "#define i32 int32_t".to_string(),
        "#define u32 uint32_t".to_string(),
        "#define i64 int64_t".to_string(),
        "#define u64 uint64_t".to_string(),
        "#define i16 int16_t".to_string(),
        "#define u16 uint16_t".to_string(),
        "#define i8 int8_t".to_string(),
        "#define u8 uint8_t".to_string(),
        "#define string std::string".to_string(),
    ];
    let int_type_redefs_len = int_type_redefs.len();

    for function in &functions {
        let type_ = if function.name == "main" { "int" } else { "void" };
        prototypes.push(format!(
            "{} {}({});",
            type_,
            function.name,
            format_param_list(&function.params_combined)
        )); // example output: "int main();" or "void foo(int a, int b);", this will be added to the top of the generated C code as function prototypes, this is needed for functions that are called before they are defined in the source code
    }

    for function in functions {
        compile_function(&function, &mut compiler);  // compile each function and add the generated C code to the compiler's target
    }
 
    let num_of_includes: usize = resolve_includes(&mut compiler); // add necessary includes at the top of the generated C code based on what features are used in the source code

    for (i, line) in int_type_redefs.iter().cloned().enumerate() {
        compiler.target.insert(num_of_includes + i, line);
    }

    for (i, proto) in prototypes.into_iter().enumerate() {
        compiler.target.insert(num_of_includes + int_type_redefs_len + i, proto);
    }


    return compiler.target;  // return the generated C code as a vector of strings, where each string is a line of C code
}

pub fn compile_function(function: &Func, compiler: &mut Compiler) {
    let source_block: &str = &function.body;
    let source_lines: Vec<String> = source_block.lines().map(|line| line.to_string()).collect();  // split source code into lines
    compiler.variable_types.clear();
    for (idx, param_type) in function.params_ltc_types.iter().enumerate() {
        compiler
            .variable_types
            .insert(format!("arg{}", idx), param_type.clone());
    }
    
    let type_ = if function.name == "main" { "int" } else { "void" };
    compiler.target.push(format!(
        "{} {}({}) {{", 
        type_,
        function.name,
        format_param_list(&function.params_combined)
    ));  // start of function definition in C

    // This is the actual compilation loop

    let mut lineidx = 0;
    while lineidx < source_lines.len() {

        let line = &source_lines[lineidx];  // read line, line is &str

        if line.trim_start().starts_with("*") { // handles comments
            lineidx += 1;
            continue;
        }

        let intermediate = lexer(line); // tokenize line, intermediate is Vec<String>
        let tokens: Vec<Token> = parser(intermediate, &compiler);  // give types, parser should return Vec<Token>

        compile_line(&tokens, compiler);  // compile line, this should generate C code
        //println!("Line {}: {:?}", lineidx + 1, &tokens); // debug
        lineidx += 1;
    }
    compiler.target.push("}".to_string());  // end of function definition in C
}

pub fn compile_line(tokens: &Vec<Token>, compiler: &mut Compiler) {
    // Placeholder compile implementation`
    let mut target_line = String::new();  // this will hold the generated C code for the line

    if tokens.is_empty() {
        return compiler.target.push(target_line);
    }
    if tokens[0].type_ != "keyword".to_string() {
        println!("Error: Line must start with a keyword, instead starts with '{}'", tokens[0].value);
        std::process::exit(1);
    }
    match tokens[0].value.as_str() {
        "mov" => { // mov [src] -> [dest]
            if tokens.len() != 4 {
                println!("Error: 'mov' instruction requires exactly 4 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            } // beyond this, assume the instruction is well-formed
            let dest = &tokens[3].value;
            let src = &tokens[1].value;
            target_line = format!("\t{} = {};", dest, src);  // generate C code for mov instruction
        }
        "make_var" => {
            if tokens.len() != 4 {
                println!("Error: 'make_var' instruction requires exactly 4 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            } // beyond this, assume the instruction is well-formed
            let var_name = &tokens[3].value;
            let var_type = &tokens[1].value;
            compiler.variable_types.insert(var_name.clone(), var_type.clone());
            target_line = format!("\t{} {};", helper::convert_type(var_type), var_name);  // generate C code for variable declaration
        }
        "typeof" => {
            if tokens.len() != 4 {
                println!("Error: 'typeof' instruction requires exactly 4 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            }
            if tokens[2].type_ != "arrow" || tokens[3].type_ != "variable" {
                println!("Error: 'typeof' instruction must be in the form 'typeof [any] -> [var]'");
                std::process::exit(1);
            }

            let resolved_type_name = resolve_typeof_type(&tokens[1], compiler);
            let dest = &tokens[3].value;
            target_line = format!("\t{} = \"{}\";", dest, resolved_type_name);
        }
        "exit" => {
            if tokens.len() != 2 {
                println!("Error: 'exit' instruction requires exactly 2 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            } // beyond this, assume the instruction is well-formed
            let return_value = &tokens[1].value;
            target_line = format!("\texit({});", return_value);  // generate C code for exit instruction
            compiler.using_stdlib = true; // mark that we're using the standard library, this will be used to determine whether we need to include stdlib.h at the top of the generated C code
        }
        
        "ret" => { // ret [type] [value]
            if tokens.len() != 3 {
                println!("Error: 'ret' instruction requires exactly 3 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            } // beyond this, assume the instruction is well-formed
            let return_type = &tokens[1].value; // return type is determined per return, not at definition, this is because we want to allow for different return types in the same function, this is a flexibility that C allows with void* pointers, and we'll use this flexibility in our convention for returning values from functions in C
            let return_value = &tokens[2].value;
            target_line = format!("\t*({}*)ret = {};", return_type, return_value);  // ret* is a pointer to the return value, this is a convention we'll use for returning values from functions in C
            }
        "call" => { // call [function_name] [arg1] [arg2] ... -> [dest]
            if tokens.len() < 3 {
                println!("Error: 'call' instruction requires at least 3 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            } // beyond this, assume the instruction is well-formed
            let func_name = &tokens[1].value;
            let mut args: Vec<String> = tokens[2..tokens.len() - 2].iter().map(|t| t.value.clone()).collect();
            let dest: &String = &tokens[tokens.len() - 1].value;
            args.insert(0, "&".to_string() + &dest.clone()); // add the last argument first, which is currently being treated as dest, to the args list
            target_line = format!("\t{}({});", func_name, args.join(", "));  // generate C code for function call
        }
        "printf" => { // printf [value]
            if tokens.len() != 2 {
                println!("Error: 'printf' instruction requires exactly 2 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            } // beyond this, assume the instruction is well-formed

            let output_expr: String = if tokens[1].type_ == "u8" || tokens[1].type_ == "i8" {
                format!("static_cast<int>({})", tokens[1].value)
            } else {
                tokens[1].value.clone()
            };

            target_line = format!("\tstd::cout << {} << \"\\n\";",  output_expr);  // generate C code for print instruction, this assumes we're printing an integer, for simplicity
            compiler.using_stdio = true; // mark that we're using the standard io, this will be used to determine whether we need to include stdlib.h at the top of the generated C code
            compiler.using_iostream = true; // mark that we're using iostream, this will be used to determine whether we need to include iostream at the top of the generated C++ code
            }
        "print" => { // print [value]
            if tokens.len() != 2 {
                println!("Error: 'print' instruction requires exactly 2 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            } // beyond this, assume the instruction is well-formed
            
            let output_expr: String = if tokens[1].type_ == "u8" || tokens[1].type_ == "i8" {
                format!("static_cast<int>({})", tokens[1].value)
            } else {
                tokens[1].value.clone()
            };


            target_line = format!("\tstd::cout << {};",  output_expr);  // generate C code for print instruction, this assumes we're printing an integer, for simplicity
            compiler.using_stdio = true; // mark that we're using the standard io, this will be used to determine whether we need to include stdlib.h at the top of the generated C code
            compiler.using_iostream = true; // mark that we're using iostream, this will be used to determine whether we need to include iostream at the top of the generated C++ code
            }

        "flush" => {
            if tokens.len() != 1 {
                println!("Error: 'flush' instruction requires exactly 1 token, instead recieved {}", tokens.len());
                std::process::exit(1);
            }
            target_line = format!("\tstd::cout.flush();");  // generate C code for flush instruction
            compiler.using_iostream = true; // mark that we're using iostream, this will be used to determine whether we need to include iostream at the top of the generated C++ code
        
            }
        "input" => { // input -> [var]
            if tokens.len() != 3 {
                println!("Error: 'print' instruction requires exactly 3 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            } // beyond this, assume the instruction is well-formed
            let dest = &tokens[2].value;

            target_line = format!("\tstd::getline(std::cin, {});",  dest);
            compiler.using_iostream = true; // mark that we're using iostream, this will be used to determine that we need to include iostream at the top of the generated C++ code
        }
        
        "add" => // add [integer] [integer] -> [dest_var]
            {
                if tokens.len() != 5 {
                    println!("Error: 'add' instruction requires exactly 5 tokens, instead recieved {}", tokens.len());
                    std::process::exit(1);
                }
                let lhs = &tokens[1].value;
                let rhs = &tokens[2].value;
                let dest = &tokens[4].value;
                target_line = format!("\t{} = {} + {};", dest, lhs, rhs);
            }
        "sub" => // sub [integer] [integer] -> [dest_var]
            {
                if tokens.len() != 5 {
                    println!("Error: 'sub' instruction requires exactly 5` tokens, instead recieved {}", tokens.len());
                    std::process::exit(1);
                }
                let lhs = &tokens[1].value;
                let rhs = &tokens[2].value;
                let dest = &tokens[4].value;
                target_line = format!("\t{} = {} - {};", dest, lhs, rhs);
            }
        "mult" => // mult [integer] [integer] -> [dest_var]
            {
                if tokens.len() != 5 {
                    println!("Error: 'mult' instruction requires exactly 5` tokens, instead recieved {}", tokens.len());
                    std::process::exit(1);
                }
                let lhs = &tokens[1].value;
                let rhs = &tokens[2].value;
                let dest = &tokens[4].value;
                target_line = format!("\t{} = {} * {};", dest, lhs, rhs);
            }
        "div" => // div [integer] [integer] -> [dest_var]
            {
                if tokens.len() != 5 {
                    println!("Error: 'div' instruction requires exactly 5` tokens, instead recieved {}", tokens.len());
                    std::process::exit(1);
                }
                let lhs = &tokens[1].value;
                let rhs = &tokens[2].value;
                let dest = &tokens[4].value;
                target_line = format!("\t{} = {} / {};", dest, lhs, rhs);
        }
        "or" => // or [boolean] [boolean] -> [dest_var]
            {
                if tokens.len() != 5 {
                    println!("Error: 'or' instruction requires exactly 5 tokens, instead recieved {}", tokens.len());
                    std::process::exit(1);
                }
                let lhs = &tokens[1].value;
                let rhs = &tokens[2].value;
                let dest = &tokens[4].value;
                target_line = format!("\t{} = {} || {};", dest, lhs, rhs);
            }
        "and" => // and [boolean] [boolean] -> [dest_var]
            {
                if tokens.len() != 5 {
                    println!("Error: 'and' instruction requires exactly 5 tokens, instead recieved {}", tokens.len());
                    std::process::exit(1);
                }
                let lhs = &tokens[1].value;
                let rhs = &tokens[2].value;
                let dest = &tokens[4].value;
                target_line = format!("\t{} = {} && {};", dest, lhs, rhs);
            }
        "not" => // not [boolean] -> [dest_var]
            {
                if tokens.len() != 4 {
                    println!("Error: 'not' instruction requires exactly 4 tokens, instead recieved {}", tokens.len());
                    std::process::exit(1);
                }
                let lhs = &tokens[1].value;
                let dest = &tokens[3].value;
                target_line = format!("\t{} = !{};", dest, lhs);
            }
        "equal" => // equal [any] [any] -> [dest_var]
            {
                if tokens.len() != 5 {
                    println!("Error: 'equal' instruction requires exactly 5 tokens, instead recieved {}", tokens.len());
                    std::process::exit(1);
                }
                let lhs = &tokens[1].value;
                let rhs = &tokens[2].value;
                let dest = &tokens[4].value;
                target_line = format!("\t{} = {} == {};", dest, lhs, rhs);
            }
        "greater" => // greater [integer] [integer] -> [dest_var]
            {
                if tokens.len() != 5 {
                    println!("Error: 'greater' instruction requires exactly 5 tokens, instead recieved {}", tokens.len());
                    std::process::exit(1);
                }
                let lhs = &tokens[1].value;
                let rhs = &tokens[2].value;
                let dest = &tokens[4].value;
                target_line = format!("\t{} = {} > {};", dest, lhs, rhs);
            }
        "less" => // less [integer] [integer] -> [dest_var]
            {
                if tokens.len() != 5 {
                    println!("Error: 'less' instruction requires exactly 5 tokens, instead recieved {}", tokens.len());
                    std::process::exit(1);
                }
                let lhs = &tokens[1].value;
                let rhs = &tokens[2].value;
                let dest = &tokens[4].value;
                target_line = format!("\t{} = {} < {};", dest, lhs, rhs);
        }
        "malloc" => // malloc [integer] -> [dest_var]
            {
            if tokens.len() != 4 {
                println!("Error: 'malloc' instruction requires exactly 4 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            } // beyond this, assume the instruction is well-formed
            let dest = &tokens[3].value;
            let size = &tokens[1].value;
            target_line = format!("\t{} = calloc({}, 1);", dest, size);  // generate C code for malloc instruction. C++ Calloc is used to initalize the data to 0
            }
        "free" => // free [ptr]
            {
            if tokens.len() != 2 {
                println!("Error: 'free' instruction requires exactly 2 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            } // beyond this, assume the instruction is well-formed
            let free = &tokens[1].value;
            target_line = format!("\tfree({});", free);  // generate C code for free instruction
            }

        "get_at" => // get_at [var] [type] [integer] -> [dest_var]
            {
            if tokens.len() != 6 {
                println!("Error: 'get_at' instruction requires exactly 6 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            } // beyond this, assume the instruction is well-formed
            let dest = &tokens[5].value;
            let idx = &tokens[3].value;
            let _type = &tokens[2].value;
            let origin = &tokens[1].value;
            target_line = format!("\t{} = (({}*){})[{}];", dest, _type, origin, idx);  // generate C code for get_at instruction
            }
        "set_at" => // set_at [any] -> [dest var] [type] [integer]
            {
            if tokens.len() != 6 {
                println!("Error: 'set_at' instruction requires exactly 6 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            } // beyond this, assume the instruction is well-formed
            let dest = &tokens[3].value;
            let idx = &tokens[5].value;
            let _type = &tokens[4].value;
            let origin = &tokens[1].value;
            target_line = format!("\t(({}*){})[{}] = {};", _type, dest, idx, origin);  // generate C code for get_at instruction
            }


        _ => {
            println!("Error: Unknown keyword '{}'", tokens[0].value);
            std::process::exit(1);
        }
    }

    compiler.target.push(target_line);
}
