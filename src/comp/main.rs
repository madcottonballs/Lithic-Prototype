mod parser;
use parser::{parser, find_functions, Token, Func};
mod helper;
use helper::{get_sys_args, format_param_list, resolve_includes};
use std::fs;


struct Compiler {
    keywords: Vec<String>,
    type_names: Vec<String>,
    target: Vec<String>,
    using_stdlib: bool,
    using_stdio: bool,
    using_stdint: bool,
    using_iostream: bool,
}

impl Compiler {
    fn new() -> Self {
        return Compiler { 
            keywords: vec![
                "let".into(), 
                "define".into(),
                "ret".into(),
                "add".into(),
                "sub".into(),
                "mul".into(),
                "div".into(),
                "print".into(),
                "input".into(),
                "inlineCpp".into(),
                "define".into(),
                "end".into(),
                "call".into(),
                "mov".into(),
                "make_var".into(),
                "exit".into(),
                "flush".into(),
                "equal".into(),
                "not_equal".into(),
                "greater".into(),
                "less".into(),
                "and".into(),
                "or".into(),
                "not".into(),
                ],
            type_names: vec![
                "i32".into(),
                "u32".into(),
                "i64".into(),
                "u64".into(),
                "i16".into(),
                "u16".into(),
                "i8".into(),
                "u8".into(),
                "string".into(),
                "boolean".into(),
                "char".into(),
            ],
            target: Vec::new(),
            using_stdlib: false,
            using_stdio: false,
            using_stdint: true,
            using_iostream: false,
        }
    }
}


fn lexer(source_line: &str) -> Vec<String> {
    // Placeholder lexer implementation
    return source_line.split_whitespace().map(|s| s.to_string()).collect();  // split line into tokens based on whitespace
}


fn compile_line(tokens: &Vec<Token>, compiler: &mut Compiler) {
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
        "mov" => {
            if tokens.len() != 5 {
                println!("Error: 'mov' instruction requires exactly 5 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            } // beyond this, assume the instruction is well-formed
            let dest = &tokens[4].value;
            let src = &tokens[2].value;
            target_line = format!("\t{} = {};", dest, src);  // generate C code for mov instruction
        }
        "make_var" => {
            if tokens.len() != 4 {
                println!("Error: 'make_var' instruction requires exactly 4 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            } // beyond this, assume the instruction is well-formed
            let var_name = &tokens[3].value;
            let var_type = &tokens[1].value;
            target_line = format!("\t{} {};", helper::convert_type(var_type), var_name);  // generate C code for variable declaration
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
        "call" => {
            if tokens.len() < 3 {
                println!("Error: 'call' instruction requires at least 3 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            } // beyond this, assume the instruction is well-formed
            let func_name = &tokens[1].value;
            let mut args: Vec<String> = tokens[2..tokens.len() - 3].iter().map(|t| t.value.clone()).collect();
            let dest: &String = &tokens[tokens.len() - 1].value;
            args.insert(0, "&".to_string() + &dest.clone()); // add the last argument first, which is currently being treated as dest, to the args list
            target_line = format!("\t{}({});", func_name, args.join(", "));  // generate C code for function call
        }
        "print" => { // print [value]
            if tokens.len() != 2 {
                println!("Error: 'print' instruction requires exactly 2 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            } // beyond this, assume the instruction is well-formed
            let value = &tokens[1].value;

            target_line = format!("\tstd::cout << {} << \"\\n\";",  value);  // generate C code for print instruction, this assumes we're printing an integer, for simplicity
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
        "add" => // add [integer] [integer] -> [dest_var]
            {
                if tokens.len() != 5 {
                    println!("Error: 'add' instruction requires exactly 5` tokens, instead recieved {}", tokens.len());
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
        _ => {
            println!("Error: Unknown keyword '{}'", tokens[0].value);
            std::process::exit(1);
        }
    }

    compiler.target.push(target_line);
}

fn compile_file(source_code: &str) -> Vec<String> {
    let mut compiler = Compiler::new();  // create a new compiler instance

    // find all functions in the source code, for simplicity, we'll assume that the entire source code is main() function
    let functions: Vec<Func> = find_functions(source_code);
    let mut prototypes: Vec<String> = Vec::new();

    let int_type_redefs: Vec<String> = vec![ // add typedefs for fixed-width integer types from stdint.h, this is needed because we're using custom type names like i32, u32, etc. in the source code, and we want to map them to the corresponding C types in the generated code
        "#define i32 int32_t".to_string(),
        "#define u32 uint32_t".to_string(),
        "#define i64 int64_t".to_string(),
        "#define u64 uint64_t".to_string(),
        "#define i16 int16_t".to_string(),
        "#define u16 uint16_t".to_string(),
        "#define i8 int8_t".to_string(),
        "#define u8 uint8_t".to_string(),
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

fn compile_function(function: &Func, compiler: &mut Compiler) {
    let source_block: &str = &function.body;
    let source_lines: Vec<String> = source_block.lines().map(|line| line.to_string()).collect();  // split source code into lines
    
    
    let type_ = if function.name == "main" { "int" } else { "void" };
    compiler.target.push(format!(
        "{} {}({}) {{", 
        type_,
        function.name,
        format_param_list(&function.params_combined)
    ));  // start of function definition in C

    let mut lineidx = 0;
    while lineidx < source_lines.len() {

        let line = &source_lines[lineidx];  // read line, line is &str

        let intermediate = lexer(line); // tokenize line, intermediate is Vec<String>
        let tokens: Vec<Token> = parser(intermediate, &compiler);  // give types, parser should return Vec<Token>

        compile_line(&tokens, compiler);  // compile line, this should generate C code
        //println!("Line {}: {:?}", lineidx + 1, &tokens); // debug
        lineidx += 1;
    }
    compiler.target.push("}".to_string());  // end of function definition in C
}

fn main() {
    let args: Vec<String> = get_sys_args(); // get command line arguments, this should return a Vec<String> where the first element is the program name and the second element is the source file name

    let source_file: &str = &args[1]; // get source file name from command line arguments, this should be the second element of the args vector
    
    let source_file_parts: Vec<&str> = source_file.split('.').collect();  // split source file name by '.', this will be used to check file extension and get file name without extension
    
    let file_extension: &str = source_file_parts.last().unwrap_or(&""); // get file extension, this should be the last element of the source_file_parts vector, if there is no extension, use an empty string
    if file_extension != "ltcir" {
        println!("Error: Source file must have .ltcir extension");
        std::process::exit(1);
    } // check file extension, if it's not .ltcir, print error message and exit

    let output_file_name: String = if source_file_parts.len() > 1 {   source_file_parts[..source_file_parts.len() - 1].join(".")  } else {String::new()}; // get file name without extension, this will be used for output file name
    
    let source_code = fs::read_to_string(source_file)
        .expect("Failed to read source file"); // read source file into a string, this will be the input to the compiler
    
    // start compilation, this should return a Vec<String> where each string is a line of C code
    let target_code = compile_file(&source_code);

    // Write the generated C code to an output file with the same name but .c extension
    let output_file_name = format!("{}.cpp", output_file_name);
    fs::write(&output_file_name, target_code.join("\n"))
        .expect("Failed to write output file");
}
