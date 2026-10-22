require stream_5.10.bb

SUMMARY = "STREAM variant with a 1.5 MiB working set for gem5 cache tests"

inherit deploy

# Cache-sized variant; results are not standard STREAM DRAM bandwidth results.
STREAM_CPPFLAGS = "-DSTREAM_ARRAY_SIZE=65536"
ALTERNATIVE:${PN} = ""

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${B}/stream ${D}${bindir}/stream-gem5-cache
}

do_deploy() {
    install -d ${DEPLOYDIR}/gem5
    install -m 0755 ${B}/stream ${DEPLOYDIR}/gem5/stream-gem5-cache
}
addtask deploy after do_compile before do_build
