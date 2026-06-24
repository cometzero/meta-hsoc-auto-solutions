# SPDX-License-Identifier: MIT

# Keep the Podman API service socket-activated. Enabling podman.service at
# boot together with podman.socket starts the service against an already-bound
# API socket and leaves the unit failed.
SYSTEMD_SERVICE:${PN}:auto-ad-nexios = "podman.socket"
