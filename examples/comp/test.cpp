#include <tuple>
#include <string>
#include <stdint.h>
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
	i32 arrtest[3];
	((i32*)arrtest)[0] = 7;
	((i32*)arrtest)[1] = 11;

	std::tuple<i32, string> pair;


	*(i32*)ret = 0;
}