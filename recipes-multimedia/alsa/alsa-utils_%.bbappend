FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

SRC_URI:append:apollo-qvp = " file://0001-aplay-bounded-drain.patch"
