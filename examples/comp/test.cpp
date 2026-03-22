#include <iostream>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
int main(void);
void ltc_main(int* ret);
#define i32 int32_t
#define u32 uint32_t
#define i64 int64_t
#define u64 uint64_t
#define i16 int16_t
#define u16 uint16_t
#define i8 int8_t
#define u8 uint8_t
int main(void) {
	i32 return_value;
	ltc_main(&return_value);
	exit(return_value);
}
void ltc_main(int* ret) {
	i32 x;
	x = 5;
	std::cout << 'h' << "\n";
	std::cout << x << "\n";
	x = x + 1;
	std::cout << x << "\n";
	std::cout.flush();
	*ret = 0;
}