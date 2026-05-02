use crate::helper;
use crate::{lexer, Compiler};
#[derive(Debug)]
pub struct Token {
    pub value: String,
    pub type_: String,
}
impl Token {
    pub fn new(value: &str, type_: &str) -> Self {
        Token {
            value: value.to_string(),
            type_: type_.to_string(),
        }
    }
}

pub struct Func {
    pub name: String,
    pub body: String,
    pub params_ltc_types: Vec<String>, // this will hold the LtcIR type names of the parameters, e.g. "i32", "string", etc.
    pub params_c_types: Vec<String>, // this will hold the C type equivalents of the parameter types, e.g. "int", "char*", etc.
    pub params_names: Vec<String>, // this will hold the parameter names for the function, e.g. "a", "b", etc.
    pub params_combined: Vec<String>, // this will hold the combined parameter declarations for the function, e.g. "int a, char* b" 
}
impl Func {
    pub fn new(name: &str, body: &str, params_ltc_types: Vec<String>, params_names: Vec<String>) -> Self {
        let mut params_c_types: Vec<String> = params_ltc_types
            .iter()
            .map(|t| helper::convert_type(t).to_string())
            .collect(); // convert LtcIR types to C types
        if name != "#main" { // skip paramters for entry function
            params_c_types.insert(0, "void*".to_string()); // add a parameter for the return value, this is a convention we'll use for returning values from functions in C, the return value will be passed as a pointer to the function
        }

        let mut params_names: Vec<String> = if params_names.len() == 0 {
            // if no parameter names were provided, generate default names like arg0, arg1, etc. For now, no arg names are ever expected.
            (0..params_ltc_types.len()).map(|i| format!("arg{}", i)).collect()
        } else {
            params_names
        };
        if name != "#main" { // skip paramters for entry function
            params_names.insert(0, "ret".to_string()); // add a parameter for the return value, this is a convention we'll use for returning values from functions in C, the return value will be passed as a pointer to the function
        }
        
        let params_combined: Vec<String> = params_c_types
            .iter()
            .zip(params_names.iter())
            .map(|(c_type, name)| format!("{} {}", c_type, name))
            .collect(); // combine C types and parameter names into declarations

        return Func {
            name: name[1..name.len()].to_string(),
            body: body.to_string(),
            params_ltc_types: params_ltc_types,
            params_c_types,
            params_names,
            params_combined,
        }
    }
}

pub fn parser(intermediate: Vec<String>, compiler: &Compiler) -> Vec<Token> {
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
        if token.value.starts_with('\'') && token.value.ends_with('\'') && token.value.len() >= 3 {
            token.value = token.value.trim_matches('\'').to_string();
            token.type_ = "char".to_string();
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

pub fn find_functions(source_code: &str) -> Vec<Func> {
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
            let params_ltc_types: Vec<String> = if intermediate.len() > 2 { intermediate[2..].to_vec() } else { Vec::new() }; // get function parameters from the define line, this assumes that the define line is well-formed and that all parameters are listed after the function name

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
            functions.push(Func::new(func_name, &func_body, params_ltc_types, Vec::new()));  // add function to list of functions found, for simplicity, we'll assume all functions have 0 parameters for now debug
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

