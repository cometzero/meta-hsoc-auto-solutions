SUMMARY = "STREAM sustainable memory bandwidth benchmark"
HOMEPAGE = "https://www.cs.virginia.edu/stream/"
LICENSE = "STREAM"
LIC_FILES_CHKSUM = "file://LICENSE.txt;md5=bca8cbe07976fe64c8946378d08314b0"
NO_GENERIC_LICENSE[STREAM] = "LICENSE.txt"

SRC_URI = "https://www.cs.virginia.edu/stream/FTP/Code/stream.c;name=source \
           https://www.cs.virginia.edu/stream/FTP/Code/LICENSE.txt;name=license"
SRC_URI[source.sha256sum] = "a52bae5e175bea3f7832112af9c085adab47117f7d2ce219165379849231692b"
SRC_URI[license.sha256sum] = "8649dd650343de1426d8d134f139734a9b70ee7bdc347c626b8c6d9029301287"

S = "${UNPACKDIR}"
B = "${WORKDIR}/build"

inherit update-alternatives

# Keep upstream defaults: three 10M-double arrays, ten iterations, one thread.
# Override with e.g. -DSTREAM_ARRAY_SIZE=20000000; record flags with results.
STREAM_CPPFLAGS ?= ""

do_compile() {
    ${CC} ${CPPFLAGS} ${CFLAGS} ${STREAM_CPPFLAGS} \
        ${S}/stream.c ${LDFLAGS} -lm -o ${B}/stream
}

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${B}/stream ${D}${bindir}/stream
}

# lmbench also installs a different benchmark named stream.
ALTERNATIVE:${PN} = "stream"
ALTERNATIVE_LINK_NAME[stream] = "${bindir}/stream"
ALTERNATIVE_PRIORITY[stream] = "100"
