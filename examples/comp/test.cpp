#include <string>
#include <iostream>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#define i32 int32_t
#define u32 uint32_t
#define i64 int64_t
#define u64 uint64_t
#define i16 int16_t
#define u16 uint16_t
#define i8 int8_t
#define u8 uint8_t
#define string std::string
int main(void);
void ltc_main(void* ret);
void ltcadd(void* ret, i32 arg0, i32 arg1);
void stringrettest(void* ret);
int main(void) {
	i32 return_value;
	ltc_main(&return_value);
	exit(return_value);
}
void ltc_main(void* ret) {
	string retval;
	stringrettest(&retval);

	std::cout << retval << "\n";

	*(i32*)ret = 0;
}
void ltcadd(void* ret, i32 arg0, i32 arg1) {
	i32 test;
	test = arg0 + arg1;
	*(i32*)ret = test;
}
void stringrettest(void* ret) {
	*(string*)ret = "hello world";
}