#include <stdlib.h>
void main(void);
void ltc_main(int* ret);
void main(void) {
	int return_value;
	ltc_main(&return_value);
	exit(return_value);
}
void ltc_main(int* ret) {
	int x;
	x = 5;
	printf("%d\n", x);
	*ret = 0;
}