#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include <wiringPi.h>
#include <lcd.h>

#define ROWS    2    // 2 lines
#define COLS    16   // 16 chars
#define BITS    4    // 4-bit mode
#define MS      1000 // ms

#define RS      7
#define STRB    0
#define D4      2
#define D5      3
#define D6      1
#define D7      4

int wiringPiSetup(void);

static char lcdBuf[ROWS][COLS] = {0, };
static int lcdFd = 0;

static void setLcdBuf(char *fname) {
    FILE *fp;
    char buf[COLS];
    int i = 0;

    memset((void *)&lcdBuf, ' ', sizeof(lcdBuf));

    if (access(fname, R_OK) != -1) {
        fp = fopen(fname, "r");
        if (fp != NULL) {
            while ((fgets(buf, sizeof(buf), fp) != NULL) && (i < ROWS)) {
                buf[strlen(buf) - 1] = '\0';
                strncpy(&lcdBuf[i][0], &buf[0], strlen(buf));
                i++;
            }
        }
        fclose(fp);
    }
}

static void lcdUpdate(void) {
    int i, j;

    for (i = 0; i < ROWS; i++) {
        lcdPosition(lcdFd, 0, i);

        for (j = 0; j < COLS; j++) {
            lcdPutchar(lcdFd, lcdBuf[i][j]);
        }
    }
}

int systemInit(void) {
    lcdFd = lcdInit(ROWS, COLS, BITS, RS, STRB, D4, D5, D6, D7, 0, 0, 0, 0);

    if (lcdFd < 0) {
        fprintf(stderr, "lcdInit() failed!\n");
        return -1;
    }

    return  0;
}

int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "missing filename argument!\n");
        return -1;
    }

    wiringPiSetup();

    if (systemInit() < 0) {
        fprintf(stderr, "systemInit() failed!\n");
        return -1;
    }

    for(;;) {
        usleep(MS * 1000);
        setLcdBuf(argv[1]);
        lcdUpdate();
    }

    return 0 ;
}
