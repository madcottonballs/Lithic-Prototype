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
int main(void) {
	i32 return_value;
	ltc_main(&return_value);
	exit(return_value);
}
void ltc_main(void* ret) {
	void* exam;
	exam = calloc(100, 1);

	u8 test;

	((u8*)exam)[0] = 50;
	test = ((u8*)exam)[0];
	std::cout << test << "\n";
	free(exam);

	*(i32*)ret = 0;
}