use std::env;
use std::fs;

#[derive(Debug)]
struct Token {
    value: String,
    type_: String,
}
impl Token {
    fn new(value: &str, type_: &str) -> Self {
        Token {
            value: value.to_string(),
            type_: type_.to_string(),
        }
    }
}

struct Func {
    name: String,
    body: String,
    params: usize, // for simplicity, we'll assume all functions have 0 parameters for now debug
}
impl Func {
    fn new(name: &str, body: &str, params: usize) -> Self {
        Func {
            name: name[1..name.len()].to_string(),
            body: body.to_string(),
            params: 0, // for simplicity, we'll assume all functions have 0 parameters for now debug
        }
    }
}


struct Compiler {
    keywords: Vec<String>,
    type_names: Vec<String>,
    target: Vec<String>,
}

impl Compiler {
    fn new() -> Self {
        Compiler { 
            keywords: vec![
                "let".into(), 
                "define".into(),
                "ret".into(),
                "add".into(),
                "sub".into(),
                "mul".into(),
                "div".into(),
                "printf".into(),
                "input".into(),
                "inlineC".into(),
                "define".into(),
                "end".into(),
                "call".into(),
                "mov".into(),
                "make_var".into(),
                "exit".into(),
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
        }
    }
}

fn get_sys_args() -> Vec<String> {
    let args: Vec<String> = env::args().collect();

    if args.len() < 2 {
        println!("Usage: {} <source_file>", args[0]);
        std::process::exit(1);
    }
    return args;
}

fn lexer(source_line: &str) -> Vec<String> {
    // Placeholder lexer implementation
    return source_line.split_whitespace().map(|s| s.to_string()).collect();  // split line into tokens based on whitespace
}

fn parser(intermediate: Vec<String>, compiler: &Compiler) -> Vec<Token> {
    let mut tokens: Vec<Token> = intermediate
        .into_iter()
        .map(|value| Token::new(&value, "generic"))
        .collect(); // convert Vec<String> to Vec<Token> with a generic type

    for token in tokens.iter_mut() {
        if token.type_ != "generic" {
            continue;  // skip tokens that have already been classified
        }
        if token.value.starts_with('"') && token.value.ends_with('"') {
            token.value = token.value.trim_matches('"').to_string();  // remove surrounding quotes
            token.type_ = "string".to_string();
        }
        if token.value.starts_with("$") {
            token.value = token.value.trim_start_matches('$').to_string();  // remove leading $
            token.type_ = "integer".to_string();
        }
        if token.value.starts_with("%") {
            token.value = token.value.trim_start_matches('%').to_string();  // remove leading %
            token.type_ = "variable".to_string();
        }
        if token.value.starts_with("#") {
            token.value = token.value.trim_start_matches('#').to_string();  // remove leading #
            token.type_ = "function".to_string();
        }
        if token.value.starts_with("|") {
            token.value = token.value.trim_start_matches('|').to_string();  // remove leading |
            token.type_ = "boolean".to_string();
        } 
        if token.value == "->" {
            token.type_ = "arrow".to_string();
        }
        if compiler.keywords.contains(&token.value) {
            token.type_ = "keyword".to_string();
        }
        if compiler.type_names.contains(&token.value) {
            token.type_ = "type".to_string();
        }
    }
    return tokens;
}

fn compile_line(tokens: &Vec<Token>, compiler: &mut Compiler) {
    // Placeholder compile implementation`
    let mut target_line = String::new();  // this will hold the generated C code for the line
    // For demonstration, we'll just join the token values with spaces
    if tokens.is_empty() {
        return compiler.target.push(target_line);
    }
    if tokens[0].type_ != "keyword".to_string() {
        println!("Error: Line must start with a keyword");
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
            target_line = format!("\t{} {};", convert_type(var_type), var_name);  // generate C code for variable declaration
        }
        "exit" => {
            // Handle exit instruction
        }
        "ret" => {
            if tokens.len() != 2 {
                println!("Error: 'ret' instruction requires exactly 2 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            } // beyond this, assume the instruction is well-formed
            let return_value = &tokens[1].value;
            target_line = format!("\treturn {};", return_value);  // generate C code for return instruction
        }
        "call" => {
            if tokens.len() < 2 {
                println!("Error: 'call' instruction requires at least 2 tokens, instead recieved {}", tokens.len());
                std::process::exit(1);
            } // beyond this, assume the instruction is well-formed
            let func_name = &tokens[1].value;
            let args: Vec<String> = tokens[2..tokens.len() - 2].iter().map(|t| t.value.clone()).collect();
            let dest = &tokens[tokens.len() - 1].value;
            target_line = format!("\t{} = {}({});", dest, func_name, args.join(", "));  // generate C code for function call
        }
        _ => {
            println!("Error: Unknown keyword '{}'", tokens[0].value);
            std::process::exit(1);
        }
    }

    compiler.target.push(target_line);
}

fn convert_type(ltcir_type: &str) -> &str {
    match ltcir_type {
        "i32" => "int",
        "u32" => "unsigned int",
        "i64" => "long long",
        "u64" => "unsigned long long",
        "i16" => "short",
        "u16" => "unsigned short",
        "i8" => "char",
        "u8" => "unsigned char",
        "string" => "char*",
        "boolean" => "_Bool",
        "char" => "char",
        _ => {
            println!("Error: Unknown type '{}'", ltcir_type);
            std::process::exit(1);
        }
    }
}

fn find_functions(source_code: &str) -> Vec<Func> {
    let mut lineidx = 0;
    let mut functions: Vec<Func> = Vec::new();  // this will hold the source code blocks for each function found             
    let source_lines: Vec<String> = source_code.lines().map(|line| line.to_string()).collect();  // split source code into lines
    
    while lineidx < source_lines.len() {
        let intermediate: Vec<String> = lexer(&source_lines[lineidx]); // tokenize line, this is just to check for function definitions, we won't use the tokens for anything else in this function
        if intermediate.is_empty() {
            lineidx += 1;
            continue;
        }
        if intermediate[0] == "define".to_string() {
            let func_name: &str = &intermediate[1];

            let mut func_body = String::new();
            lineidx += 1; // start collecting after the define line
            while lineidx < source_lines.len() {
                let line = &source_lines[lineidx];
                if line.trim_start().starts_with("end") {
                    break;
                }
                func_body.push_str(line);
                func_body.push('\n'); // add line to function body, this assumes the function body is well-formed
                lineidx += 1;
            }
            functions.push(Func::new(func_name, &func_body, 0));  // add function to list of functions found, for simplicity, we'll assume all functions have 0 parameters for now debug
            // skip the "end" line if we stopped on it
            if lineidx < source_lines.len() {
                lineidx += 1;
            }
            continue;
        }
        lineidx += 1;
    }
    return functions;
}

fn compile_file(source_code: &str) -> Vec<String> {
    let mut compiler = Compiler::new();  // create a new compiler instance

    // find all functions in the source code, for simplicity, we'll assume that the entire source code is main() function
    let functions: Vec<Func> = find_functions(source_code);
    for function in functions {
        compile_function(&function, &mut compiler);  // compile each function and add the generated C code to the compiler's target
    }

    return compiler.target;  // return the generated C code as a vector of strings, where each string is a line of C code
}

fn compile_function(function: &Func, compiler: &mut Compiler) {
    let source_block: &str = &function.body;
    let source_lines: Vec<String> = source_block.lines().map(|line| line.to_string()).collect();  // split source code into lines
    
    compiler.target.push(format!("void {}() {{", function.name));  // start of function definition in C
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

    let all_file_name_parts_but_ext: String = if source_file_parts.len() > 1 {   source_file_parts[..source_file_parts.len() - 1].join(".")  } else {String::new()}; // get file name without extension, this will be used for output file name
    
    let source_code = fs::read_to_string(source_file)
        .expect("Failed to read source file"); // read source file into a string, this will be the input to the compiler
    
    // start compilation, this should return a Vec<String> where each string is a line of C code
    let target_code = compile_file(&source_code);

    // Write the generated C code to an output file with the same name but .c extension
    let output_file_name = format!("{}.c", all_file_name_parts_but_ext);
    fs::write(&output_file_name, target_code.join("\n"))
        .expect("Failed to write output file");
}
