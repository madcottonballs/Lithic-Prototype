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
int main(void);
void ltc_main(void* ret);
void ltcadd(void* ret, i32 arg0, i32 arg1);
int main(void) {
	i32 return_value;
	ltc_main(&return_value);
	exit(return_value);
}
void ltc_main(void* ret) {
	i32 num1;
	i32 num2;
	num1 = 5;
	num2 = 10;
	ltcadd(&num1, num1, num2);
	std::cout << num1 << "\n";
	*(i32*)ret = 0;
}
void ltcadd(void* ret, i32 arg0, i32 arg1) {
	i32 test;
	test = arg0 + arg1;
	*(i32*)ret = test;
}