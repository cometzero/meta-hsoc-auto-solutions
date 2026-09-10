/* SPDX-License-Identifier: MIT */
/* One process arms both ALSA streams and compares a complete PCM sequence. */
#include <alsa/asoundlib.h>
#include <stdint.h>
#include <time.h>
#include <unistd.h>

#define FRAMES 65536
#define BUFFER 16384
#define PERIOD 1024

static void check(int rc, const char *operation)
{
    if (rc < 0) {
        fprintf(stderr, "%s: %s\n", operation, snd_strerror(rc));
        exit(1);
    }
}

static snd_pcm_t *open_pcm(const char *name, snd_pcm_stream_t stream)
{
    snd_pcm_t *pcm;
    snd_pcm_hw_params_t *hw;
    snd_pcm_sw_params_t *sw;
    snd_pcm_uframes_t boundary;

    check(snd_pcm_open(&pcm, name, stream, SND_PCM_NONBLOCK), "open");
    snd_pcm_hw_params_alloca(&hw);
    check(snd_pcm_hw_params_any(pcm, hw), "hw any");
    check(snd_pcm_hw_params_set_access(pcm, hw, SND_PCM_ACCESS_RW_INTERLEAVED), "access");
    check(snd_pcm_hw_params_set_format(pcm, hw, SND_PCM_FORMAT_S16_LE), "format");
    check(snd_pcm_hw_params_set_channels(pcm, hw, 2), "channels");
    check(snd_pcm_hw_params_set_rate(pcm, hw, 48000, 0), "rate");
    check(snd_pcm_hw_params_set_period_size(pcm, hw, PERIOD, 0), "period");
    check(snd_pcm_hw_params_set_buffer_size(pcm, hw, BUFFER), "buffer");
    check(snd_pcm_hw_params(pcm, hw), "hw params");
    snd_pcm_sw_params_alloca(&sw);
    check(snd_pcm_sw_params_current(pcm, sw), "sw current");
    check(snd_pcm_sw_params_get_boundary(sw, &boundary), "boundary");
    check(snd_pcm_sw_params_set_start_threshold(pcm, sw, boundary), "manual start");
    check(snd_pcm_sw_params_set_avail_min(pcm, sw, 1), "avail min");
    check(snd_pcm_sw_params(pcm, sw), "sw params");
    check(snd_pcm_prepare(pcm), "prepare");
    return pcm;
}

int main(int argc, char **argv)
{
    static uint16_t tx[FRAMES + BUFFER][2], rx[PERIOD][2];
    snd_pcm_t *play, *capture;
    snd_pcm_sframes_t n;
    unsigned int received = 0;
    unsigned int written = BUFFER;
    unsigned int idle = 0;
    unsigned int seed = 0x1234;
    struct timespec start, now;

    if (argc != 3) {
        fprintf(stderr, "Usage: %s playback-pcm capture-pcm\n", argv[0]);
        return 2;
    }
    for (const unsigned char *p = (const unsigned char *)argv[1]; *p; ++p)
        seed = seed * 33u + *p;
    for (unsigned int i = 0; i < FRAMES + BUFFER; ++i) {
        tx[i][0] = (uint16_t)(i * 73u + seed);
        tx[i][1] = (uint16_t)(i * 151u + (seed ^ 0xabcdu));
    }
    capture = open_pcm(argv[2], SND_PCM_STREAM_CAPTURE);
    play = open_pcm(argv[1], SND_PCM_STREAM_PLAYBACK);
    n = snd_pcm_writei(play, tx, BUFFER);
    check((int)n, "preload");
    if (n != BUFFER) return 1;
    check(snd_pcm_start(capture), "start capture");
    check(snd_pcm_start(play), "start playback");
    clock_gettime(CLOCK_MONOTONIC, &start);
    while (received < FRAMES) {
        if (written < FRAMES + BUFFER) {
            n = snd_pcm_writei(play, tx + written, FRAMES + BUFFER - written);
            if (n > 0) written += n;
            else if (n != -EAGAIN) check((int)n, "playback write");
        }
        n = snd_pcm_readi(capture, rx, PERIOD);
        if (n > 0) {
            for (snd_pcm_sframes_t i = 0; i < n && received < FRAMES; ++i) {
                /* An enabled I2S clock emits zeros before the first TX IRQ. */
                if (!received && !rx[i][0] && !rx[i][1] && idle < BUFFER) {
                    ++idle;
                    continue;
                }
                if (rx[i][0] != tx[received][0] || rx[i][1] != tx[received][1]) {
                    fprintf(stderr, "mismatch frame=%u expected=%04x/%04x actual=%04x/%04x idle=%u\n",
                            received, tx[received][0], tx[received][1], rx[i][0], rx[i][1], idle);
                    snd_pcm_drop(play);
                    snd_pcm_drop(capture);
                    return 1;
                }
                ++received;
            }
        } else if (n != -EAGAIN) {
            check((int)n, "capture read");
        }
        clock_gettime(CLOCK_MONOTONIC, &now);
        if (now.tv_sec - start.tv_sec > 120) {
            fprintf(stderr, "timeout: received=%u/%u capture=%s playback=%s\n",
                    received, FRAMES, snd_pcm_state_name(snd_pcm_state(capture)),
                    snd_pcm_state_name(snd_pcm_state(play)));
            snd_pcm_drop(play);
            snd_pcm_drop(capture);
            return 1;
        }
        if (n == -EAGAIN) usleep(100);
    }
    check(snd_pcm_drop(play), "drop playback");
    check(snd_pcm_drop(capture), "drop capture");
    snd_pcm_close(play);
    snd_pcm_close(capture);
    printf("I2S_LOOPBACK_PASS playback=%s capture=%s frames=%u bytes=%u format=S16_LE rate=48000 idle=%u\n",
           argv[1], argv[2], FRAMES, FRAMES * 4, idle);
    return 0;
}
